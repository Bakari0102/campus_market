"""WCAG 2.2 helpers: palette, contrast maths, and size constants (target: Level AA)."""

# Every colour pairing the UI uses is checked in tests/test_accessibility.py.
LIGHT = {
    "bg": "#F4F6FB", "card": "#FFFFFF", "text": "#111827", "muted": "#4B5563",
    "border": "#D5DAE8", "outline": "#6B7280",
    "primary": "#1B2D6B", "on_primary": "#FFFFFF",
    "primary_container": "#DCE4FB", "on_primary_container": "#14275B",
    "accent": "#FFE45C", "on_accent": "#14275B",          # the highlighter-yellow price tag
    "hero": "#14275B", "on_hero": "#FFFFFF",
    "success": "#166534", "error": "#B91C1C", "on_error": "#FFFFFF",
    "error_container": "#FEE2E2", "on_error_container": "#7F1D1D",
    "neutral": "#E5E9F2",
}
DARK = {
    "bg": "#0E1526", "card": "#17223B", "text": "#EEF2FF", "muted": "#AAB4CE",
    "border": "#2B3A5E", "outline": "#8A97B8",
    "primary": "#A9BCFF", "on_primary": "#0E1A3D",
    "primary_container": "#2A3C7A", "on_primary_container": "#DCE4FB",
    "accent": "#FFE45C", "on_accent": "#14275B",
    "hero": "#1C2C66", "on_hero": "#FFFFFF",
    "success": "#86EFAC", "error": "#FCA5A5", "on_error": "#450A0A",
    "error_container": "#7F1D1D", "on_error_container": "#FEE2E2",
    "neutral": "#26345A",
}

BODY_SIZE = 16          # readable default; text must also scale with the OS setting
SECONDARY_SIZE = 14
TITLE_SIZE = 24
BUTTON_HEIGHT = 48      # WCAG 2.5.8 only needs 24px; 48px follows mobile best practice


def _channel(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def meets_aa(fg: str, bg: str, large_text: bool = False) -> bool:
    """1.4.3 needs 4.5:1 for normal text and 3:1 for large text (and 1.4.11: 3:1 for UI parts)."""
    return contrast_ratio(fg, bg) >= (3.0 if large_text else 4.5)
