"""A path component may not end in a dot or a space, and both sanitizers must agree.

Windows and FAT drop trailing dots and spaces when a name is created, so ``Trip.`` and ``Trip``
are one directory there and two on ext4. `layout._sanitize_value` has always trimmed them and
its docstring says why; `categorize.sanitize_label` did not, because its own cap ran *after*
its trim: ``cleaned[:60].strip()`` removes whitespace but not a dot, so a 60-character cut that
landed on one kept it.

`test_filename_safety.py` pins this property for the layout sanitizer. This file pins the rule
itself -- one helper, both callers -- so the two cannot drift apart again.
"""

from __future__ import annotations

import pytest
from truestill_core.categorize import sanitize_label
from truestill_core.layout import _sanitize_value
from truestill_core.models import SAVED_LABEL, strip_component_tail

_SANITIZERS = (("sanitize_label", sanitize_label), ("_sanitize_value", _sanitize_value))


@pytest.mark.parametrize(("name", "sanitize"), _SANITIZERS)
def test_no_sanitizer_returns_a_component_ending_in_a_dot_or_space(
    name: str, sanitize: object
) -> None:
    """The rule, asserted on both implementations rather than on one."""
    assert callable(sanitize)
    for raw in ("Trip.", "Trip ", "Trip. ", "Trip .", "A" * 59 + ".b", "A" * 58 + " . tail"):
        cleaned = sanitize(raw)
        assert not cleaned.endswith((".", " ")), f"{name}({raw!r}) -> {cleaned!r}"


@pytest.mark.parametrize(("name", "sanitize"), _SANITIZERS)
def test_every_sanitizer_is_idempotent(name: str, sanitize: object) -> None:
    """``f(f(x)) == f(x)`` -- asserted as the general property, not on one lucky input.

    The counterexample that started this was a 60-character cap landing on a dot, so the
    corpus deliberately straddles both sanitizers' caps rather than testing short names.
    """
    assert callable(sanitize)
    raws = [
        "Canon EOS 5D",
        "Trip.",
        "A" * 59 + ".b",
        "A" * 58 + " . tail",
        "A" * 61,
        "x" * 300 + ".",
        "  spaced  out  ",
        'weird<>:"/\\|?*name',
    ]
    for raw in raws:
        once = sanitize(raw)
        assert sanitize(once) == once, f"{name} is not idempotent on {raw!r}: {once!r}"


def test_the_shared_helper_trims_only_the_tail() -> None:
    """Cry-wolf: dots and spaces *inside* a name are ordinary and must survive."""
    assert strip_component_tail("Mr. Smith's Trip") == "Mr. Smith's Trip"
    assert strip_component_tail("v1.2.3") == "v1.2.3"
    assert strip_component_tail("  Trip.  ") == "Trip"
    assert strip_component_tail("...") == ""


def test_an_ordinary_label_is_untouched_by_the_fix() -> None:
    """Cry-wolf for the caller: the fix must not reword names that were already fine."""
    assert sanitize_label("Canon EOS 5D Mark IV") == "Canon EOS 5D Mark IV"
    assert sanitize_label("Adobe Photoshop") == "Adobe Photoshop"
    assert sanitize_label("   ") == SAVED_LABEL


def test_a_label_whose_cap_lands_on_a_dot_loses_it() -> None:
    """The exact defect, stated as one case so a failure names it rather than a property."""
    assert sanitize_label("A" * 59 + ".b") == "A" * 59
