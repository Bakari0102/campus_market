import pytest
from services import auth_service as auth
from services.auth_service import AuthError


def test_hash_is_salted_and_verifies():
    h1, h2 = auth.hash_password("secret123"), auth.hash_password("secret123")
    assert h1 != h2                       # different salts
    assert auth.verify_password("secret123", h1)
    assert not auth.verify_password("wrong", h1)


def test_verify_handles_corrupt_hash():
    assert auth.verify_password("x", "not-a-valid-hash") is False


def test_register_and_login(seller):
    user = auth.login("  ADA@uni.edu ", "password1")   # trimmed, case-insensitive
    assert user["id"] == seller
    assert user["password_hash"] != "password1"


@pytest.mark.parametrize("name,email,pw", [
    ("", "a@b.com", "password1"),
    ("A", "not-an-email", "password1"),
    ("A", "a@b.com", "short1"),
    ("A", "a@b.com", "nodigitshere"),
])
def test_register_rejects_bad_input(name, email, pw):
    with pytest.raises(AuthError):
        auth.register(name, email, pw)


def test_duplicate_email_rejected(seller):
    with pytest.raises(AuthError):
        auth.register("Other", "ada@uni.edu", "password9")


def test_login_errors_do_not_reveal_which_part_failed(seller):
    with pytest.raises(AuthError) as bad_pw:
        auth.login("ada@uni.edu", "wrongpass1")
    with pytest.raises(AuthError) as no_user:
        auth.login("ghost@uni.edu", "password1")
    assert str(bad_pw.value) == str(no_user.value)


def test_campus_domain_enforced(monkeypatch):
    monkeypatch.setenv("CAMPUS_EMAIL_DOMAIN", "uni.edu")
    with pytest.raises(AuthError):
        auth.register("Z", "z@gmail.com", "password1")
    assert auth.register("Z", "z@uni.edu", "password1")


def test_sql_injection_string_is_treated_as_data(seller):
    with pytest.raises(AuthError):
        auth.login("' OR '1'='1", "x")


# ---------- brute-force throttling ----------
def test_account_locks_after_five_failures(seller):
    for _ in range(5):
        with pytest.raises(AuthError, match="Invalid"):
            auth.login("ada@uni.edu", "wrong-pass1")
    with pytest.raises(AuthError, match="Too many"):
        auth.login("ada@uni.edu", "password1")           # even the right password is refused


def test_lock_expires(seller, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auth, "_clock", lambda: now[0])
    for _ in range(5):
        with pytest.raises(AuthError):
            auth.login("ada@uni.edu", "wrong-pass1")
    now[0] += auth.LOCK_SECONDS + 1
    assert auth.login("ada@uni.edu", "password1")["id"] == seller


def test_success_resets_failure_count(seller):
    for _ in range(4):
        with pytest.raises(AuthError):
            auth.login("ada@uni.edu", "wrong-pass1")
    auth.login("ada@uni.edu", "password1")
    for _ in range(4):                                   # would lock if the counter had not reset
        with pytest.raises(AuthError, match="Invalid"):
            auth.login("ada@uni.edu", "wrong-pass1")


def test_unknown_emails_are_throttled_too():
    for _ in range(5):
        with pytest.raises(AuthError, match="Invalid"):
            auth.login("ghost@uni.edu", "x")
    with pytest.raises(AuthError, match="Too many"):
        auth.login("ghost@uni.edu", "x")
