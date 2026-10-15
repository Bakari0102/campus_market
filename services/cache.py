"""Small thread-safe cache with expiry (TTL) and a size limit (least-recently-used eviction)."""
import threading
import time
from collections import OrderedDict


class TTLCache:
    def __init__(self, ttl=300, maxsize=512, clock=time.monotonic):
        self.ttl, self.maxsize, self._clock = ttl, maxsize, clock
        self._data = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        """Returns the value, or None if missing or expired."""
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if self._clock() >= expires:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key, value, ttl=None):
        with self._lock:
            self._data[key] = (self._clock() + (self.ttl if ttl is None else ttl), value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def clear(self):
        with self._lock:
            self._data.clear()

    def __len__(self):
        return len(self._data)
