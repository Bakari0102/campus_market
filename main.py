"""Presentation tier: Flet UI. Run with `python main.py` (desktop) or `flet run --web main.py`."""
import inspect
import os

import flet as ft

from data.database import init_db
from data.repositories import ListingRepository, VendorRepository
from services import auth_service, listing_service, vendor_service
from services.auth_service import AuthError
from services.listing_service import ListingError
from services.catalog import catalog
from services.price_search import compare_prices
from ui.accessibility import BUTTON_HEIGHT, SECONDARY_SIZE
from ui.components import (badge, brand, button_style, dropdown, empty_state, field, form_card,
                           heading, hero, muted, notice, online_price_tile, product_card,
                           section_title, shell, txt, loading_row)
from ui.theme import apply_theme

listings = ListingRepository()
vendors = VendorRepository()
# Flet renamed ElevatedButton -> Button in 1.0; support both.
Button = getattr(ft, "Button", None) or ft.ElevatedButton
PAGE_SIZE = 20          # products drawn per screen; "Show more" loads the next page
CATEGORIES = ["Textbooks", "Phones", "Laptops", "Accessories"]
CONDITIONS = [("new", "New"), ("like_new", "Like new"), ("good", "Good"), ("fair", "Fair")]


def main(page: ft.Page):
    init_db()
    page.title = "Campus Market"
    apply_theme(page)     # contrast-tested light/dark palettes + bundled font (WCAG 1.4.3 / 1.4.11)
    page.show_semantics_debugger = os.environ.get("FLET_A11Y_DEBUG") == "1"
    state = {"user": None}

    async def open_url(url):
        result = page.launch_url(url)      # async in Flet 1.0, sync in older versions
        if inspect.isawaitable(result):
            await result

    def make_error():
        """Icon + text (never colour alone, WCAG 1.4.1), announced as a live region (4.1.3)."""
        text = txt("", 15, color=ft.Colors.ERROR)
        row = ft.Row([ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.ERROR), text], visible=False)

        def show(message):
            text.value = message
            row.visible = True
            page.update()
        return ft.Semantics(live_region=True, content=row), show

    def action(label, on_click, kind="primary"):
        return Button(label, on_click=on_click, height=BUTTON_HEIGHT, style=button_style(kind))

    # ---------- Login / Register ----------
    def login_view(e=None):
        page.clean()
        email = field(label="Email", autofocus=True, autofill_hints=[ft.AutofillHint.EMAIL])
        password = field(label="Password", password=True, can_reveal_password=True,
                         autofill_hints=[ft.AutofillHint.PASSWORD])
        err, show_err = make_error()
        message = state.pop("note", "")

        def do_login(_):
            try:
                state["user"] = auth_service.login(email.value, password.value)
                home_view()
            except AuthError as ex:
                show_err(str(ex))

        page.add(shell(
            ft.Container(brand(), padding=ft.Padding.only(top=8, bottom=4)),
            heading("Log in"),
            muted("Buy textbooks and gadgets from verified campus businesses.", 16),
            *([notice(message)] if message else []),
            form_card(email, password, err, action("Log in", do_login)),
            ft.TextButton("Create an account", on_click=register_view)))

    def register_view(e=None):
        page.clean()
        is_business = ft.Switch(label="I am a business selling on Campus Market")
        name = field(label="Full name", helper="Required")
        email = field(label="Campus email", helper="Required", autofill_hints=[ft.AutofillHint.EMAIL])
        matric = field(label="Matric number (optional)")
        biz_name = field(label="Business name", helper="Required", visible=False)
        phone = field(label="Business phone", helper="e.g. 08031234567", visible=False,
                      keyboard_type=ft.KeyboardType.PHONE)
        cac = field(label="CAC registration number", helper="e.g. RC123456 (checked by an admin)",
                    visible=False)
        password = field(label="Password (8+ chars, include a number)", password=True,
                         can_reveal_password=True, autofill_hints=[ft.AutofillHint.NEW_PASSWORD])
        err, show_err = make_error()

        def toggle(_):
            on = bool(is_business.value)
            for f in (biz_name, phone, cac):
                f.visible = on
            matric.visible = not on
            email.label = "Business email" if on else "Campus email"
            page.update()

        is_business.on_change = toggle

        def do_register(_):
            try:
                if is_business.value:
                    vendor_service.register_vendor(name.value, email.value, password.value,
                                                   biz_name.value, phone.value, cac.value)
                    state["note"] = ("Business account created. An admin must verify it before you "
                                     "can list products. You can log in now.")
                else:
                    auth_service.register(name.value, email.value, password.value, matric.value)
                    state["note"] = "Account created. Log in to start shopping."
                login_view()
            except AuthError as ex:
                show_err(str(ex))

        page.add(shell(
            ft.Container(brand(), padding=ft.Padding.only(top=8, bottom=4)),
            heading("Create your account"),
            form_card(is_business, name, email, matric, biz_name, phone, cac, password, err,
                      action("Create account", do_register)),
            ft.TextButton("Back to log in", on_click=login_view)))

    # ---------- Home / Search ----------
    def home_view(e=None):
        page.clean()
        query = field(on_card=False, label="Search textbooks, phones, laptops...", expand=True,
                      prefix_icon=ft.Icons.SEARCH)
        counts = listings.categories_with_counts()     # one query per visit; chips reuse it
        selected = {"cat": None}                       # None = All
        view = {"mode": "browse", "cid": None, "after_id": None, "ids": [], "shown": 0}
        chips = ft.Row(wrap=True, spacing=8, run_spacing=8, data="chips")
        list_col, more_slot, compare_col = ft.Column(spacing=12), ft.Column(), ft.Column(spacing=12)
        results = ft.Column([list_col, more_slot, compare_col], spacing=12, data="results")

        def fetch_page():
            """Next page of products. Browsing uses keyset paging; searching slices the ranked ids
            and loads fresh rows for just that slice (one query)."""
            if view["mode"] == "search":
                ids = view["ids"][view["shown"]:view["shown"] + PAGE_SIZE]
                view["shown"] += len(ids)
                return listings.get_many(ids), view["shown"] < len(view["ids"])
            rows = listings.list_active(category_id=view["cid"], after_id=view["after_id"],
                                        limit=PAGE_SIZE + 1)         # one extra row = "is there more?"
            more = len(rows) > PAGE_SIZE
            rows = rows[:PAGE_SIZE]
            if rows:
                view["after_id"] = rows[-1]["id"]
            return rows, more

        def set_more(has_more):
            more_slot.controls.clear()
            if has_more:
                more_slot.controls.append(action("Show more products", load_more))

        def load_more(_=None):
            rows, has_more = fetch_page()
            list_col.controls.extend(product_card(dict(r)) for r in rows)
            set_more(has_more)
            page.update()

        compare_state = {"n": 0}                       # which search the comparison belongs to

        def comparison_controls(result):
            items = [section_title("Compare with online stores"),
                     muted("Sample prices for demonstration.")]
            items.extend(online_price_tile(p, lambda ev, u=p["url"]: page.run_task(open_url, u))
                         for p in result["prices"])
            if result["failed"]:
                items.append(muted("Could not reach: " + ", ".join(result["failed"]) + "."))
            return items

        def load_comparison(text, token):
            """Runs OFF the screen's thread, so slow stores never freeze the app."""
            result = compare_prices(text)
            if token != compare_state["n"]:            # the user searched again meanwhile: drop it
                return
            compare_col.controls[:] = comparison_controls(result)
            page.update()

        
        def do_search(_=None):
            text = (query.value or "").strip()
            cat = selected["cat"]
            list_col.controls[:] = [
                section_title("Products from campus businesses")
            ]
            compare_col.controls.clear()
            compare_state["n"] += 1
            view.update(after_id=None, shown=0)

            if text:
                view.update(
                    mode="search",
                    ids=catalog.search(text, category=cat)
                )
            else:
                view.update(
                    mode="browse",
                    cid=listings.category_id(cat) if cat else None
                )

            rows, has_more = fetch_page()

            if rows:
                list_col.controls.extend(
                    product_card(dict(r)) for r in rows
                )

            elif not text and not cat:
                demo_products = [
                    {
                        "title": "MacBook Laptop",
                        "category": "Laptops",
                        "price": 900000,
                        "condition": "good",
                        "quantity": 2,
                        "seller_name": "Demo Campus Store",
                        "seller_verified": False,
                        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500",
                        "image_is_stock": True,
                    },
                    {
                        "title": "Smartphone",
                        "category": "Phones",
                        "price": 600000,
                        "condition": "good",
                        "quantity": 3,
                        "seller_name": "Demo Campus Store",
                        "seller_verified": False,
                        "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500",
                        "image_is_stock": True,
                    },
                    {
                        "title": "University Textbooks",
                        "category": "Textbooks",
                        "price": 8500,
                        "condition": "good",
                        "quantity": 5,
                        "seller_name": "Demo Campus Store",
                        "seller_verified": False,
                        "image_url": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=500",
                        "image_is_stock": True,
                    },
                    {
                        "title": "Wireless Headphones",
                        "category": "Accessories",
                        "price": 18000,
                        "condition": "like_new",
                        "quantity": 4,
                        "seller_name": "Demo Campus Store",
                        "seller_verified": False,
                        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500",
                        "image_is_stock": True,
                    },
                ]

                list_col.controls.extend(
                    product_card(product) for product in demo_products
                )

            else:
                list_col.controls.append(
                    empty_state(
                        "No products found",
                        "Try another word or pick a different category."
                    )
                )

            set_more(has_more)

            if text:
                compare_col.controls[:] = [
                    section_title("Compare with online stores"),
                    loading_row("Checking online stores...")
                ]
                page.run_thread(
                    load_comparison,
                    text,
                    compare_state["n"]
                )

            page.update()

        def build_chips():
            options = [("All", sum(n for _, n in counts))] + counts
            chips.controls.clear()
            for name, n in options:
                is_on = selected["cat"] == (None if name == "All" else name)
                chips.controls.append(ft.Chip(label=txt(f"{name} ({n})", 15, "semibold"),
                                              selected=is_on,
                                              on_select=lambda ev, c=name: pick(c)))

        def pick(name):
            selected["cat"] = None if name == "All" else name
            build_chips()
            do_search()

        query.on_submit = do_search
        user = state["user"]
        extra = []
        if user["account_type"] == "vendor":
            profile = vendors.get(user["id"])
            if profile and profile["is_verified"]:
                extra.append(action("Add a product", sell_view, "primary"))
            else:
                extra.append(notice("Your business is awaiting verification. "
                                    "You can't list products yet."))
        first_name = user["full_name"].split()[0]
        page.add(shell(
            hero(f"Hi, {first_name}", lambda _: (state.update(user=None), login_view()),
                 [query, action("Search", do_search, "accent")]),
            *extra,
            section_title("Browse by category"),
            chips,
            results))
        build_chips()
        do_search()

    # ---------- Add product (businesses) ----------
    def sell_view(e=None):
        page.clean()
        category = dropdown(label="Category", value="Textbooks",
                            options=[ft.dropdown.Option(c) for c in CATEGORIES])
        condition = dropdown(label="Condition", value="new",
                             options=[ft.dropdown.Option(k, t) for k, t in CONDITIONS])
        title = field(label="Title", helper="Required")
        price = field(label="Price (₦)", helper="Required, numbers only",
                      keyboard_type=ft.KeyboardType.NUMBER)
        quantity = field(label="Quantity in stock", value="1", helper="Whole number",
                         keyboard_type=ft.KeyboardType.NUMBER)
        isbn = field(label="ISBN (textbooks only, optional)")
        desc = field(label="Description", multiline=True, min_lines=2)
        photo = field(label="Photo URL (optional)")
        err, show_err = make_error()

        def submit(_):
            try:
                listing_service.create_listing(
                    state["user"]["id"], category.value, title.value, price.value, condition.value,
                    desc.value, isbn.value, [photo.value.strip()] if photo.value.strip() else [],
                    quantity=quantity.value)
                home_view()
            except ListingError as ex:
                show_err(str(ex))

        page.add(shell(
            heading("Add a product"),
            form_card(category, title, price, quantity, condition, isbn, desc, photo, err,
                      action("Publish product", submit)),
            ft.TextButton("Cancel", on_click=home_view)))

    login_view()


if __name__ == "__main__":
    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    if hasattr(ft, "run"):
        ft.run(main, assets_dir=assets)
    else:
        ft.app(target=main, assets_dir=assets)
