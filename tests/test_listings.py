import pytest
from tests.conftest import no_network
from data.repositories import ListingRepository
from services.listing_service import ListingError, create_listing

repo = ListingRepository()


def make(seller, **kw):
    args = dict(category="Laptops", title="HP Laptop 15", price=95000,
                condition="good", image_checker=no_network)
    args.update(kw)
    return create_listing(seller, **args)


def test_create_and_fetch(seller):
    lid = make(seller)
    row = repo.get(lid)
    assert row["title"] == "HP Laptop 15"
    assert row["category"] == "Laptops"
    assert row["status"] == "active"


@pytest.mark.parametrize("kw", [
    {"title": "   "}, {"price": "abc"}, {"price": -5},
    {"condition": "broken"}, {"category": "Cars"},
])
def test_validation(seller, kw):
    with pytest.raises(ListingError):
        make(seller, **kw)


def test_seller_photo_is_primary_and_not_stock(seller):
    row = repo.get(make(seller, image_urls=["http://img/real.jpg"]))
    assert row["image_url"] == "http://img/real.jpg"
    assert row["image_is_stock"] == 0


def test_placeholder_when_no_photo(seller):
    row = repo.get(make(seller, category="Phones", title="Tecno"))
    assert row["image_url"].endswith("placeholder_phone.png")
    assert row["image_is_stock"] == 1


def test_isbn_cover_used_when_available(seller):
    row = repo.get(make(seller, category="Textbooks", title="Calculus", isbn="9780131103627",
                        image_checker=lambda url: True))
    assert "covers.openlibrary.org" in row["image_url"]
    assert row["image_is_stock"] == 1


def test_keyset_pagination_has_no_overlap(seller):
    for i in range(5):
        make(seller, title=f"Item {i}")
    page1 = repo.list_active(limit=3)
    page2 = repo.list_active(after_id=page1[-1]["id"], limit=3)
    ids = [r["id"] for r in page1] + [r["id"] for r in page2]
    assert len(ids) == 5 and len(set(ids)) == 5


def test_price_and_category_filters(seller):
    make(seller, title="Cheap", price=1000)
    make(seller, title="Pricey", price=90000)
    cat = repo.category_id("laptops")
    assert [r["title"] for r in repo.list_active(category_id=cat, max_price=5000)] == ["Cheap"]


# ---------- input hardening ----------
@pytest.mark.parametrize("isbn", ["abc", "123", "9780131103627/../../x", "978013110362?"])
def test_bad_isbn_rejected(seller, isbn):
    with pytest.raises(ListingError):
        make(seller, category="Textbooks", isbn=isbn)


def test_isbn_with_hyphens_is_normalised(seller):
    row = repo.get(make(seller, category="Textbooks", isbn="978-0-13-110362-7"))
    assert row["isbn"] == "9780131103627"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "ftp://x/y.jpg",
                                 "data:text/html;base64,AAAA", "//evil.com/x.jpg"])
def test_dangerous_photo_links_rejected(seller, url):
    with pytest.raises(ListingError):
        make(seller, image_urls=[url])


def test_upload_path_and_https_links_allowed(seller):
    make(seller, image_urls=["uploads/abc123.png"])
    make(seller, image_urls=["https://cdn.example.com/a.jpg"])


def test_category_counts_include_empty_categories(seller):
    make(seller, category="Phones", title="A")
    make(seller, category="Phones", title="B")
    counts = dict(repo.categories_with_counts())
    assert counts == {"Textbooks": 0, "Phones": 2, "Laptops": 0, "Accessories": 0}


# ---------- B2C rules ----------
def test_students_cannot_list_products(buyer):
    with pytest.raises(ListingError, match="verified businesses"):
        make(buyer)


def test_unverified_business_cannot_list(unverified_vendor):
    with pytest.raises(ListingError, match="verified businesses"):
        make(unverified_vendor)


def test_verified_business_can_list_new_stock_and_shows_seller(seller):
    row = repo.get(make(seller, condition="new", quantity=12))
    assert row["quantity"] == 12 and row["condition"] == "new"
    assert row["seller_name"] == "Ada Gadgets" and row["seller_verified"] == 1


@pytest.mark.parametrize("qty", [0, -3, "x", 10001, "2.5"])
def test_bad_stock_quantity_rejected(seller, qty):
    with pytest.raises(ListingError):
        make(seller, quantity=qty)
