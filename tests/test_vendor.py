import sqlite3

import pytest
from data.database import get_conn
from data.repositories import VendorRepository
from services import auth_service, vendor_service
from services.auth_service import AuthError
import manage

vendors = VendorRepository()


def register(**kw):
    args = dict(full_name="Ada", email="shop@biz.ng", password="password1",
                business_name="Ada Gadgets", phone="08031234567", cac_number="RC123456")
    args.update(kw)
    return vendor_service.register_vendor(**args)


def test_new_business_starts_unverified():
    uid = register()
    assert vendors.get(uid)["is_verified"] == 0
    assert not vendor_service.is_verified(uid)
    vendor_service.verify_vendor(uid)
    assert vendor_service.is_verified(uid)


def test_business_can_log_in_and_is_marked_vendor():
    register()
    assert auth_service.login("shop@biz.ng", "password1")["account_type"] == "vendor"


def test_students_are_not_vendors(buyer):
    assert auth_service.users.get(buyer)["account_type"] == "student"
    assert not vendor_service.is_verified(buyer)


@pytest.mark.parametrize("kw", [
    {"business_name": " "}, {"phone": "123"}, {"phone": "0803abc4567"},
    {"cac_number": "XX123"}, {"cac_number": "RC"}, {"password": "short"},
])
def test_bad_input_rejected(kw):
    with pytest.raises(AuthError):
        register(**kw)


def test_phone_and_cac_are_normalised():
    uid = register(phone="0803 123-4567", cac_number="rc 123456")
    row = vendors.get(uid)
    assert row["phone"] == "08031234567" and row["cac_number"] == "RC123456"


def test_cac_is_optional():
    assert register(cac_number="")


def test_duplicate_cac_or_email_rejected():
    register()
    with pytest.raises(AuthError):
        register(email="other@biz.ng")                # same CAC number
    with pytest.raises(AuthError):
        register(cac_number="RC777777")               # same email


def test_failed_registration_leaves_no_orphan_user():
    register()
    with pytest.raises(AuthError):
        register(email="other@biz.ng")                # fails on duplicate CAC
    assert auth_service.users.get_by_email("other@biz.ng") is None


def test_campus_domain_applies_to_students_not_businesses(monkeypatch):
    monkeypatch.setenv("CAMPUS_EMAIL_DOMAIN", "uni.edu")
    assert register(email="shop@gmail.com")           # business: any email is fine
    with pytest.raises(AuthError):
        auth_service.register("Stu", "stu@gmail.com", "password1")


def test_verify_unknown_vendor_fails():
    with pytest.raises(AuthError):
        vendor_service.verify_vendor(9999)


def test_manage_cli_lists_and_verifies(capsys):
    uid = register()
    assert manage.main(["pending-vendors"]) == 0
    assert "Ada Gadgets" in capsys.readouterr().out
    assert manage.main(["verify-vendor", "SHOP@biz.ng"]) == 0
    assert vendor_service.is_verified(uid)
    assert manage.main(["verify-vendor", "ghost@biz.ng"]) == 1
    assert manage.main([]) == 2
