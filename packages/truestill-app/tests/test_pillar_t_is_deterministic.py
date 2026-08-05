"""The pillar T's committed SVG must be exactly what its generator produces.

The artwork is authored as **named constants in Python**, not as path data, so the committed
`.svg` is a derived file with a source of truth one step away. That is the shape where a
constant gets edited, the SVG is never regenerated, and the two drift apart silently - the
repo then contains a logo whose stated source no longer produces it.

**This pins the CURRENT constants; it does not freeze them.** `TOP_BAR_EXTRA` is a deliberate
knob. Changing it is expected: re-run `scripts/make_pillar_t.py` and commit both the constant
and the regenerated SVG, and this test pins the new pair. What it forbids is changing one
without the other.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BRAND = ROOT / "brand"
GENERATOR = ROOT / "scripts" / "make_pillar_t.py"

OUTPUTS = ("pillar-t-geometric.svg", "pillar-t-geometric-solid.svg")


def _load_generator():
    """Import the script by path - `scripts/` is not a package and is not importable."""
    spec = importlib.util.spec_from_file_location("make_pillar_t", GENERATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_pillar_t"] = module
    spec.loader.exec_module(module)
    return module


def test_the_generator_is_in_the_repo_not_in_scratch() -> None:
    """It was untracked scratch; a `git clean` would have taken the logo's only source."""
    assert GENERATOR.is_file(), "scripts/make_pillar_t.py is missing"


@pytest.mark.parametrize("name", OUTPUTS)
def test_the_committed_svg_is_byte_identical_to_a_fresh_render(name: str) -> None:
    """Render in memory and compare bytes - nothing is written to disk at all.

    Deliberately NOT `write_pillar_t()`: that writes into `brand/`, so calling it here would make
    the test *cause* the state it asserts and pass unconditionally. `_svg()` is the same string
    the writer would have written, with no side effect.
    """
    module = _load_generator()
    committed = (BRAND / name).read_text(encoding="utf-8")

    gradient = not name.endswith("-solid.svg")
    title = "Truestill pillar T (gradient)" if gradient else "Truestill pillar T (solid)"
    fresh = module._svg(gradient=gradient, title=title)

    assert fresh == committed, (
        f"brand/{name} is not what scripts/make_pillar_t.py produces. A constant changed "
        "without the SVG being regenerated (or vice versa). Re-run the generator and commit both."
    )


def test_the_knob_is_recorded_in_the_artwork_so_a_render_is_self_describing() -> None:
    """`TOP_BAR_EXTRA` is emitted into the SVG's `<desc>`, so a stray copy can be identified."""
    module = _load_generator()
    committed = (BRAND / OUTPUTS[0]).read_text(encoding="utf-8")
    assert f"TOP_BAR_EXTRA={module.TOP_BAR_EXTRA}" in committed


def test_the_geometric_t_does_not_claim_a_font_origin() -> None:
    """It is drawn, not outlined - and it sits beside marks that ARE Libre Caslon derived.

    Asserted rather than trusted to the docstring, because the failure mode is a later editor
    copying a neighbouring file's `<desc>` block along with its licence claim.
    """
    for name in OUTPUTS:
        text = (BRAND / name).read_text(encoding="utf-8")
        lowered = text.lower()
        for claim in ("libre caslon", "ofl", "outlined from", "dejavu"):
            assert claim not in lowered, (
                f"brand/{name} claims a font origin ({claim!r}); this mark is original "
                "geometric artwork and no font licence attaches to it"
            )


def test_the_geometric_t_has_not_replaced_the_libre_caslon_one() -> None:
    """Both exist on purpose. The favicon still builds from the Libre Caslon pair.

    `scripts/build_brand_assets.py` reads `brand/pillar-t-{light,dark}.svg` for the ICO's 16
    and 24 entries. Deleting those to "tidy up" would silently change the shipped favicon,
    which is a separate decision the maintainer has not taken.
    """
    for name in ("pillar-t-light.svg", "pillar-t-dark.svg"):
        assert (BRAND / name).is_file(), (
            f"brand/{name} is gone - the favicon's 16/24 entries are generated from it"
        )
