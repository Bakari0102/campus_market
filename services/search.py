"""Logic tier: inverted-index search (query cost depends on matches, not total listings)."""
import re
from collections import defaultdict


def tokenize(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


class SearchIndex:
    def __init__(self):
        self.index = defaultdict(set)   # token -> {listing ids}
        self.docs = {}                  # id -> (listing dict, title tokens)

    def add(self, listing):
        title_tokens = set(tokenize(listing["title"]))
        self.docs[listing["id"]] = (listing, title_tokens)
        for tok in title_tokens | set(tokenize(listing.get("description"))):
            self.index[tok].add(listing["id"])

    def search(self, query, max_price=None, category=None):
        tokens = tokenize(query)
        if not tokens:
            return []
        postings = sorted((self.index.get(t, set()) for t in tokens), key=len)
        ids = set.intersection(*postings)          # AND search
        results = []
        for i in ids:
            doc, title_tokens = self.docs[i]
            if max_price is not None and doc["price"] > max_price:
                continue
            if category and doc["category"].lower() != category.lower():
                continue
            title_hits = sum(t in title_tokens for t in tokens)
            results.append((title_hits, -doc["price"], doc))
        results.sort(key=lambda r: (r[0], r[1]), reverse=True)  # relevance, then cheaper
        return [r[2] for r in results]
