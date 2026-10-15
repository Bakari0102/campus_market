import pytest
from tests.conftest import no_network
from data.repositories import ListingRepository
from services import order_service as orders
from services.listing_service import create_listing
from services.order_service import OrderError

listings = ListingRepository()


def product(seller, quantity=1):
    return create_listing(seller, "Phones", "Tecno Spark", 40000, "new",
                          quantity=quantity, image_checker=no_network)


def test_valid_transitions():
    orders.check_transition("reserved", "paid")
    orders.check_transition("meetup_set", "completed")


@pytest.mark.parametrize("a,b", [("reserved", "completed"), ("paid", "completed"),
                                 ("completed", "paid"), ("cancelled", "paid")])
def test_invalid_transitions(a, b):
    with pytest.raises(OrderError):
        orders.check_transition(a, b)


def test_reserve_takes_stock_and_prices_the_order(seller, buyer):
    pid = product(seller, quantity=5)
    oid = orders.reserve(pid, buyer, 2)
    row = listings.get(pid)
    assert row["quantity"] == 3 and row["status"] == "active"
    from data.repositories import OrderRepository
    order = OrderRepository().get(oid)
    assert order["quantity"] == 2 and order["amount"] == 80000


def test_last_unit_marks_product_sold_out(seller, buyer):
    pid = product(seller, 1)
    orders.reserve(pid, buyer)
    assert listings.get(pid)["status"] == "sold_out"
    assert listings.list_active() == []              # hidden from browsing


def test_full_happy_path_keeps_stock_deducted(seller, buyer):
    pid = product(seller, 1)
    oid = orders.reserve(pid, buyer)
    for step in ["paid", "meetup_set", "completed"]:
        orders.advance(oid, step)
    row = listings.get(pid)
    assert row["quantity"] == 0 and row["status"] == "sold_out"


@pytest.mark.parametrize("final", ["cancelled"])
def test_cancel_restores_stock_and_relists(seller, buyer, final):
    pid = product(seller, 1)
    oid = orders.reserve(pid, buyer)
    orders.advance(oid, final)
    row = listings.get(pid)
    assert row["quantity"] == 1 and row["status"] == "active"


def test_refund_restores_stock(seller, buyer):
    pid = product(seller, 2)
    oid = orders.reserve(pid, buyer, 2)
    orders.advance(oid, "paid")
    orders.advance(oid, "refunded")
    assert listings.get(pid)["quantity"] == 2


def test_cannot_oversell(seller, buyer, buyer2):
    pid = product(seller, 2)
    with pytest.raises(OrderError, match="Not enough stock"):
        orders.reserve(pid, buyer, 3)
    assert listings.get(pid)["quantity"] == 2         # failed attempt changed nothing
    orders.reserve(pid, buyer, 1)
    orders.reserve(pid, buyer2, 1)
    with pytest.raises(OrderError, match="no longer available"):
        orders.reserve(pid, buyer, 1)


def test_adjust_stock_is_atomic_and_never_negative(seller):
    pid = product(seller, 1)
    assert listings.adjust_stock(pid, -1) is True
    assert listings.adjust_stock(pid, -1) is False
    assert listings.get(pid)["quantity"] == 0


@pytest.mark.parametrize("qty", [0, -1, "abc", 1.5 * 0 - 1])
def test_bad_quantities_rejected(seller, buyer, qty):
    with pytest.raises(OrderError):
        orders.reserve(product(seller, 3), buyer, qty)


def test_business_cannot_buy_its_own_product(seller):
    with pytest.raises(OrderError):
        orders.reserve(product(seller), seller)


def test_cannot_skip_payment(seller, buyer):
    oid = orders.reserve(product(seller), buyer)
    with pytest.raises(OrderError):
        orders.advance(oid, "completed")
