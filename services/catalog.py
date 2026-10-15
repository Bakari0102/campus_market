"""Cached product search. The index is rebuilt only when the database's catalogue counter says
searchable data changed, so a search costs one tiny query instead of re-reading every product.
The index holds only ids and searchable text; the UI then loads fresh rows for just the page it
shows, so prices, stock and photos are never stale."""
import threading

from data import database
from data.repositories import ListingRepository
from services.search import SearchIndex


class Catalog:
    def __init__(self):
        self._repo = ListingRepository()
        self._index, self._key = None, None
        self._lock = threading.Lock()
        self.rebuilds = 0                       # exposed for tests and monitoring

    def invalidate(self):
        self._key = None

    def _fresh_index(self):
        key = (database.DB_PATH, self._repo.catalog_version())
        if key != self._key or self._index is None:
            with self._lock:                    # one thread rebuilds, the others wait for it
                if key != self._key or self._index is None:
                    index = SearchIndex()
                    for row in self._repo.search_documents():
                        index.add(dict(row))
                    self._index, self._key = index, key
                    self.rebuilds += 1
        return self._index

    def search(self, query, category=None, max_price=None):
        """Ranked list of product ids."""
        found = self._fresh_index().search(query, max_price=max_price, category=category)
        return [doc["id"] for doc in found]


catalog = Catalog()
