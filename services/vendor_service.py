"""Logic tier: business (vendor) accounts for the B2C marketplace."""
import re
import sqlite3

from data.repositories import VendorRepository
from services import auth_service
from services.auth_service import AuthError, hash_password

vendors = VendorRepository()
PHONE_RE = re.compile(r"^(\+234|0)\d{10}$")          # e.g. 08031234567 or +2348031234567
CAC_RE = re.compile(r"^(RC|BN|IT)\d{3,9}$")          # format check only; an admin verifies the real record


def register_vendor(full_name, email, password, business_name, phone, cac_number=None):
    """Creates an UNVERIFIED business account. It cannot list products until verify_vendor()."""
    business_name = (business_name or "").strip()
    if len(business_name) < 2:
        raise AuthError("Please enter your business name.")
    phone = re.sub(r"[\s-]", "", phone or "")
    if not PHONE_RE.match(phone):
        raise AuthError("Enter a valid Nigerian phone number, e.g. 08031234567.")
    cac = re.sub(r"[\s-]", "", cac_number or "").upper() or None
    if cac and not CAC_RE.match(cac):
        raise AuthError("CAC number should look like RC123456 or BN1234567.")
    full_name, email = auth_service.validate_new_account(full_name, email, password,
                                                         enforce_domain=False)
    try:
        return vendors.create_with_user(full_name, email, hash_password(password),
                                        business_name, phone, cac)
    except sqlite3.IntegrityError:
        raise AuthError("An account with that email or CAC number already exists.")


def verify_vendor(user_id):
    if not vendors.set_verified(user_id, True):
        raise AuthError("Business account not found.")


def is_verified(user_id):
    vendor = vendors.get(user_id)
    return bool(vendor and vendor["is_verified"])
