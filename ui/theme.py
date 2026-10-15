"""Theme: colour schemes built from the contrast-tested palettes, plus the bundled font."""
import flet as ft

from ui.accessibility import DARK, LIGHT

FONT_REGULAR, FONT_SEMIBOLD, FONT_BOLD = "Hanken", "Hanken SemiBold", "Hanken Bold"
FONTS = {  # Hanken Grotesk (SIL Open Font License), bundled in assets/fonts so it works offline
    FONT_REGULAR: "fonts/HankenGrotesk-Regular.otf",
    FONT_SEMIBOLD: "fonts/HankenGrotesk-SemiBold.otf",
    FONT_BOLD: "fonts/HankenGrotesk-Bold.otf",
}


def color_scheme(p: dict) -> ft.ColorScheme:
    """Map the palette onto Flutter's colour roles. Components then use role names
    (ft.Colors.PRIMARY, SECONDARY, ...) so light and dark mode switch automatically."""
    return ft.ColorScheme(
        primary=p["primary"], on_primary=p["on_primary"],
        primary_container=p["primary_container"], on_primary_container=p["on_primary_container"],
        secondary=p["accent"], on_secondary=p["on_accent"],                       # price tag, search button
        secondary_container=p["accent"], on_secondary_container=p["on_accent"],   # selected category chip
        tertiary_container=p["hero"], on_tertiary_container=p["on_hero"],         # header block
        error=p["error"], on_error=p["on_error"],
        error_container=p["error_container"], on_error_container=p["on_error_container"],
        surface=p["bg"], on_surface=p["text"], on_surface_variant=p["muted"],
        surface_container=p["card"], surface_container_highest=p["neutral"],
        outline=p["outline"], outline_variant=p["border"],
    )


def apply_theme(page: ft.Page):
    page.fonts = FONTS
    page.theme = ft.Theme(color_scheme=color_scheme(LIGHT), font_family=FONT_REGULAR)
    page.dark_theme = ft.Theme(color_scheme=color_scheme(DARK), font_family=FONT_REGULAR)
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.bgcolor = ft.Colors.SURFACE
    page.padding = 16
    page.scroll = ft.ScrollMode.AUTO
