"""Benchmark the main operations on a large synthetic catalogue.
Usage: python -m scripts.benchmark [N]      (default N = 20000 products)
Numbers are only comparable on the same machine; use them to compare before/after a change."""
import os
import random
import sqlite3
import statistics
import sys
import tempfile
import time

from data import database

WORDS = ["laptop", "phone", "calculus", "physics", "textbook", "charger", "headphones", "tecno",
         "samsung", "hp", "dell", "engineering", "chemistry", "mouse", "keyboard", "power", "bank",
         "iphone", "infinix", "novel", "biology", "case", "screen", "guard", "notes", "scientific"]


def seed(n, vendors=50):
    """Bulk-insert n products with one image each (direct SQL, one transaction)."""
    rnd = random.Random(42)
    conn = sqlite3.connect(database.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    for v in range(1, vendors + 1):
        conn.execute("INSERT INTO users (id, full_name, email, password_hash, account_type) "
                     "VALUES (?,?,?,?, 'vendor')", (v, f"Vendor {v}", f"v{v}@shop.ng", "x"))
        conn.execute("INSERT INTO vendors (user_id, business_name, phone, is_verified) "
                     "VALUES (?,?,?,1)", (v, f"Shop {v}", "08031234567"))
    listings, images = [], []
    for i in range(1, n + 1):
        title = " ".join(rnd.sample(WORDS, 3))
        listings.append((i, rnd.randint(1, vendors), rnd.randint(1, 4), title, "good " + title,
                         rnd.randint(1000, 500000), rnd.choice(["new", "good"]), rnd.randint(1, 20)))
        images.append((i, f"assets/placeholder_{i % 4}.png", 1, 1))
    conn.executemany("INSERT INTO listings (id, seller_id, category_id, title, description, price, "
                     "condition, quantity) VALUES (?,?,?,?,?,?,?,?)", listings)
    conn.executemany("INSERT INTO listing_images (listing_id, url, is_primary, is_stock) "
                     "VALUES (?,?,?,?)", images)
    conn.execute("INSERT INTO users (id, full_name, email, password_hash) VALUES (9999,'Buyer','b@x.ng','x')")
    conn.commit()
    conn.close()


def timeit(fn, repeat=7):
    samples = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1000)
    return statistics.median(samples)


def main(n=20000):
    from data.repositories import ListingRepository
    from services import listing_service, order_service
    from services.search import SearchIndex

    database.DB_PATH = os.path.join(tempfile.mkdtemp(), "bench.db")
    database.init_db()
    seed(n)
    repo = ListingRepository()
    results = {}

    def search_rebuild():                      # how the UI searched before: rebuild the index every time
        index = SearchIndex()
        for row in repo.all_active():
            index.add(dict(row))
        return index.search("laptop dell")

    try:
        from services.catalog import catalog
        catalog.search("laptop dell")           # first call builds the cache (not timed)
        results["search (typical query)"] = timeit(lambda: catalog.search("laptop dell"))
        results["search (first query / cold cache)"] = timeit(lambda: (catalog.invalidate(), catalog.search("laptop dell")), 3)
    except ImportError:
        results["search (typical query)"] = timeit(search_rebuild, 3)

    results["browse first page (20)"] = timeit(lambda: repo.list_active(limit=20))
    results["browse first page, one category"] = timeit(lambda: repo.list_active(category_id=2, limit=20))
    results["category counts"] = timeit(repo.categories_with_counts)
    results["browse deep page (after id 100)"] = timeit(lambda: repo.list_active(after_id=100, limit=20))

    counter = iter(range(10 ** 6))
    results["create product (each)"] = timeit(
        lambda: listing_service.create_listing(1, "Phones", f"Item {next(counter)}", 1000, "new",
                                               image_checker=lambda u: False), 100)
    ids = iter(range(1, n))
    results["reserve + cancel (each)"] = timeit(
        lambda: order_service.advance(order_service.reserve(next(ids), 9999), "cancelled"), 100)

    with database.get_conn() as conn:
        plan = conn.execute("EXPLAIN QUERY PLAN SELECT l.*, i.url FROM listings l "
                            "LEFT JOIN listing_images i ON i.listing_id = l.id AND i.is_primary = 1 "
                            "WHERE l.status='active' AND l.category_id=2 ORDER BY l.id DESC LIMIT 20").fetchall()
    print(f"\n{n:,} products\n" + "-" * 52)
    for name, ms in results.items():
        print(f"{name:38} {ms:9.2f} ms")
    print("\nquery plan for browsing one category:")
    for row in plan:
        print("  ", row[-1])


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20000)
