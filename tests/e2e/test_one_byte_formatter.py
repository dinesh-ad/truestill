"""The browser and the engine must render one byte count the same way.

`fmtBytes` in `app.js` is a mirror of `truestill_core.units.format_bytes`, the way `plural` and
`dupOrigins` are: the browser cannot import Python. A mirror with no gate is two implementations
with a shared name, so this runs both over the same table and compares.

It also catches the drift that started this: the JS copy was 1024-based and labelled its output
"GB", while the Python sites were `f"{n / 1024**3:.1f} GB"` inline. Three implementations, no
test, one visible disagreement.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page
from truestill_core.units import format_bytes

VALUES = [
    0,
    1,
    512,
    999,
    1_000,
    1_500,
    999_999,
    1_000_000,
    296_509_852,
    1_000_000_000,
    5_298_094_843,
    5_594_604_695,
    1_000_000_000_000,
]


def test_the_browser_formats_bytes_exactly_as_the_engine_does(ui: Page) -> None:
    rendered = ui.evaluate("(vals) => vals.map(v => fmtBytes(v))", VALUES)
    expected = [format_bytes(v) for v in VALUES]

    mismatched = [
        f"{value}: browser {got!r} vs engine {want!r}"
        for value, got, want in zip(VALUES, rendered, expected, strict=True)
        if got != want
    ]
    assert not mismatched, "the JS mirror has drifted:\n  " + "\n  ".join(mismatched)


def test_the_scale_really_is_decimal_in_the_browser(ui: Page) -> None:
    """Pins the convention itself, so a change of base fails here and not only in the mirror
    test - where both sides could be changed together and stay 'in agreement' while wrong."""
    assert ui.evaluate("() => fmtBytes(1000)") == "1.0 KB"
    assert ui.evaluate("() => fmtBytes(1024)") == "1.0 KB", "1024 bytes is not a kilobyte here"


@pytest.mark.parametrize("value", [-1, -5_000])
def test_a_negative_never_reaches_a_user_as_a_size(ui: Page, value: int) -> None:
    assert ui.evaluate("(v) => fmtBytes(v)", value) == format_bytes(value) == "0 B"
