"""`truestill config`: show / set-template / preset / preview, and organize honoring the result."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli import cli as cli_module
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.layout import LAYOUT_EVENT_TEMPLATE_KEY, LAYOUT_TEMPLATE_KEY, PRESETS


def test_config_show_lists_default_and_presets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["config", "--db", str(tmp_path / "c.sqlite")]) == 0
    out = capsys.readouterr().out
    assert "{yyyy}/{yyyy}-{mm}" in out  # the year-first default
    assert "year-month-day" in out  # presets are listed


def test_set_template_persists_and_previews(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "c.sqlite"
    assert main(["config", "--db", str(db), "--set-template", "{yyyy}/{yyyy}-{mm}/{dd}"]) == 0
    assert "Preview:" in capsys.readouterr().out
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) == "{yyyy}/{yyyy}-{mm}/{dd}"


def test_preset_persists_its_template(tmp_path: Path) -> None:
    """A preset persists its resolved TEMPLATE, never its name.

    That is the property which lets preset names be renamed or retired without orphaning a
    stored setting, so it is asserted on the stored value rather than on the name.
    """
    db = tmp_path / "c.sqlite"
    assert main(["config", "--db", str(db), "--preset", "year-month-day"]) == 0
    with Catalog(db) as catalog:
        stored = catalog.get_setting(LAYOUT_TEMPLATE_KEY)
    assert stored == "{yyyy}/{yyyy}-{mm}/{yyyy}-{mm}-{dd}"
    assert "year-month-day" not in (stored or "")  # the name is not what was written


def test_invalid_template_is_rejected_and_not_saved(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "c.sqlite"
    assert main(["config", "--db", str(db), "--set-template", "{nope}"]) == 2
    assert "invalid template" in capsys.readouterr().err
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None


def test_preview_flag_does_not_persist(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "c.sqlite"
    code = main(
        ["config", "--db", str(db), "--set-template", "{yyyy}/{yyyy}-{mm}/{dd}", "--preview"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Preview:" in out
    assert "not saved" in out
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_skip_undated_names_skipped_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    # A filename-dated file (kept) and an undateable one (no EXIF, no date in name).
    Image.new("RGB", (16, 16), (1, 2, 3)).save(src / "IMG_20250804_120000.jpg", "JPEG")
    Image.new("RGB", (16, 16), (9, 8, 7)).save(src / "mystery-scan.jpg", "JPEG")
    out = tmp_path / "out"
    db = tmp_path / "c.sqlite"

    assert main(["organize", str(src), str(out), "--db", str(db), "--apply", "--skip-undated"]) == 0
    report = capsys.readouterr().out
    # ⚠ **"Never silent" moved rather than weakened.** `(afm)` stopped an authorised run from
    # re-listing per file what it is about to do, so the names are no longer in this report - the
    # count is, and the RECORD carries each name with its reason. Asserting the record is stronger
    # than asserting the terminal was: it outlives the scrollback that prompted `(afl)`.
    assert "1  skipped, no date" in report, "the run must still say how many it skipped"
    # The BLOCK, not the name: `_print_largest` prints a capped sample that names files too, so
    # `"mystery-scan.jpg" not in report` would be measuring the haystack rather than the subject.
    assert "SKIPPED (undated" not in report, "an authorised run does not re-list them"
    record = json.loads((db.parent / "last-run.json").read_text(encoding="utf-8"))
    skipped = [f for f in record["files"] if f["status"] == "skipped_undated"]
    assert [Path(f["source"]).name for f in skipped] == ["mystery-scan.jpg"], (
        "named, never silent - in the record, which is where an authorised run's detail now lives"
    )
    # The undated file was not written; the dated one was.
    written = [p.name for p in out.rglob("*.jpg")]
    assert "mystery-scan.jpg" not in written
    assert any("20250804" in n or "WA0007" in n for n in written)


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_organize_honors_stored_template(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    # A dateable name that names no origin. It must NOT be a capture convention: this test's
    # subject is the side-bin shape, and `IMG_20250804_120000.jpg` - what it used to be - is
    # Android's own naming, so it now routes to the timeline and tested nothing here.
    Image.new("RGB", (16, 16), (1, 2, 3)).save(src / "scan-20250804.jpg", "JPEG")
    dest = tmp_path / "out"
    db = tmp_path / "c.sqlite"

    assert main(["config", "--db", str(db), "--set-template", "{yyyy}/{yyyy}-{mm}/{dd}"]) == 0
    assert main(["organize", str(src), str(dest), "--db", str(db), "--apply"]) == 0

    placed = list(dest.rglob("*.jpg"))
    assert placed, "a file should have been organized"
    rel = placed[0].relative_to(dest).as_posix()
    # Routing on rule is now live: this fixture carries no camera EXIF and no capture-convention
    # name, so it belongs in a labelled side bin rather than on the timeline. The side-bin shape
    # is fixed and deliberately NOT the stored timeline template. Timeline routing under a
    # stored template is covered end to end in test_year_first_organize.py.
    assert rel == "Saved/2025/2025-08/scan-20250804.jpg"
    assert "/2025/08/" not in rel  # not the legacy bare-month shape


def test_an_unknown_preset_fails_with_an_actionable_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A mistyped preset must name the mistake and show the options.

    `flat-date` is one of the five names removed in the year-first correction, so this is also
    the case a user following an old note or an old README will hit.
    """
    db = tmp_path / "c.sqlite"
    assert main(["config", "--db", str(db), "--preset", "flat-date"]) == 2

    err = capsys.readouterr().err
    assert "unknown preset" in err
    assert "flat-date" in err  # what they typed
    for name in ("year-month-event", "year-event", "year-month-day"):
        assert name in err  # and every option they actually have
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None  # nothing was written


def test_every_preset_named_in_user_facing_copy_exists() -> None:
    """A command or standalone preset key in shipped copy must resolve through the registry."""
    references = {
        match
        for groups in re.findall(
            r"--preset\s+([a-z][a-z0-9-]*)|`([a-z][a-z0-9-]*)`",
            cli_module._PINNED_NOTICE,
        )
        for match in groups
        if match
    }

    assert references
    assert references <= PRESETS.keys()


def test_a_category_template_is_refused_at_the_config_door(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R2: the year is the top-level parent structurally, not by convention."""
    db = tmp_path / "c.sqlite"
    assert main(["config", "--db", str(db), "--set-template", "{category}/{yyyy}/{mm}"]) == 2

    assert "{category} cannot be used in the timeline" in capsys.readouterr().err
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None


def test_a_preset_with_a_distinct_event_shape_persists_both_and_clears_on_switch(
    tmp_path: Path,
) -> None:
    """`year-event` is the only preset whose evented shape differs, so it needs a second key.

    Switching away must *clear* it: a stale override would keep sending events somewhere the
    newly-chosen preset does not put them.
    """
    db = tmp_path / "c.sqlite"
    assert main(["config", "--db", str(db), "--preset", "year-event"]) == 0
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) == "{yyyy}/{yyyy}-{mm}"
        assert catalog.get_setting(LAYOUT_EVENT_TEMPLATE_KEY) == "{yyyy}"

    # year-month-day's evented and un-evented shapes are identical, so switching to it must
    # CLEAR the override rather than leave year-event's behind.
    assert main(["config", "--db", str(db), "--preset", "year-month-day"]) == 0
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_EVENT_TEMPLATE_KEY) is None


def test_no_removed_preset_name_survives_anywhere_in_the_tree() -> None:
    """The five names are deleted, not hidden -- proved against the repo, not the registry.

    Only resolved template *strings* are ever persisted, so removing the names cannot orphan a
    stored setting; what it can do is leave a stale name in help text or a doc that sends
    someone to a preset that no longer exists.
    """
    removed = (
        "category-year-month-day",
        "category-year-month",
        "category-year-event",
        "category-year",
        "flat-date",
    )
    root = Path(__file__).resolve().parents[3]
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.split()
    assert tracked, (
        "`git ls-files` (whole repo) returned nothing, so this guard has no subject and would pass by\n"
        "finding zero violations in zero files. See ENGINEERING_STANDARD.md 4, the\n"
        "fifty-second member: a guard must prove its subject is non-empty first."
    )

    offenders: list[str] = []
    for relative in tracked:
        path = root / relative
        # This test names the strings it forbids, and the research docs record the history.
        if path.suffix in {".png", ".jpg", ".ico"} or relative in {
            "packages/truestill-cli/tests/test_config_cli.py",
            "docs/default-layout-research.md",
        }:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        offenders += [f"{relative}: {name}" for name in removed if name in text]

    assert not offenders, "removed preset names still present: " + "; ".join(offenders)
