"""The icon set is built from the pillar T SVG, and the small sizes drop the flute.

`(abi)`: `build_brand_assets.py` generated every icon from the Libre Caslon font, so the
geometric mark was committed and reached no output. It reads the SVG now, and needs no font.
"""

from __future__ import annotations

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
    """Importing it must not require fontTools - that is the dependency `(abi)` removed."""
    module = _load()
    assert module.icon_source(16).name.startswith("pillar-t-geometric")


@pytest.mark.parametrize(
    ("size", "flute"),
    [(16, False), (24, False), (32, False), (48, False), (64, False), (128, True), (256, True)],
)
def test_each_icon_size_takes_the_right_variant(size: int, flute: bool) -> None:
    """Hard-coded against the real ladder, so moving the threshold has to move these too.

    The flute is 12% of the stem and sub-pixel below ~61px; at 64 it is still a grey smudge and
    only reaches paper white at 128. Sizes are listed rather than derived from the constant,
    because a test that reads the constant it is checking cannot fail when the constant moves.
    """
    module = _load()
    source = module.icon_source(size)
    assert source.is_file(), f"{source} does not exist"
    assert ("noflute" in source.name) is (not flute), (
        f"{size}px takes {source.name}, which is the wrong variant"
    )


def test_the_flute_actually_reaches_the_large_icons_and_not_the_small_ones() -> None:
    """Aimed at the pixels, not the filename: the variants must really differ where drawn.

    A threshold that pointed both sizes at the same file would satisfy the mapping test above.
    """
    module = _load()
    small = module.mark_mask(module.icon_source(16), 512)
    large = module.mark_mask(module.icon_source(128), 512)

    def ink(mask: object) -> int:
        return sum(1 for value in mask.get_flattened_data() if value > 128)  # type: ignore[attr-defined]

    # The flute is a cutout, so the fluted mark has strictly less ink at the same canvas size.
    assert ink(large) < ink(small), (
        "the large icon has no less ink than the small one - the flute is not being cut"
    )


def test_the_path_flattener_rejects_a_command_it_does_not_understand() -> None:
    """Silently skipping an unknown command would produce a subtly wrong mark."""
    module = _load()
    with pytest.raises(ValueError, match="unsupported path command"):
        module.flatten_path("M 0 0 S 1 1 2 2 Z")
