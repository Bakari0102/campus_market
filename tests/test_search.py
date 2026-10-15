from services.search import SearchIndex, tokenize


def build():
    idx = SearchIndex()
    for i, (t, p, c) in enumerate([
        ("HP Laptop 15 inch", 95000, "Laptops"),
        ("Dell Laptop", 120000, "Laptops"),
        ("Laptop bag", 5000, "Accessories"),
        ("Calculus textbook", 4000, "Textbooks"),
    ], start=1):
        idx.add({"id": i, "title": t, "description": "", "price": p, "category": c})
    return idx


def test_tokenize_ignores_case_and_punctuation():
    assert tokenize("HP-Laptop, 15!") == ["hp", "laptop", "15"]


def test_and_search_requires_all_words():
    assert [d["id"] for d in build().search("hp laptop")] == [1]


def test_title_hits_rank_before_price():
    ids = [d["id"] for d in build().search("laptop")]
    assert ids == [3, 1, 2]   # all have one title hit, so cheaper comes first


def test_filters():
    idx = build()
    assert [d["id"] for d in idx.search("laptop", category="accessories")] == [3]
    assert 2 not in [d["id"] for d in idx.search("laptop", max_price=100000)]


def test_empty_and_unknown_queries():
    idx = build()
    assert idx.search("") == []
    assert idx.search("zzzz") == []
