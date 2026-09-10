"""The icon set is built from the ONE mark - the same file the rail inlines.

`(abi)`: `build_brand_assets.py` generated every icon from the Libre Caslon font, so the
committed artwork reached no output. It reads the SVG now, and needs no font.

⚠ **RE-POINTED 2026-09-10, and what this file used to assert was the divergence itself.** It
pinned `icon_source(16).name.startswith("pillar-t-geometric")` and the flute/no-flute split -
i.e. it asserted that the icons come from a DIFFERENT mark than the rail, which is exactly the
state that shipped for weeks. The icons and the rail take `brand/truestill-mark.svg` now, and
`tests/e2e/test_one_mark_the_truestill_t.py` holds the pixels of the two together.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "scripts" / "build_brand_assets.py"

pytest.importorskip("PIL", reason="the brand generator needs pillow")


def _load():
    spec = importlib.util.spec_from_file_location("build_brand_assets", GENERATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_brand_assets"] = module
    spec.loader.exec_module(module)
    return module


def test_the_generator_needs_no_font_to_build_icons() -> None:
    """The whole point of `(abi)`: the artwork is the source, not a font."""
    module = _load()
    assert module.MARK == "truestill-mark.svg"
    assert (ROOT / "brand" / module.MARK).is_file(), "the one mark is missing from brand/"


def _code_strings() -> list[str]:
    """Every string literal in the generator that is NOT a docstring.

    ⚠ Read through `ast`, because the first version of these two tests grepped the text and both
    failed on the module docstring - which NAMES both marks, correctly, while explaining the
    change. A prose mention is not a second source; a string literal in code is.
    """
    tree = ast.parse(GENERATOR.read_text(encoding="utf-8"))
    docstrings = {
        ast.get_docstring(node, clean=False)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value not in docstrings
    ]


def test_the_generator_names_the_mark_exactly_once() -> None:
    """⚠ **A SECOND PLACE TO WRITE THE FILENAME IS A SECOND MARK WAITING TO HAPPEN.** The icons
    diverged from the rail because two surfaces each named their own source. `MARK` is the one
    name in this script, and a literal beside it would let them part again."""
    named = [text for text in _code_strings() if "truestill-mark" in text]
    assert named == ["truestill-mark.svg"], (
        f"the mark's filename appears {len(named)} times in the generator's code: {named}. "
        "It must be read from `MARK`."
    )


def test_the_retired_mark_is_no_longer_a_source() -> None:
    """The pillar T is kept in `brand/` as a record and must not be rasterised again."""
    leaked = [text for text in _code_strings() if "pillar-t" in text]
    assert not leaked, f"the generator still names the retired mark in code: {leaked}"

    tree = ast.parse(GENERATOR.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    } | {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    for gone in ("icon_source", "FLUTE_MIN_SIZE", "flatten_path", "mark_mask", "raster_pillar_t"):
        assert gone not in defined, (
            f"{gone!r} is still defined in the generator - retired machinery left inert"
        )


def test_the_shape_reader_rejects_a_path_it_does_not_understand() -> None:
    """It replaced a bezier flattener that raised on an unknown command, and it keeps that
    property: a shape silently dropped would produce a subtly wrong mark at every size."""
    module = _load()
    with pytest.raises(ValueError, match="unsupported path"):
        module._shapes(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            '<path d="M 0 0 C 1 1 2 2 3 3" stroke-width="2"/></svg>'
        )


def test_the_mark_is_read_from_the_file_rather_than_transcribed() -> None:
    """⚠ **The numbers must come from the artwork.** A transcribed copy in this script would be
    a second source that agrees until someone edits one of them - which is the defect one level
    up. Proved by feeding the reader a mark whose coordinates are nothing like the real one."""
    module = _load()
    draw, knockout = module._shapes(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect x="0" y="0" width="100" height="100" rx="22" fill="url(#r)"/>'
        '<g mask="url(#m)"><g transform="translate(10 10) scale(0.5)">'
        '<circle cx="20" cy="20" r="4" fill="#161826"/></g></g>'
        '<defs><mask id="m"><rect x="0" y="0" width="100" height="100" fill="#fff"/>'
        '<g transform="translate(10 10) scale(0.5)">'
        '<circle cx="20" cy="20" r="2" fill="#000"/></g></mask></defs></svg>'
    )
    # translate(10 10) scale(0.5) puts a r=4 circle at (20,20) on centre (20,20), radius 2.
    assert draw == [(18.0, 18.0, 22.0, 22.0, 2.0)], draw
    assert knockout == [(19.0, 19.0, 21.0, 21.0, 1.0)], knockout


def test_the_plate_is_not_drawn_as_part_of_the_mark() -> None:
    """⚠ **The first render painted the whole tile in the mark's ink** - a dark square with two
    rose eyes - because the ramp-filled plate was collected as a mark shape. The plate is
    identified by its `url(...)` fill, so a file that names its shapes differently still works."""
    module = _load()
    draw, _ = module._shapes(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect x="0" y="0" width="100" height="100" rx="22" fill="url(#ramp)"/>'
        '<rect x="10" y="10" width="20" height="20" rx="0" fill="#161826"/></svg>'
    )
    assert draw == [(10.0, 10.0, 30.0, 30.0, 0.0)], f"the plate leaked into the mark: {draw}"
