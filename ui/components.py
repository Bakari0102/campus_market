"""Visual components. One bold idea: the price is a highlighter-yellow tag, like a label on a
market stall. Everything else stays quiet. Colours are theme roles, so dark mode just works."""
"""Visual components for Campus Market."""
import flet as ft

from ui.theme import FONT_BOLD, FONT_REGULAR, FONT_SEMIBOLD

C = ft.Colors

FONT_FOR = {
    "body": FONT_REGULAR,
    "semibold": FONT_SEMIBOLD,
    "bold": FONT_BOLD,
}

CATEGORY_ICONS = {
    "Textbooks": ft.Icons.MENU_BOOK,
    "Phones": ft.Icons.PHONE_ANDROID,
    "Laptops": ft.Icons.LAPTOP_MAC,
    "Accessories": ft.Icons.HEADPHONES,
}

CONDITION_LABELS = {
    "new": "New",
    "like_new": "Like new",
    "good": "Good",
    "fair": "Fair",
}

BADGES = {
    "info": (C.PRIMARY_CONTAINER, C.ON_PRIMARY_CONTAINER),
    "warn": (C.ERROR_CONTAINER, C.ON_ERROR_CONTAINER),
    "neutral": (C.SURFACE_CONTAINER_HIGHEST, C.ON_SURFACE),
}

RADIUS_CARD = 16
RADIUS_FIELD = 12
RADIUS_BLOCK = 24


# ---------- Text ----------

def txt(value, size=16, style="body", color=None, **kw):
    return ft.Text(
        value,
        size=size,
        font_family=FONT_FOR[style],
        color=color,
        **kw,
    )


def muted(value, size=14, **kw):
    return txt(value, size, color=C.ON_SURFACE_VARIANT, **kw)


def heading(text, size=28):
    return ft.Semantics(
        header=True,
        content=txt(text, size, "bold"),
    )


def section_title(text):
    return ft.Semantics(
        header=True,
        content=txt(text, 20, "bold"),
    )


# ---------- Inputs and buttons ----------

def field(on_card=True, **kw):
    border = C.OUTLINE if on_card else C.ON_TERTIARY_CONTAINER
    focus = C.PRIMARY if on_card else C.SECONDARY

    return ft.TextField(
        filled=True,
        bgcolor=C.SURFACE if on_card else C.SURFACE_CONTAINER,
        border_radius=RADIUS_FIELD,
        border_color=border,
        focused_border_color=focus,
        text_size=16,
        **kw,
    )


def dropdown(**kw):
    return ft.Dropdown(
        border_radius=RADIUS_FIELD,
        border_color=C.OUTLINE,
        focused_border_color=C.PRIMARY,
        **kw,
    )


def button_style(kind="primary"):
    bg, fg = (
        (C.SECONDARY, C.ON_SECONDARY)
        if kind == "accent"
        else (C.PRIMARY, C.ON_PRIMARY)
    )

    return ft.ButtonStyle(
        bgcolor=bg,
        color=fg,
        shape=ft.RoundedRectangleBorder(radius=RADIUS_FIELD),
    )


# ---------- Small components ----------

def badge(text, kind="neutral", icon=None):
    bg, fg = BADGES[kind]

    parts = []

    if icon:
        parts.append(ft.Icon(icon, size=16, color=fg))

    parts.append(txt(text, 14, "semibold", color=fg))

    return ft.Container(
        content=ft.Row(parts, spacing=4, tight=True),
        bgcolor=bg,
        border_radius=999,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
    )


def price_tag(price, size=20):
    return ft.Container(
        content=txt(
            f"₦{price:,.0f}",
            size,
            "bold",
            color=C.ON_SECONDARY,
        ),
        bgcolor=C.SECONDARY,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=ft.BorderRadius(
            top_left=6,
            top_right=16,
            bottom_right=16,
            bottom_left=6,
        ),
    )


def brand(color=None, size=18):
    mark = ft.Container(
        content=ft.Icon(
            ft.Icons.STOREFRONT,
            size=22,
            color=C.ON_SECONDARY,
        ),
        bgcolor=C.SECONDARY,
        border_radius=10,
        padding=8,
    )

    return ft.Row(
        [
            mark,
            txt("Campus Market", size, "bold", color=color),
        ],
        spacing=10,
        tight=True,
    )


def empty_state(title, hint, icon=ft.Icons.SEARCH_OFF):
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(
                    icon,
                    size=40,
                    color=C.ON_SURFACE_VARIANT,
                ),
                txt(title, 18, "semibold"),
                muted(
                    hint,
                    15,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        padding=32,
        alignment=ft.Alignment(0, 0),
    )


def notice(text):
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.INFO_OUTLINE,
                    color=C.ON_PRIMARY_CONTAINER,
                ),
                txt(
                    text,
                    15,
                    color=C.ON_PRIMARY_CONTAINER,
                    expand=True,
                ),
            ],
            spacing=10,
        ),
        bgcolor=C.PRIMARY_CONTAINER,
        border_radius=RADIUS_FIELD,
        padding=12,
    )


def loading_row(text):
    return ft.Semantics(
        live_region=True,
        content=ft.Row(
            [
                ft.ProgressRing(
                    width=20,
                    height=20,
                    stroke_width=3,
                    semantics_label=text,
                ),
                muted(text, 15),
            ],
            spacing=10,
        ),
    )


# ---------- Product images ----------

def product_image(item, size=96):
    url = item.get("image_url") or ""

    if url.startswith("http"):
        stock = (
            " (stock image, not the actual item)"
            if item.get("image_is_stock")
            else ""
        )

        condition = CONDITION_LABELS.get(
            item["condition"],
            item["condition"],
        )

        alt = f'{item["title"]}, {condition}{stock}'

        return ft.Image(
            src=url,
            width=size,
            height=size,
            fit=ft.BoxFit.COVER,
            border_radius=12,
            semantics_label=alt,
            tooltip=item["title"],
        )

    icon = CATEGORY_ICONS.get(
        item["category"],
        ft.Icons.STOREFRONT,
    )

    return ft.Semantics(
        label=f'{item["category"]} placeholder, no photo',
        content=ft.Container(
            content=ft.Icon(
                icon,
                size=size * 0.4,
                color=C.ON_PRIMARY_CONTAINER,
            ),
            width=size,
            height=size,
            bgcolor=C.PRIMARY_CONTAINER,
            border_radius=12,
            alignment=ft.Alignment(0, 0),
        ),
    )


# ---------- Product cards ----------


def product_card(item):
    condition = CONDITION_LABELS.get(
        item["condition"],
        item["condition"],
    )

    badges = [badge(condition, "neutral")]

    if item.get("seller_verified"):
        badges.append(
            badge("Verified", "info", ft.Icons.VERIFIED)
        )

    if item["quantity"] <= 3:
        badges.append(
            badge(
                f'Only {item["quantity"]} left',
                "warn",
                ft.Icons.WARNING_AMBER,
            )
        )

    # Main product image
    image_area = ft.Container(
        content=product_image(item, size=200),
        alignment=ft.Alignment(0, 0),
        bgcolor=C.SURFACE,
        border_radius=12,
        padding=8,
    )

    # Product details without the seller name or sample-photo label
    details = ft.Column(
        [
            txt(
                item["title"],
                17,
                "semibold",
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Row(
                badges,
                wrap=True,
                spacing=6,
                run_spacing=6,
            ),
            price_tag(item["price"], size=20),
        ],
        spacing=9,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )

    return ft.Container(
        content=ft.Column(
            [
                image_area,
                details,
            ],
            spacing=12,
        ),
        bgcolor=C.SURFACE_CONTAINER,
        border=ft.Border.all(1, C.OUTLINE_VARIANT),
        border_radius=RADIUS_CARD,
        padding=14,
        data="product-card",
    )


# ---------- Online price comparison ----------

def online_price_tile(p, on_click):
    return ft.Container(
        content=ft.ListTile(
            title=txt(p["title"], 16),
            subtitle=muted(p["store"]),
            trailing=price_tag(p["price"], 16),
            on_click=on_click,
        ),
        bgcolor=C.SURFACE_CONTAINER,
        border=ft.Border.all(1, C.OUTLINE_VARIANT),
        border_radius=RADIUS_CARD,
    )


# ---------- Page structure ----------

def hero(greeting, on_logout, search_controls):
    on = C.ON_TERTIARY_CONTAINER

    return ft.Container(
        bgcolor=C.TERTIARY_CONTAINER,
        border_radius=RADIUS_BLOCK,
        padding=ft.Padding.symmetric(horizontal=30, vertical=28),
        content=ft.Column(
            [
                ft.Row(
                    [
                        brand(on, size=21),
                        ft.TextButton(
                            "Log out",
                            on_click=on_logout,
                            style=ft.ButtonStyle(color=on),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(height=8),
                txt(greeting, 16, color=on),
                ft.Semantics(
                    header=True,
                    content=txt(
                        "Your Campus. Your Marketplace.",
                        32,
                        "bold",
                        color=on,
                    ),
                ),
                txt(
                    "Discover textbooks, phones, laptops and everyday "
                    "essentials from campus businesses.",
                    16,
                    color=on,
                ),
                ft.Container(height=8),
                ft.Row(
                    search_controls,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                ),
            ],
            spacing=12,
        ),
    )

def form_card(*controls):
    return ft.Container(
        content=ft.Column(list(controls), spacing=14),
        bgcolor=C.SURFACE_CONTAINER,
        border=ft.Border.all(1, C.OUTLINE_VARIANT),
        border_radius=RADIUS_BLOCK,
        padding=24,
    )


def shell(*controls):
    return ft.Container(
        content=ft.Column(
            list(controls),
            spacing=24,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        width=1200,
        padding=ft.Padding.symmetric(horizontal=28, vertical=24),
        alignment=ft.Alignment(0, 0),
        margin=ft.Margin.symmetric(horizontal=0, vertical=0),
    )