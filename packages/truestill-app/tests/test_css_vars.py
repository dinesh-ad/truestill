"""(F40) CSS custom properties used in app.css must be declared in the theme tokens."""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static"
APP_CSS = STATIC / "app.css"
TOKENS_CSS = STATIC / "tokens.css"

_USED = re.compile(r"var\(\s*(--[a-z0-9-]+)", re.I)
_DECLARED = re.compile(r"(--[a-z0-9-]+)\s*:", re.I)


def test_app_css_custom_properties_are_declared() -> None:
    """An undeclared var() drops the property at computed-value time (transparent bg / wrong color)."""
    used = set(_USED.findall(APP_CSS.read_text(encoding="utf-8")))
    declared = set(_DECLARED.findall(TOKENS_CSS.read_text(encoding="utf-8")))
    declared |= set(_DECLARED.findall(APP_CSS.read_text(encoding="utf-8")))
    missing = sorted(used - declared)
    assert missing == [], f"undeclared CSS variables used in app.css: {missing}"
