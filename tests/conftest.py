import pytest
from data import database
from services import auth_service, vendor_service


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Every test gets its own empty database file."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("CAMPUS_EMAIL_DOMAIN", raising=False)
    monkeypatch.setattr(auth_service, "SCRYPT_N", 2 ** 4)   # fast hashing for tests only
    from services import images
    images._checks.clear()
    from services.price_search import _cache
    _cache.clear()
    database.init_db()
    auth_service.reset_throttle()


def make_vendor(email="ada@uni.edu", name="Ada Gadgets", cac="RC123456", verified=True):
    uid = vendor_service.register_vendor("Ada Seller", email, "password1", name,
                                         "08031234567", cac)
    if verified:
        vendor_service.verify_vendor(uid)
    return uid


@pytest.fixture
def seller():
    """A VERIFIED business (B2C: only these can list products)."""
    return make_vendor()


@pytest.fixture
def unverified_vendor():
    return make_vendor("new@shop.ng", "New Shop", "RC999999", verified=False)


@pytest.fixture
def buyer():
    return auth_service.register("Bola Buyer", "bola@uni.edu", "password2", "MAT002")


@pytest.fixture
def buyer2():
    return auth_service.register("Chidi Buyer", "chidi@uni.edu", "password3", "MAT003")


def no_network(url):
    return False
