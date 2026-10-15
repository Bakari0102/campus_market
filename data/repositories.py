"""Data access layer. Only this module writes SQL; all queries are parameterized."""
from data.database import get_conn

_LISTING_SELECT = """
SELECT l.*, c.name AS category, i.url AS image_url, i.is_stock AS image_is_stock,
       v.business_name AS seller_name, v.is_verified AS seller_verified
FROM listings l
JOIN categories c ON c.id = l.category_id
LEFT JOIN listing_images i ON i.listing_id = l.id AND i.is_primary = 1
LEFT JOIN vendors v ON v.user_id = l.seller_id
"""


def _adjust_stock(conn, listing_id, delta, require_active=False):
    """Change stock in ONE statement; refuses to go below zero. True if the row was updated."""
    sql = """UPDATE listings SET quantity = quantity + ?,
                 status = CASE
                     WHEN status = 'active' AND quantity + ? <= 0 THEN 'sold_out'
                     WHEN status = 'sold_out' AND quantity + ? > 0 THEN 'active'
                     ELSE status END
             WHERE id = ? AND quantity + ? >= 0"""
    if require_active:
        sql += " AND status = 'active'"
    return conn.execute(sql, (delta, delta, delta, listing_id, delta)).rowcount == 1


class UserRepository:
    def create(self, full_name, email, matric_no, password_hash):
        with get_conn() as conn:  # raises sqlite3.IntegrityError on duplicates
            cur = conn.execute(
                "INSERT INTO users (full_name, email, matric_no, password_hash) VALUES (?,?,?,?)",
                (full_name, email, matric_no, password_hash))
            return cur.lastrowid

    def get_by_email(self, email):
        with get_conn() as conn:
            return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    def get(self, user_id):
        with get_conn() as conn:
            return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


class ListingRepository:
    def category_id(self, name):
        with get_conn() as conn:
            row = conn.execute("SELECT id FROM categories WHERE lower(name) = lower(?)",
                               (name,)).fetchone()
            return row["id"] if row else None

    def categories_with_counts(self):
        """[(name, active_listing_count)] including categories with zero listings."""
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT c.name, COUNT(l.id) AS n FROM categories c
                   LEFT JOIN listings l ON l.category_id = c.id AND l.status = 'active'
                   GROUP BY c.id ORDER BY c.id""").fetchall()
        return [(r["name"], r["n"]) for r in rows]

    def create(self, seller_id, category_id, title, description, price, condition, isbn=None,
               quantity=1):
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO listings
                   (seller_id, category_id, title, description, price, condition, isbn, quantity)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (seller_id, category_id, title, description, price, condition, isbn, quantity))
            return cur.lastrowid

    def adjust_stock(self, listing_id, delta):
        """Atomic; returns False (changing nothing) if stock would drop below zero."""
        with get_conn() as conn:
            return _adjust_stock(conn, listing_id, delta)

    def create_with_image(self, seller_id, category_id, title, description, price, condition,
                          isbn, quantity, image_url, image_is_stock):
        """Product + its primary image in ONE transaction: one disk sync instead of two, and
        never a product without an image if something fails half-way."""
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO listings
                   (seller_id, category_id, title, description, price, condition, isbn, quantity)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (seller_id, category_id, title, description, price, condition, isbn, quantity))
            conn.execute("INSERT INTO listing_images (listing_id, url, is_primary, is_stock) "
                         "VALUES (?,?,1,?)", (cur.lastrowid, image_url, int(image_is_stock)))
            return cur.lastrowid

    def add_image(self, listing_id, url, is_stock, is_primary=True):
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO listing_images (listing_id, url, is_primary, is_stock) VALUES (?,?,?,?)",
                (listing_id, url, int(is_primary), int(is_stock)))

    def get(self, listing_id):
        with get_conn() as conn:
            return conn.execute(_LISTING_SELECT + " WHERE l.id = ?", (listing_id,)).fetchone()

    def list_active(self, category_id=None, max_price=None, after_id=None, limit=20):
        """Keyset pagination: pass the last id you saw as after_id."""
        sql = _LISTING_SELECT + " WHERE l.status = 'active'"
        params = []
        if category_id is not None:
            sql += " AND l.category_id = ?"; params.append(category_id)
        if max_price is not None:
            sql += " AND l.price <= ?"; params.append(max_price)
        if after_id is not None:
            sql += " AND l.id < ?"; params.append(after_id)
        sql += " ORDER BY l.id DESC LIMIT ?"; params.append(limit)
        with get_conn() as conn:
            return conn.execute(sql, params).fetchall()

    def all_active(self):
        with get_conn() as conn:
            return conn.execute(_LISTING_SELECT + " WHERE l.status = 'active'").fetchall()

    def get_many(self, ids):
        """Fresh rows for these ids in the SAME order, with ONE query (for one page of results)."""
        ids = list(ids)
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        with get_conn() as conn:
            rows = conn.execute(_LISTING_SELECT + f" WHERE l.id IN ({marks})", ids).fetchall()
        by_id = {r["id"]: r for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def search_documents(self):
        """Only the columns the search index needs (no joins to images or vendors)."""
        with get_conn() as conn:
            return conn.execute(
                """SELECT l.id, l.title, l.description, l.price, c.name AS category
                   FROM listings l JOIN categories c ON c.id = l.category_id
                   WHERE l.status = 'active'""").fetchall()

    def catalog_version(self):
        with get_conn() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = 'catalog_version'").fetchone()
            return row["value"] if row else 0

    def update_status(self, listing_id, status):
        with get_conn() as conn:
            conn.execute("UPDATE listings SET status = ? WHERE id = ?", (status, listing_id))


class OrderRepository:
    def create(self, listing_id, buyer_id, amount, quantity=1):
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO orders (listing_id, buyer_id, amount, quantity) VALUES (?,?,?,?)",
                (listing_id, buyer_id, amount, quantity))
            return cur.lastrowid

    def get(self, order_id):
        with get_conn() as conn:
            return conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

    def reserve(self, listing_id, buyer_id, quantity):
        """Take stock AND create the order in one transaction (one disk sync, and a crash can
        never leave stock taken without an order). Returns the order id, or None if the product
        is not active or has too little stock."""
        with get_conn() as conn:
            if not _adjust_stock(conn, listing_id, -quantity, require_active=True):
                return None
            price = conn.execute("SELECT price FROM listings WHERE id = ?", (listing_id,)).fetchone()["price"]
            return conn.execute(
                "INSERT INTO orders (listing_id, buyer_id, amount, quantity) VALUES (?,?,?,?)",
                (listing_id, buyer_id, price * quantity, quantity)).lastrowid

    def set_status(self, order_id, status, restock=False):
        """Change status and (for cancel/refund) return the stock, in one transaction."""
        with get_conn() as conn:
            conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
            if restock:
                o = conn.execute("SELECT listing_id, quantity FROM orders WHERE id = ?",
                                 (order_id,)).fetchone()
                _adjust_stock(conn, o["listing_id"], o["quantity"])


class VendorRepository:
    def create_with_user(self, full_name, email, password_hash, business_name, phone, cac_number):
        """One transaction: the user and the business profile are created together or not at all."""
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO users (full_name, email, matric_no, password_hash, account_type)
                   VALUES (?, ?, NULL, ?, 'vendor')""", (full_name, email, password_hash))
            user_id = cur.lastrowid
            conn.execute(
                "INSERT INTO vendors (user_id, business_name, cac_number, phone) VALUES (?,?,?,?)",
                (user_id, business_name, cac_number, phone))
            return user_id

    def get(self, user_id):
        with get_conn() as conn:
            return conn.execute("SELECT * FROM vendors WHERE user_id = ?", (user_id,)).fetchone()

    def set_verified(self, user_id, verified=True):
        with get_conn() as conn:
            return conn.execute("UPDATE vendors SET is_verified = ? WHERE user_id = ?",
                                (int(verified), user_id)).rowcount == 1

    def list_pending(self):
        with get_conn() as conn:
            return conn.execute(
                """SELECT v.*, u.email FROM vendors v JOIN users u ON u.id = v.user_id
                   WHERE v.is_verified = 0 ORDER BY v.created_at""").fetchall()
