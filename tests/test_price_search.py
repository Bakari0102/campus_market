from services.price_search import fetch_prices, store_links


def test_query_is_url_encoded():
    assert "hp+laptop+15" in store_links("hp laptop 15")["Jumia"]


def test_special_characters_are_escaped():
    assert "&" not in store_links("a&b=c")["Konga"].split("search=")[1]


def test_all_stores_present():
    assert set(store_links("x")) == {"Jumia", "Konga", "Temu"}


def test_prices_sorted_ascending():
    prices = [r["price"] for r in fetch_prices("laptop")]
    assert prices == sorted(prices)
