"""Logic tier: registration, login, password hashing (scrypt, standard library)."""
import hashlib
import hmac
import os
import re
import sqlite3
import time

from data.repositories import UserRepository

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
users = UserRepository()

MAX_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60
_failures = {}          # email -> timestamps of recent failures (use Redis when you run >1 server)
_clock = time.monotonic


def reset_throttle():
    _failures.clear()


def _check_lock(email):
    now = _clock()
    recent = [t for t in _failures.get(email, []) if now - t < LOCK_SECONDS]
    _failures[email] = recent
    if len(recent) >= MAX_ATTEMPTS:
        minutes = int((LOCK_SECONDS - (now - recent[0])) // 60) + 1
        raise AuthError(f"Too many failed attempts. Try again in {minutes} minute(s).")


class AuthError(ValueError):
    """Raised with a user-friendly message."""


DEFAULT_SCRYPT_N = 2 ** 14      # ~50 ms per login on purpose: it is what makes stolen hashes slow to crack
SCRYPT_N, SCRYPT_R, SCRYPT_P = DEFAULT_SCRYPT_N, 8, 1


def hash_password(password: str) -> str:
    """Stores the cost parameters inside the hash, so the cost can be raised later while old
    hashes keep verifying."""
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                                n=int(n), r=int(r), p=int(p))
    except ValueError:                      # malformed hash, or parameters beyond the memory limit
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def validate_new_account(full_name, email, password, enforce_domain=True):
    full_name, email = full_name.strip(), email.strip().lower()
    if not full_name:
        raise AuthError("Please enter your full name.")
    if not EMAIL_RE.match(email):
        raise AuthError("Please enter a valid email address.")
    domain = os.environ.get("CAMPUS_EMAIL_DOMAIN")  # students only; businesses use their own email
    if enforce_domain and domain and not email.endswith("@" + domain):
        raise AuthError(f"Use your campus email (@{domain}).")
    if len(password) < 8 or not any(ch.isdigit() for ch in password):
        raise AuthError("Password must be at least 8 characters and include a number.")
    return full_name, email


def register(full_name, email, password, matric_no=None):
    """Student (buyer) account."""
    full_name, email = validate_new_account(full_name, email, password)
    try:
        return users.create(full_name, email, (matric_no or None), hash_password(password))
    except sqlite3.IntegrityError:
        raise AuthError("An account with that email or matric number already exists.")


def login(email, password):
    email = email.strip().lower()
    _check_lock(email)                       # counts unknown emails too, so lock-outs reveal nothing
    user = users.get_by_email(email)
    # Same message for both failures so attackers can't discover which emails exist.
    if not user or not verify_password(password, user["password_hash"]):
        _failures.setdefault(email, []).append(_clock())
        raise AuthError("Invalid email or password.")
    _failures.pop(email, None)
    return user
