"""Tests that keep the efficiency work from quietly regressing."""
import threading
import time

import pytest
from data import database
from data.database import get_conn
from data.repositories import ListingRepository, OrderRepository
from services import auth_service, images, order_service
from services.cache import TTLCache
from services.catalog import Catalog
from services.listing_service import create_listing
from services.price_search import compare_prices
from tests.conftest import no_network

repo = ListingRepository()


def product(seller, title="Tecno Spark", category="Phones", **kw):
    args = dict(price=40000, condition="new", image_checker=no_network)
    args.update(kw)
    return create_listing(seller, category, title, **args)


# ---------- indexes ----------
def plan(sql, *params):
    with get_conn() as conn:
        return " | ".join(r[-1] for r in conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall())


def test_image_join_uses_an_index_not_a_scan():
    """Regression: without this index, listing 20,000 products took ~22 seconds."""
    text = plan("SELECT l.id, i.url FROM listings l LEFT JOIN listing_images i "
                "ON i.listing_id = l.id AND i.is_primary = 1 WHERE l.status = 'active' "
                "ORDER BY l.id DESC LIMIT 20")
    assert "SCAN i" not in text and "idx_images_listing" in text, text


def test_browsing_uses_the_status_category_index():
    text = plan("SELECT id FROM listings WHERE status='active' AND category_id=? ORDER BY id DESC LIMIT 20", 2)
    assert "idx_listings_status_cat_id" in text and "TEMP B-TREE" not in text, text


def test_wal_mode_is_on_and_connections_wait_for_locks():
    with get_conn() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# ---------- catalogue version counter ----------
def test_version_changes_only_when_searchable_data_changes(seller):
    v0 = repo.catalog_version()
    lid = product(seller, quantity=5)
    v1 = repo.catalog_version()
    assert v1 > v0                                         # new product
    repo.adjust_stock(lid, -1)                             # stock 5 -> 4: not searchable data
    assert repo.catalog_version() == v1
    with get_conn() as conn:
        conn.execute("UPDATE listings SET price = 1 WHERE id = ?", (lid,))
    assert repo.catalog_version() > v1                     # price is used for search filters
    v2 = repo.catalog_version()
    repo.adjust_stock(lid, -4)                             # sells out -> disappears from search
    assert repo.catalog_version() > v2


# ---------- cached search ----------
def test_search_index_is_built_once_then_reused(seller):
    product(seller, "Tecno Spark")
    cat = Catalog()
    assert cat.search("tecno") and cat.rebuilds == 1
    for _ in range(5):
        cat.search("tecno")
    assert cat.rebuilds == 1                               # five more searches, zero rebuilds


def test_new_product_is_found_immediately(seller):
    cat = Catalog()
    assert cat.search("laptop") == []
    lid = product(seller, "HP Laptop", "Laptops")
    assert cat.search("laptop") == [lid] and cat.rebuilds == 2


def test_stock_changes_do_not_rebuild_but_selling_out_does(seller, buyer):
    lid = product(seller, "Tecno Spark", quantity=2)
    cat = Catalog()
    cat.search("tecno")
    order_service.reserve(lid, buyer, 1)                   # 2 -> 1 left, still listed
    assert cat.search("tecno") == [lid] and cat.rebuilds == 1
    order_service.reserve(lid, buyer, 1)                   # sold out
    assert cat.search("tecno") == [] and cat.rebuilds == 2


def test_cache_is_not_shared_between_databases(seller, tmp_path, monkeypatch):
    product(seller)
    cat = Catalog()
    assert cat.search("tecno")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "other.db"))
    database.init_db()
    assert cat.search("tecno") == []                       # different file, so the index was rebuilt


def test_get_many_keeps_order_and_skips_missing(seller):
    a, b, c = product(seller, "A item"), product(seller, "B item"), product(seller, "C item")
    rows = repo.get_many([c, 9999, a, b])
    assert [r["id"] for r in rows] == [c, a, b]
    assert repo.get_many([]) == []


# ---------- one transaction instead of several ----------
def test_product_and_image_are_created_together(seller):
    lid = product(seller)
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM listing_images WHERE listing_id = ? AND is_primary = 1",
                         (lid,)).fetchone()[0]
    assert n == 1


def test_failed_stock_reservation_creates_no_order(seller, buyer):
    lid = product(seller, quantity=1)
    with pytest.raises(order_service.OrderError):
        order_service.reserve(lid, buyer, 5)
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
    assert repo.get(lid)["quantity"] == 1


def test_cancel_restocks_in_the_same_transaction(seller, buyer):
    lid = product(seller, quantity=3)
    oid = order_service.reserve(lid, buyer, 2)
    order_service.advance(oid, "cancelled")
    assert repo.get(lid)["quantity"] == 3
    assert OrderRepository().get(oid)["status"] == "cancelled"


# ---------- TTL cache ----------
def test_ttl_cache_expires_and_evicts_oldest():
    now = [0.0]
    cache = TTLCache(ttl=10, maxsize=2, clock=lambda: now[0])
    cache.set("a", 1); cache.set("b", 2)
    assert cache.get("a") == 1
    cache.set("c", 3)                                      # over capacity: "b" is least recently used
    assert cache.get("b") is None and cache.get("a") == 1 and cache.get("c") == 3
    now[0] = 11
    assert cache.get("a") is None and len(cache) < 3       # expired


def test_ttl_cache_per_item_ttl():
    now = [0.0]
    cache = TTLCache(ttl=100, clock=lambda: now[0])
    cache.set("short", 1, ttl=5)
    cache.set("long", 2)
    now[0] = 6
    assert cache.get("short") is None and cache.get("long") == 2


# ---------- price comparison ----------
def slow(store, price, delay):
    def provider(query):
        time.sleep(delay)
        return [{"store": store, "title": query, "price": price, "url": "u"}]
    return provider


def test_stores_are_asked_in_parallel():
    providers = {s: slow(s, p, 0.4) for s, p in [("A", 3), ("B", 1), ("C", 2)]}
    start = time.perf_counter()
    result = compare_prices("laptop", providers, cache=TTLCache())
    elapsed = time.perf_counter() - start
    assert [p["store"] for p in result["prices"]] == ["B", "C", "A"]   # sorted by price
    assert elapsed < 0.9, f"took {elapsed:.2f}s; sequential calls would take 1.2s"


def test_slow_store_times_out_without_blocking_the_others():
    release = threading.Event()

    def hung(query):
        release.wait(5)
        return []
    providers = {"Fast": slow("Fast", 1, 0), "Hung": hung}
    start = time.perf_counter()
    result = compare_prices("x", providers, timeout=0.3, cache=TTLCache())
    elapsed = time.perf_counter() - start
    release.set()                                          # let the background thread finish
    assert [p["store"] for p in result["prices"]] == ["Fast"] and result["failed"] == ["Hung"]
    assert elapsed < 1.5


def test_broken_store_is_reported_not_raised():
    def broken(query):
        raise RuntimeError("API down")
    result = compare_prices("x", {"Ok": slow("Ok", 1, 0), "Bad": broken}, cache=TTLCache())
    assert len(result["prices"]) == 1 and result["failed"] == ["Bad"]


def test_results_are_cached_per_store_and_failures_are_not():
    calls = {"ok": 0, "bad": 0}

    def ok(q):
        calls["ok"] += 1
        return [{"store": "Ok", "title": q, "price": 1, "url": "u"}]

    def bad(q):
        calls["bad"] += 1
        raise RuntimeError

    cache = TTLCache()
    for _ in range(3):
        compare_prices("Laptop ", {"Ok": ok, "Bad": bad}, cache=cache)
    assert calls == {"ok": 1, "bad": 3}                    # good answer reused, failure retried


# ---------- cover-image lookups ----------
def test_cover_check_is_remembered(monkeypatch):
    calls = []

    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(images.urllib.request, "urlopen", lambda *a, **k: calls.append(1) or Resp())
    assert images.url_works("https://covers.example/x.jpg")
    assert images.url_works("https://covers.example/x.jpg")
    assert len(calls) == 1


def test_failed_cover_check_is_remembered_only_briefly(monkeypatch):
    def boom(*a, **k):
        raise images.urllib.error.URLError("offline")
    monkeypatch.setattr(images.urllib.request, "urlopen", boom)
    assert images.url_works("https://covers.example/y.jpg") is False
    assert images._checks.get("https://covers.example/y.jpg") is False


# ---------- password hashing ----------
def test_production_hash_cost_is_not_weakened():
    assert auth_service.DEFAULT_SCRYPT_N >= 2 ** 14       # the test suite lowers SCRYPT_N, not this


def test_hash_embeds_its_parameters(monkeypatch):
    monkeypatch.setattr(auth_service, "SCRYPT_N", auth_service.DEFAULT_SCRYPT_N)
    stored = auth_service.hash_password("password1")
    assert stored.startswith(f"scrypt${auth_service.DEFAULT_SCRYPT_N}$8$1$")


def test_old_hashes_still_verify_after_the_cost_is_raised(monkeypatch):
    stored = auth_service.hash_password("password1")      # made at the (test) low cost
    monkeypatch.setattr(auth_service, "SCRYPT_N", auth_service.SCRYPT_N * 2)
    assert auth_service.verify_password("password1", stored)
    assert not auth_service.verify_password("wrong", stored)


def test_benchmark_script_still_runs(capsys):
    from scripts import benchmark
    benchmark.main(300)
    out = capsys.readouterr().out
    assert "search (typical query)" in out and "SCAN i" not in out
