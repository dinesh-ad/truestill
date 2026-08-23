"""The golden-corpus differential summarizes before it itemizes. `(P29)` tooling.

⚠ **The snapshot itself is NOT CI coverage and cannot be** - the corpus is one real machine's
`/data/TruestillLibrary/Input`, so `tests/golden/input-dates.tsv` is evidence a human
regenerates on demand (`tests/golden/README.md` states the limit). What CI can and does own
is the differential logic: that a rule change moving thousands of files reads as one counted
line per transition, never as thousands of printed paths.

Imported by path, the `test_pillar_t_is_deterministic` pattern - `scripts/` is not a package.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def _tool() -> Any:
    spec = importlib.util.spec_from_file_location(
        "golden_corpus", ROOT / "scripts" / "golden_corpus.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["golden_corpus"] = module
    spec.loader.exec_module(module)
    return module


gc = _tool()


def _row(relative: str, date: str = "2020-01-01T00:00:00", source: str = "exif") -> Any:
    return gc.Row(
        relative=relative, date=date, source=source, tag="CreateDate", target=f"S/{relative}"
    )


def test_render_and_parse_round_trip(tmp_path: Path) -> None:
    """A snapshot survives its own format: every body row comes back exactly."""
    rows = [_row("a/x.jpg"), _row("b/y.jpg", source="none", date="-")]
    text = gc.render(rows, tmp_path)
    assert gc.parse_snapshot(text) == {r.relative: r for r in rows}
    assert f"# files: {len(rows)}" in text
    assert "# filesystem:" in text, "a measurement must state its medium"
    assert "not CI coverage" in text, "the limit travels with the fixture"


def test_identical_rows_are_clean() -> None:
    old = {r.relative: r for r in [_row("a.jpg"), _row("b.jpg")]}
    drift = gc.diff_rows(old, dict(old))
    assert drift.clean
    assert "clean" in gc.format_drift(drift)


def test_a_source_transition_is_one_counted_line_not_a_wall() -> None:
    """The Q162 contract: N files moving source A -> B read as one bucket with a count."""
    old = {f"f{i}.jpg": _row(f"f{i}.jpg", source="exif") for i in range(40)}
    new = {k: gc.Row(k, v.date, "filename", v.tag, v.target) for k, v in old.items()}

    drift = gc.diff_rows(old, new)
    out = gc.format_drift(drift)

    assert drift.source_moves[("exif", "filename")] == sorted(old)
    assert "source exif -> filename: 40 files" in out
    assert out.count("f") < 40 * 3, "the wall of text is the failure the summary exists to stop"
    assert f"and {40 - gc.EXAMPLE_CAP} more not shown" in out, "elision must be announced"


def test_date_and_target_drift_are_separate_buckets() -> None:
    """Same source but a moved date is a different finding from a moved placement."""
    old = {"a.jpg": _row("a.jpg"), "b.jpg": _row("b.jpg")}
    new = {
        "a.jpg": gc.Row("a.jpg", "2021-05-05T00:00:00", "exif", "CreateDate", "S/a.jpg"),
        "b.jpg": gc.Row("b.jpg", old["b.jpg"].date, "exif", "CreateDate", "Elsewhere/b.jpg"),
    }

    drift = gc.diff_rows(old, new)

    assert drift.date_only == ["a.jpg"]
    assert drift.target_only == ["b.jpg"]
    assert not drift.source_moves


def test_added_and_removed_files_are_named() -> None:
    old = {"gone.jpg": _row("gone.jpg"), "stays.jpg": _row("stays.jpg")}
    new = {"stays.jpg": old["stays.jpg"], "fresh.jpg": _row("fresh.jpg")}

    drift = gc.diff_rows(old, new)
    out = gc.format_drift(drift)

    assert drift.added == ["fresh.jpg"]
    assert drift.removed == ["gone.jpg"]
    assert "files added to the corpus: 1 files" in out
    assert "files no longer in the corpus: 1 files" in out
