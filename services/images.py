"""Image matching: seller photo -> Open Library cover (ISBN) -> category placeholder."""
import urllib.error
import urllib.request

from services.cache import TTLCache

PLACEHOLDERS = {
    "textbooks": "assets/placeholder_book.png",
    "phones": "assets/placeholder_phone.png",
    "laptops": "assets/placeholder_laptop.png",
    "accessories": "assets/placeholder_accessory.png",
}


_checks = TTLCache(ttl=3600, maxsize=2048)


def url_works(url: str, timeout: float = 2) -> bool:
    """HEAD request, remembered: many shops list the same textbook, so the cover is checked once
    an hour, not on every listing. Failures are remembered only briefly (network blips)."""
    cached = _checks.get(url)
    if cached is not None:
        return cached
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ok = r.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        ok = False
    _checks.set(url, ok, ttl=3600 if ok else 300)
    return ok


def resolve_image(category, isbn, seller_images, checker=url_works):
    """Return {'url': str, 'is_stock': bool}. `checker` is injectable so tests need no network."""
    if seller_images:
        return {"url": seller_images[0], "is_stock": False}
    if isbn:
        cover = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false"
        if checker(cover):
            return {"url": cover, "is_stock": True}
    return {"url": PLACEHOLDERS.get(category.lower(), "assets/placeholder.png"), "is_stock": True}
