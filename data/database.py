"""Data tier: connection handling and schema (SQLite for the MVP)."""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("CAMPUS_DB", "campus_market.db")
CATEGORIES = ["Textbooks", "Phones", "Laptops", "Accessories"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  matric_no TEXT UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student','admin')),
  account_type TEXT NOT NULL DEFAULT 'student' CHECK (account_type IN ('student','vendor')),
  is_verified INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS vendors (
  user_id INTEGER PRIMARY KEY REFERENCES users(id),
  business_name TEXT NOT NULL,
  cac_number TEXT UNIQUE,
  phone TEXT NOT NULL,
  is_verified INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS listings (
  id INTEGER PRIMARY KEY,
  seller_id INTEGER NOT NULL REFERENCES users(id),
  category_id INTEGER NOT NULL REFERENCES categories(id),
  title TEXT NOT NULL,
  description TEXT,
  price REAL NOT NULL CHECK (price >= 0),
  condition TEXT NOT NULL CHECK (condition IN ('new','like_new','good','fair')),
  isbn TEXT,
  quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 0),
  status TEXT NOT NULL DEFAULT 'active'
         CHECK (status IN ('pending','active','sold_out','removed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_listings_cat_price ON listings(category_id, price);
CREATE INDEX IF NOT EXISTS idx_listings_status_id ON listings(status, id);
CREATE INDEX IF NOT EXISTS idx_listings_status_cat_id ON listings(status, category_id, id);
CREATE TABLE IF NOT EXISTS listing_images (
  id INTEGER PRIMARY KEY,
  listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  is_primary INTEGER NOT NULL DEFAULT 0,
  is_stock INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY,
  listing_id INTEGER NOT NULL REFERENCES listings(id),
  buyer_id INTEGER NOT NULL REFERENCES users(id),
  quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),
  amount REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'reserved',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_images_listing ON listing_images(listing_id, is_primary);
CREATE INDEX IF NOT EXISTS idx_orders_listing ON orders(listing_id);
CREATE INDEX IF NOT EXISTS idx_orders_buyer ON orders(buyer_id);

-- A counter that changes only when SEARCHABLE data changes (title, description, price, status,
-- category). The search cache compares it to know when to rebuild: one tiny query, and it stays
-- correct even with several app processes sharing the database.
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE TRIGGER IF NOT EXISTS trg_catalog_insert AFTER INSERT ON listings
BEGIN UPDATE meta SET value = value + 1 WHERE key = 'catalog_version'; END;
CREATE TRIGGER IF NOT EXISTS trg_catalog_update AFTER UPDATE ON listings
WHEN OLD.status IS NOT NEW.status OR OLD.title IS NOT NEW.title
  OR OLD.description IS NOT NEW.description OR OLD.price IS NOT NEW.price
  OR OLD.category_id IS NOT NEW.category_id
BEGIN UPDATE meta SET value = value + 1 WHERE key = 'catalog_version'; END;
CREATE TRIGGER IF NOT EXISTS trg_catalog_delete AFTER DELETE ON listings
BEGIN UPDATE meta SET value = value + 1 WHERE key = 'catalog_version'; END;
"""


@contextmanager
def get_conn():
    """Open a connection, commit on success, roll back on error, always close."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")     # wait for a lock instead of failing at once
    conn.execute("PRAGMA synchronous = NORMAL")    # safe with WAL; fewer disk syncs per commit
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode = WAL")   # readers no longer block the writer
        conn.executescript(SCHEMA)
        conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('catalog_version', 0)")
        conn.executemany("INSERT OR IGNORE INTO categories(name) VALUES (?)",
                         [(c,) for c in CATEGORIES])
