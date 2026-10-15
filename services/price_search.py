"""Store-search adapters. Tier 1 = deep links (safe); fetch_prices is a mock for Tier 2."""
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, wait

from services.cache import TTLCache

STORES = {
    "Jumia": "https://www.jumia.com.ng/catalog/?q={q}",
    "Konga": "https://www.konga.com/search?search={q}",
    "Temu":  "https://www.temu.com/search_result.html?search_key={q}",
}


def store_links(query):
    q = urllib.parse.quote_plus(query)
    return {name: url.format(q=q) for name, url in STORES.items()}


def fetch_prices(query):
    """MOCK data for the demo. Replace with a licensed API/affiliate feed in production."""
    links = store_links(query)
    mock = [("Jumia", 185000), ("Konga", 192500), ("Temu", 168000)]
    return sorted(({"store": s, "title": f"{query} (new)", "price": p, "url": links[s]}
                   for s, p in mock), key=lambda x: x["price"])


# ---------- comparison across stores: parallel, time-limited, cached ----------
def _mock_provider(store, price):
    def provider(query):
        return [{"store": store, "title": f"{query} (new)", "price": price,
                 "url": store_links(query)[store]}]
    return provider


PROVIDERS = {"Jumia": _mock_provider("Jumia", 185000), "Konga": _mock_provider("Konga", 192500),
             "Temu": _mock_provider("Temu", 168000)}      # replace with real API/feed adapters
_cache = TTLCache(ttl=300, maxsize=256)


def compare_prices(query, providers=None, timeout=3.0, cache=_cache):
    """Ask every store AT THE SAME TIME (total wait = the slowest store, not the sum), give up on
    stores slower than `timeout`, and cache each store's answer for 5 minutes.
    Returns {"prices": [... sorted cheapest first], "failed": [store names]}."""
    providers = providers or PROVIDERS
    key = query.strip().lower()
    prices, failed, to_fetch = [], [], {}
    for store, fn in providers.items():
        hit = cache.get((store, key))
        if hit is not None:
            prices.extend(hit)
        else:
            to_fetch[store] = fn
    if to_fetch:
        pool = ThreadPoolExecutor(max_workers=len(to_fetch))
        futures = {pool.submit(fn, query): store for store, fn in to_fetch.items()}
        done, not_done = wait(futures, timeout=timeout)
        for f in done:
            try:
                items = f.result()
            except Exception:                           # one broken store must not break the page
                failed.append(futures[f])
                continue
            cache.set((futures[f], key), items)         # only successes are cached
            prices.extend(items)
        for f in not_done:
            failed.append(futures[f])
            f.cancel()
        pool.shutdown(wait=False, cancel_futures=True)  # do not wait for a hung store
    prices.sort(key=lambda p: p["price"])
    return {"prices": prices, "failed": sorted(failed)}
