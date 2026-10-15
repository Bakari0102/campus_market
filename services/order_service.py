"""Logic tier: B2C orders with stock control and an escrow-style state machine.
Stock is taken when an order is reserved and given back if it is cancelled or refunded."""
from data.repositories import ListingRepository, OrderRepository

ALLOWED = {
    "reserved":   {"paid", "cancelled"},
    "paid":       {"meetup_set", "refunded"},
    "meetup_set": {"completed", "disputed"},
    "disputed":   {"completed", "refunded"},
}
listings, orders = ListingRepository(), OrderRepository()


class OrderError(ValueError):
    """Raised with a user-friendly message."""


def check_transition(current, new):
    if new not in ALLOWED.get(current, set()):
        raise OrderError(f"Cannot change order from '{current}' to '{new}'.")


def reserve(listing_id, buyer_id, quantity=1):
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise OrderError("Quantity must be a whole number.")
    if quantity < 1:
        raise OrderError("Quantity must be at least 1.")
    listing = listings.get(listing_id)
    if not listing:
        raise OrderError("Product not found.")
    if listing["status"] != "active":
        raise OrderError("This product is no longer available.")
    if listing["seller_id"] == buyer_id:
        raise OrderError("You cannot buy from your own business account.")
    order_id = orders.reserve(listing_id, buyer_id, quantity)   # stock + order, atomically
    if order_id is None:
        raise OrderError("Not enough stock available.")
    return order_id


def advance(order_id, new_status):
    order = orders.get(order_id)
    if not order:
        raise OrderError("Order not found.")
    check_transition(order["status"], new_status)
    orders.set_status(order_id, new_status, restock=new_status in ("cancelled", "refunded"))
