"""WCAG 2.2 AA checks that can be automated. Manual checks are in the README checklist."""
import os
from unittest.mock import MagicMock

import pytest

from ui.accessibility import DARK, LIGHT, contrast_ratio, meets_aa
from ui.theme import FONTS, apply_theme, color_scheme

THEMES = [("light", LIGHT), ("dark", DARK)]

# (foreground, background, required ratio, what it is)
TEXT = 4.5      # 1.4.3 Contrast (Minimum), normal text
UI = 3.0        # 1.4.11 Non-text contrast, component boundaries and graphics
PAIRS = [
    ("text", "bg", TEXT, "body text on page"),
    ("text", "card", TEXT, "body text on cards"),
    ("muted", "bg", TEXT, "secondary text on page"),
    ("muted", "card", TEXT, "secondary text on cards"),
    ("primary", "bg", TEXT, "links/outlined controls on page"),
    ("primary", "card", TEXT, "links/outlined controls on cards"),
    ("on_primary", "primary", TEXT, "button label"),
    ("on_primary_container", "primary_container", TEXT, "info badge, notice, image placeholder"),
    ("on_accent", "accent", TEXT, "price tag, search button, selected chip"),
    ("on_hero", "hero", TEXT, "header block text"),
    ("text", "neutral", TEXT, "neutral badge"),
    ("on_error_container", "error_container", TEXT, "low-stock badge"),
    ("error", "bg", TEXT, "error text on page"),
    ("error", "card", TEXT, "error text on cards"),
    ("success", "bg", TEXT, "success text on page"),
    ("success", "card", TEXT, "success text on cards"),
    ("outline", "card", UI, "input border on card"),
    ("outline", "bg", UI, "chip/input border on page"),
    ("on_hero", "hero", UI, "search field border on header"),
    ("accent", "hero", UI, "search button and keyboard focus ring against header"),
]


def test_contrast_maths_known_values():
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)


@pytest.mark.parametrize("theme_name,palette", THEMES)
@pytest.mark.parametrize("fg,bg,needed,what", PAIRS, ids=[p[3] for p in PAIRS])
def test_every_colour_pairing_meets_wcag(theme_name, palette, fg, bg, needed, what):
    ratio = contrast_ratio(palette[fg], palette[bg])
    assert ratio >= needed, f"{theme_name}: {what} is {ratio:.2f}:1, needs {needed}:1"


def test_checker_rejects_a_bad_pair():
    assert not meets_aa("#999999", "#FFFFFF")          # classic light-grey-on-white failure


def test_both_themes_define_the_same_roles():
    assert LIGHT.keys() == DARK.keys()


@pytest.mark.parametrize("p", [LIGHT, DARK])
def test_colour_scheme_builds_from_palette(p):
    cs = color_scheme(p)
    assert cs.surface == p["bg"] and cs.secondary == p["accent"] and cs.on_surface == p["text"]


def test_bundled_fonts_exist_and_are_registered():
    root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    for family, path in FONTS.items():
        assert os.path.exists(os.path.join(root, path)), f"{family}: {path} missing"
    assert os.path.exists(os.path.join(root, "fonts", "OFL.txt"))      # licence shipped with the font
    page = MagicMock()
    apply_theme(page)
    assert page.fonts == FONTS


def test_header_search_field_has_visible_focus_ring_and_border():
    import flet as ft
    from ui.components import field
    box = field(on_card=False, label="Search")
    assert box.focused_border_color == ft.Colors.SECONDARY       # yellow ring, not ink-on-ink
    assert box.border_color == ft.Colors.ON_TERTIARY_CONTAINER   # white outline on the dark header
    on_card = field(label="Email")
    assert on_card.focused_border_color == ft.Colors.PRIMARY and on_card.border_color == ft.Colors.OUTLINE
