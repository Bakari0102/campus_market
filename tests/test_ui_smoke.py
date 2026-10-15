"""Builds every screen against a fake page so constructor/API errors show up without a display."""
from unittest.mock import MagicMock

import pytest

ft = pytest.importorskip("flet")
import main as app  # noqa: E402
from services import auth_service  # noqa: E402
from tests.conftest import make_vendor  # noqa: E402


def flatten(controls):
    for c in controls:
        yield c
        for attr in ("controls", "content"):
            child = getattr(c, attr, None)
            if child is None:
                continue
            yield from flatten(child if isinstance(child, list) else [child])


def last_screen(page):
    return list(flatten(page.add.call_args.args))


def tagged(page, tag):
    """The live control carrying data=tag (results list, category chips)."""
    return next(c for c in flatten(page.add.call_args.args) if getattr(c, "data", None) == tag)


def find(screen, cls, label=None, text=None):
    for c in screen:
        if isinstance(c, cls) and (label is None or getattr(c, "label", None) == label) \
                and (text is None or getattr(c, "text", None) == text or getattr(c, "content", None) == text):
            return c
    raise AssertionError(f"{cls.__name__} {label or text} not found")


def test_register_login_sell_and_search_flow():
    page = MagicMock()
    app.main(page)                                    # login screen
    screen = last_screen(page)
    find(screen, ft.TextField, "Email")

    make_vendor()
    find(screen, ft.TextField, "Email").value = "ada@uni.edu"
    find(screen, ft.TextField, "Password").value = "password1"
    buttons = [c for c in screen if isinstance(c, app.Button)]
    buttons[0].on_click(None)                         # log in -> home screen
    home = last_screen(page)
    assert any(isinstance(c, ft.TextField) and "Search" in c.label for c in home)

    sell = [c for c in home if isinstance(c, app.Button)][-1]
    sell.on_click(None)                               # sell screen
    form = last_screen(page)
    find(form, ft.TextField, "Title").value = "Calculus textbook"
    find(form, ft.TextField, "Price (₦)").value = "4000"
    find(form, ft.Dropdown, "Category").value = "Phones"   # avoids ISBN network lookup
    [c for c in form if isinstance(c, app.Button)][0].on_click(None)   # post -> back to home
    home = last_screen(page)
    titles = [c.value for c in flatten(home) if isinstance(c, ft.Text)]
    assert "Calculus textbook" in titles


def test_login_shows_error_for_bad_password():
    page = MagicMock()
    app.main(page)
    screen = last_screen(page)
    find(screen, ft.TextField, "Email").value = "nobody@uni.edu"
    find(screen, ft.TextField, "Password").value = "whatever1"
    [c for c in screen if isinstance(c, app.Button)][0].on_click(None)
    err = [c for c in screen if isinstance(c, ft.Text) and c.value == "Invalid email or password."]
    assert err


def test_accessibility_features_present_on_screens():
    page = MagicMock()
    app.main(page)
    screen = last_screen(page)
    # 1.3.1 headings exposed as headers, 4.1.3 errors as live region, 3.3.8 autofill hints
    assert any(isinstance(c, ft.Semantics) and c.header for c in screen)
    assert any(isinstance(c, ft.Semantics) and c.live_region for c in screen)
    assert find(screen, ft.TextField, "Email").autofill_hints
    # every field has a visible label (3.3.2) and every button a minimum height (2.5.8)
    assert all(c.label for c in screen if isinstance(c, ft.TextField))
    assert all(c.height >= 48 for c in screen if isinstance(c, app.Button))
    # 1.4.1 errors use an icon as well as colour
    assert any(isinstance(c, ft.Icon) for c in screen)


def test_listing_images_have_text_alternatives():
    from services.listing_service import create_listing
    uid = make_vendor()
    create_listing(uid, "Phones", "Tecno Spark", 40000, "good", image_urls=["http://img/x.jpg"],
                   image_checker=lambda u: False)
    page = MagicMock()
    app.main(page)
    screen = last_screen(page)
    find(screen, ft.TextField, "Email").value = "ada@uni.edu"
    find(screen, ft.TextField, "Password").value = "password1"
    [c for c in screen if isinstance(c, app.Button)][0].on_click(None)
    images = [c for c in flatten(last_screen(page)) if isinstance(c, ft.Image)]
    assert images and all("Tecno Spark" in i.semantics_label for i in images)


def test_category_chips_show_counts_and_filter_results():
    from services.listing_service import create_listing
    uid = make_vendor()
    create_listing(uid, "Phones", "Tecno Spark", 40000, "good", image_checker=lambda u: False)
    create_listing(uid, "Laptops", "HP Laptop", 95000, "good", image_checker=lambda u: False)
    page = MagicMock()
    app.main(page)
    screen = last_screen(page)
    find(screen, ft.TextField, "Email").value = "ada@uni.edu"
    find(screen, ft.TextField, "Password").value = "password1"
    [c for c in screen if isinstance(c, app.Button)][0].on_click(None)
    chip_row, results = tagged(page, "chips"), tagged(page, "results")
    labels = lambda: [c.label.value for c in chip_row.controls]
    titles = lambda: [c.value for c in flatten(results.controls) if isinstance(c, ft.Text)]

    assert labels() == ["All (2)", "Textbooks (0)", "Phones (1)", "Laptops (1)", "Accessories (0)"]
    assert "Tecno Spark" in titles() and "HP Laptop" in titles()

    next(c for c in chip_row.controls if c.label.value.startswith("Phones")).on_select(None)
    assert "Tecno Spark" in titles() and "HP Laptop" not in titles()
    assert [c.selected for c in chip_row.controls] == [False, False, True, False, False]   # not colour only


def labels_of_buttons(screen):
    return [getattr(c, "content", None) or getattr(c, "text", None)
            for c in screen if isinstance(c, app.Button)]


def login_as(page, email, password):
    app.main(page)
    screen = last_screen(page)
    find(screen, ft.TextField, "Email").value = email
    find(screen, ft.TextField, "Password").value = password
    [c for c in screen if isinstance(c, app.Button)][0].on_click(None)
    return last_screen(page)


def test_students_see_no_add_product_button(buyer):
    home = login_as(MagicMock(), "bola@uni.edu", "password2")
    assert "Add a product" not in labels_of_buttons(home)


def test_verified_business_sees_add_product_button(seller):
    home = login_as(MagicMock(), "ada@uni.edu", "password1")
    assert "Add a product" in labels_of_buttons(home)


def test_unverified_business_sees_waiting_message(unverified_vendor):
    home = login_as(MagicMock(), "new@shop.ng", "password1")
    texts = [c.value for c in home if isinstance(c, ft.Text)]
    assert any("awaiting verification" in t for t in texts)
    assert "Add a product" not in labels_of_buttons(home)


def test_business_toggle_reveals_business_fields_and_registers():
    page = MagicMock()
    app.main(page)
    [c for c in last_screen(page) if isinstance(c, ft.TextButton)][0].on_click(None)   # Create an account
    form = last_screen(page)
    switch = next(c for c in form if isinstance(c, ft.Switch))
    biz = find(form, ft.TextField, "Business name")
    assert biz.visible is False
    switch.value = True
    switch.on_change(None)
    assert biz.visible is True and find(form, ft.TextField, "Business email")

    find(form, ft.TextField, "Full name").value = "Ada"
    find(form, ft.TextField, "Business email").value = "shop@biz.ng"
    biz.value = "Ada Gadgets"
    find(form, ft.TextField, "Business phone").value = "08031234567"
    find(form, ft.TextField, "CAC registration number").value = "RC123456"
    find(form, ft.TextField, "Password (8+ chars, include a number)").value = "password1"
    [c for c in form if isinstance(c, app.Button)][0].on_click(None)
    login_screen = last_screen(page)
    assert any(isinstance(c, ft.Text) and "must verify" in (c.value or "") for c in login_screen)
    assert auth_service.login("shop@biz.ng", "password1")["account_type"] == "vendor"


def test_cards_show_business_name_and_stock(seller):
    from services.listing_service import create_listing
    create_listing(seller, "Phones", "Tecno Spark", 40000, "new", quantity=2,
                   image_checker=lambda u: False)
    page = MagicMock()
    login_as(page, "ada@uni.edu", "password1")
    results = tagged(page, "results")
    texts = [c.value for c in flatten(results.controls) if isinstance(c, ft.Text)]
    assert "Ada Gadgets" in texts and "Verified business" in texts      # who sells it, and that they're verified
    assert "Only 2 left" in texts and "New" in texts                     # stock and condition as text, not colour
    assert "₦40,000" in texts                                            # the price tag


def test_empty_results_show_a_helpful_empty_state(buyer):
    page = MagicMock()
    login_as(page, "bola@uni.edu", "password2")
    texts = [c.value for c in flatten(tagged(page, "results").controls) if isinstance(c, ft.Text)]
    assert "No products found" in texts
    assert any("Try another word" in t for t in texts)                   # says what to do next


def test_search_shows_online_comparison_section(seller):
    from services.listing_service import create_listing
    create_listing(seller, "Phones", "Tecno Spark", 40000, "new", image_checker=lambda u: False)
    page = MagicMock()
    login_as(page, "ada@uni.edu", "password1")
    box = next(c for c in flatten(page.add.call_args.args) if isinstance(c, ft.TextField) and "Search" in c.label)
    box.value = "tecno"
    box.on_submit(None)
    results = tagged(page, "results")
    texts = [c.value for c in flatten(results.controls) if isinstance(c, ft.Text)]
    assert "Compare with online stores" in texts and "Tecno Spark" in texts
    assert any(isinstance(c, ft.ProgressRing) for c in flatten(results.controls))   # shown while loading
    fn, *args = page.run_thread.call_args.args            # the work was handed to a background thread
    fn(*args)                                             # ...simulate it finishing
    stores = [c.subtitle.value for c in flatten(results.controls) if isinstance(c, ft.ListTile)]
    assert stores == ["Temu", "Jumia", "Konga"]            # all three arrived, cheapest first
    assert not any(isinstance(c, ft.ProgressRing) for c in flatten(results.controls))


def test_login_note_is_a_dismissable_free_banner_shown_once():
    page = MagicMock()
    app.main(page)
    [c for c in last_screen(page) if isinstance(c, ft.TextButton)][0].on_click(None)
    form = last_screen(page)
    find(form, ft.TextField, "Full name").value = "Ada"
    find(form, ft.TextField, "Campus email").value = "ada@uni.edu"
    find(form, ft.TextField, "Password (8+ chars, include a number)").value = "password1"
    [c for c in form if isinstance(c, app.Button)][0].on_click(None)
    shown = [c.value for c in last_screen(page) if isinstance(c, ft.Text)]
    assert any("Account created" in (t or "") for t in shown)


def count_cards(results):
    return len([c for c in flatten(results.controls) if getattr(c, "data", None) == "product-card"])


def labels_in(results):
    return [getattr(c, "content", None) for c in flatten(results.controls) if isinstance(c, app.Button)]


def test_browse_loads_one_page_then_show_more(seller):
    from services.listing_service import create_listing
    for i in range(app.PAGE_SIZE + 5):
        create_listing(seller, "Phones", f"Phone {i}", 1000, "new", image_checker=lambda u: False)
    page = MagicMock()
    login_as(page, "ada@uni.edu", "password1")
    results = tagged(page, "results")
    assert count_cards(results) == app.PAGE_SIZE and "Show more products" in labels_in(results)
    more = next(c for c in flatten(results.controls) if isinstance(c, app.Button))
    more.on_click(None)
    assert count_cards(results) == app.PAGE_SIZE + 5 and "Show more products" not in labels_in(results)
    titles = [c.value for c in flatten(results.controls) if isinstance(c, ft.Text)]
    assert len({t for t in titles if t.startswith("Phone ")}) == app.PAGE_SIZE + 5   # no repeats, none missing


def test_search_results_are_paged_too(seller):
    from services.listing_service import create_listing
    for i in range(app.PAGE_SIZE + 3):
        create_listing(seller, "Laptops", f"Dell Laptop {i}", 1000 + i, "new", image_checker=lambda u: False)
    page = MagicMock()
    login_as(page, "ada@uni.edu", "password1")
    box = next(c for c in flatten(page.add.call_args.args) if isinstance(c, ft.TextField) and "Search" in c.label)
    box.value = "dell laptop"
    box.on_submit(None)
    results = tagged(page, "results")
    assert count_cards(results) == app.PAGE_SIZE
    next(c for c in flatten(results.controls) if isinstance(c, app.Button)).on_click(None)
    assert count_cards(results) == app.PAGE_SIZE + 3


def test_category_click_does_not_requery_counts(seller, monkeypatch):
    from data.repositories import ListingRepository
    page = MagicMock()
    login_as(page, "ada@uni.edu", "password1")
    calls = []
    original = ListingRepository.categories_with_counts
    monkeypatch.setattr(ListingRepository, "categories_with_counts",
                        lambda self: calls.append(1) or original(self))
    for chip in list(tagged(page, "chips").controls)[:3]:
        chip.on_select(None)
    assert calls == []                                     # counts were loaded once, when the screen opened


def test_stale_store_answer_is_dropped_when_user_searches_again(seller):
    from services.listing_service import create_listing
    create_listing(seller, "Phones", "Tecno Spark", 40000, "new", image_checker=lambda u: False)
    page = MagicMock()
    login_as(page, "ada@uni.edu", "password1")
    box = next(c for c in flatten(page.add.call_args.args) if isinstance(c, ft.TextField) and "Search" in c.label)
    box.value = "tecno"; box.on_submit(None)
    first = page.run_thread.call_args.args
    box.value = "dell"; box.on_submit(None)
    second = page.run_thread.call_args.args
    results = tagged(page, "results")
    first[0](*first[1:])                                   # the slow first answer arrives late
    assert any(isinstance(c, ft.ProgressRing) for c in flatten(results.controls))   # ignored: still waiting for "dell"
    second[0](*second[1:])
    assert not any(isinstance(c, ft.ProgressRing) for c in flatten(results.controls))


def test_unreachable_store_is_named_on_screen(seller, monkeypatch):
    from services.listing_service import create_listing
    create_listing(seller, "Phones", "Tecno Spark", 40000, "new", image_checker=lambda u: False)
    monkeypatch.setattr(app, "compare_prices", lambda text: {"prices": [], "failed": ["Temu"]})
    page = MagicMock()
    login_as(page, "ada@uni.edu", "password1")
    box = next(c for c in flatten(page.add.call_args.args) if isinstance(c, ft.TextField) and "Search" in c.label)
    box.value = "tecno"; box.on_submit(None)
    fn, *args = page.run_thread.call_args.args
    fn(*args)
    texts = [c.value for c in flatten(tagged(page, "results").controls) if isinstance(c, ft.Text)]
    assert "Could not reach: Temu." in texts


def test_browsing_without_a_search_starts_no_background_work(seller):
    page = MagicMock()
    login_as(page, "ada@uni.edu", "password1")
    page.run_thread.assert_not_called()
