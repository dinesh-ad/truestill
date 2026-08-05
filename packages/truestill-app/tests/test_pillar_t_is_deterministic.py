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
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BRAND = ROOT / "brand"
GENERATOR = ROOT / "scripts" / "make_pillar_t.py"

# Every variant the generator emits. Derived from the generator's own VARIANTS tuple at test
# time, so adding a variant without committing its SVG fails here rather than going unnoticed.
OUTPUTS = (
    "pillar-t-geometric.svg",
    "pillar-t-geometric-solid.svg",
    "pillar-t-geometric-noflute.svg",
    "pillar-t-geometric-noflute-solid.svg",
)


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


def test_every_variant_the_generator_emits_is_committed() -> None:
    """Adding a variant without committing its SVG must fail here, not go unnoticed."""
    module = _load_generator()
    emitted = {module.variant_name(**spec) for spec in module.VARIANTS}
    assert emitted == set(OUTPUTS), (
        f"generator emits {sorted(emitted)}, tests pin {sorted(OUTPUTS)}"
    )


@pytest.mark.parametrize("name", OUTPUTS)
def test_the_committed_svg_is_byte_identical_to_a_fresh_render(name: str) -> None:
    """Render in memory and compare BYTES - nothing is written to disk.

    Deliberately NOT `write_pillar_t()`: that writes into `brand/`, so calling it here would make
    the test *cause* the state it asserts and pass unconditionally.
    """
    module = _load_generator()
    committed = (BRAND / name).read_text(encoding="utf-8")

    gradient = not name.endswith("-solid.svg")
    flute = "noflute" not in name
    fresh = module._svg(
        gradient=gradient,
        title=module.variant_title(gradient=gradient, flute=flute),
        flute=flute,
    )

    assert fresh == committed, (
        f"brand/{name} is not what scripts/make_pillar_t.py produces. A constant changed "
        "without the SVG being regenerated (or vice versa). Re-run the generator and commit both."
    )


@pytest.mark.parametrize("name", OUTPUTS)
def test_the_flute_is_present_only_where_it_should_be(name: str) -> None:
    """The variants must actually differ in the path data, not only in their filename.

    Byte-equality above would be satisfied by four identical files. This pins that the cutout
    subpath is where the name says it is.
    """
    module = _load_generator()
    svg = (BRAND / name).read_text(encoding="utf-8")
    flute_start = f"M {module.FLUTE_L} {module.FLUTE_TOP_Y}"

    if "noflute" in name:
        assert flute_start not in svg, f"{name} still carries the flute cutout"
    else:
        assert flute_start in svg, f"{name} has lost the flute cutout"


def _main_body_path(svg: str) -> str:
    """The `d` of the main body, which is the artwork - not the document around it."""
    match = re.search(r'id="main-body".*?d="(.*?)"', svg, re.S)
    assert match is not None, "no main-body path in the SVG"
    return match.group(1)


def test_the_two_forms_are_not_the_same_artwork() -> None:
    """Anti-vacuity: the flag must change the GEOMETRY.

    Comparing whole documents does not do it - `<desc>` echoes the flag, so a no-op `flute`
    still yields two different strings. Only the path data answers the question.
    """
    module = _load_generator()
    with_flute = _main_body_path(module._svg(gradient=True, title="x", flute=True))
    without = _main_body_path(module._svg(gradient=True, title="x", flute=False))

    assert with_flute != without, "the flute flag does not change the path data"
    assert len(without) < len(with_flute), "the flute-less form should be the shorter path"
    assert f"M {module.FLUTE_L} {module.FLUTE_TOP_Y}" not in without


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


def test_there_is_exactly_one_t_in_the_repo_and_no_monogram() -> None:
    """REVERSED 2026-08-05: the geometric T now IS the mark, and the alternatives are deleted.

    This asserted that the Libre Caslon pair still existed, because the favicon was built from
    the font. `(abi)` closed that: the generator reads the geometric artwork, so a second
    letterform of the same letter is only something to confuse a later reader with.
    """
    for gone in (
        "monogram-light.svg",
        "monogram-dark.svg",
        "pillar-t-light.svg",
        "pillar-t-dark.svg",
    ):
        assert not (BRAND / gone).exists(), f"brand/{gone} is back - there is one mark"

    # The wordmark stays: `brand/PROVENANCE.md` keeps it for a possible website header, where a
    # serif at display size is a different question from a serif at 18px in a rail.
    assert (BRAND / "wordmark-dark.svg").is_file()
