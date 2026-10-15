"""Logic tier: validation and creation of listings."""
import re
from urllib.parse import urlparse

from data.repositories import ListingRepository, VendorRepository
from services.images import resolve_image, url_works

CONDITIONS = {"new", "like_new", "good", "fair"}
repo = ListingRepository()
vendors = VendorRepository()
ISBN_RE = re.compile(r"^(\d{9}[\dX]|\d{13})$")


def _clean_isbn(isbn):
    value = (isbn or "").replace("-", "").replace(" ", "").upper()
    if value and not ISBN_RE.match(value):
        raise ListingError("ISBN must be 10 or 13 digits.")
    return value


def _check_image_urls(urls):
    for u in urls:
        parsed = urlparse(u)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            continue
        if not parsed.scheme and u.startswith("uploads/"):
            continue                          # file saved by process_upload
        raise ListingError("Photo link must start with http:// or https://")


class ListingError(ValueError):
    """Raised with a user-friendly message."""


def create_listing(seller_id, category, title, price, condition, description="",
                   isbn=None, image_urls=None, image_checker=url_works, quantity=1):
    # B2C rule: only verified businesses may list products; students are buyers.
    vendor = vendors.get(seller_id)
    if not vendor or not vendor["is_verified"]:
        raise ListingError("Only verified businesses can list products.")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ListingError("Quantity must be a whole number.")
    if not 1 <= quantity <= 10000:
        raise ListingError("Quantity must be between 1 and 10,000.")
    title = (title or "").strip()
    if not title:
        raise ListingError("Title is required.")
    try:
        price = float(price)
    except (TypeError, ValueError):
        raise ListingError("Price must be a number.")
    if price < 0:
        raise ListingError("Price cannot be negative.")
    if condition not in CONDITIONS:
        raise ListingError("Choose a valid condition.")
    category_id = repo.category_id(category)
    if category_id is None:
        raise ListingError("Choose a valid category.")

    isbn = _clean_isbn(isbn)
    _check_image_urls(image_urls or [])
    image = resolve_image(category, isbn, image_urls or [], image_checker)   # network, before any DB write
    return repo.create_with_image(seller_id, category_id, title, (description or "").strip(), price,
                                  condition, isbn or None, quantity, image["url"], image["is_stock"])
