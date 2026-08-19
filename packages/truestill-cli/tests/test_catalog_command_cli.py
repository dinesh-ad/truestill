"""The ``catalog`` command surface: which catalog is in use, where the standard place is.

**This command had no test on any platform**, which is why three CI lanes rendered none of it.
The gap was found by asking what the Windows lane actually *exercised* rather than reading its
green tick, and it hid a real defect underneath.

**The defect.** ``_cmd_catalog`` built the standard location from
``platformdirs.user_data_dir(APP_NAME)`` directly, while everything else in the product goes
through ``app_paths``, which honours ``TRUESTILL_DATA_DIR``. Under an override the two disagree,
and a command whose entire job is answering *"which catalog am I using?"* printed a path that
was not it.

Two consequences, and the second is the serious one:

* **It cried wolf.** ``current != standard`` was true for every override install, so the command
  told a user whose catalog was exactly where it belonged that it was "in the old location" and
  offered to move it.
* **``--move`` wrote to the wrong place.** The same variable is the *destination*, so the copy
  landed in the un-overridden OS directory - somewhere ``default_catalog_path`` will never look.
  A user who followed the advice, checked the copy, and deleted the original as the report tells
  them to would be left with truestill reporting "No catalog yet".

The cause was structural rather than careless: ``app_paths`` owned "where does the catalog go"
but exposed no name for "where does it *belong*", so the one caller that needed it reimplemented
the rule and got it wrong. The fix gave that rule a home - `standard_catalog_path` - and the
CLI stops importing `platformdirs` at all.

The session fixture points ``TRUESTILL_DATA_DIR`` at a temporary directory, so **every test here
runs the override case by construction** - the case the old code got wrong.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.app_paths import (
    DATA_DIR_ENV,
    cache_path_for,
    default_catalog_path,
)
from truestill_core.catalog import Catalog


def _lines(out: str) -> dict[str, str]:
    """The report's ``label : value`` lines, keyed by trimmed label."""
    found = {}
    for line in out.splitlines():
        if " : " in line:
            label, _, value = line.partition(" : ")
            found[label.strip()] = value.strip()
    return found


def test_the_standard_place_is_the_one_the_product_would_actually_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The bug, at its sharpest: the announced standard place must honour the override.

    Built from ``platformdirs`` directly, this printed the un-overridden OS directory - a path
    this install will never read or write.
    """
    monkeypatch.chdir(tmp_path)

    assert main(["catalog"]) == 0

    reported = _lines(capsys.readouterr().out)
    assert reported["Catalog in use"] == str(default_catalog_path())


def test_a_catalog_already_in_the_standard_place_is_not_called_old(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cry-wolf half. With no legacy catalog, in-use *is* the standard place.

    The old code compared against a location this install never uses, so the two never matched
    and every override install was told to move a catalog that was already right.
    """
    monkeypatch.chdir(tmp_path)

    assert main(["catalog"]) == 0

    out = capsys.readouterr().out
    assert "old location" not in out, "a correctly-placed catalog was reported as misplaced"
    # ⚠ Since `(aeb)` there is no "Standard place" line to compare against: it printed a second
    # spelling of the same value, and comparing the two is what produced the false claim.
    assert "Standard place" not in out
    assert _lines(out)["Catalog in use"] == str(default_catalog_path())


def test_a_legacy_catalog_in_the_working_directory_is_not_reported_as_in_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ REVERSED BY `(adw)`, 2026-08-19, AND THE CONSEQUENCE IS RECORDED RATHER THAN GLOSSED.

    This asserted the opposite: that a `reports/catalog.sqlite` beside the working directory was
    *"reported as in use and offered a move"*. It was, and that was the defect - the same install
    reported a different catalog in use depending on where it was run, because the path is
    relative.

    **What this costs, stated plainly:** `truestill catalog` no longer notices a legacy file, so a
    user who has one is no longer told it exists or pointed at `--move`. `--move` still works and
    still migrates it; nothing advertises it. That is acceptable **only** because the population
    who can hold one is a single person - no release has ever been published - and their catalog
    was migrated before this landed. It would not be acceptable after a release, which is exactly
    why `(adw)` records that the reasoning expires at the first `v*` tag.
    """
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "reports" / "catalog.sqlite"
    legacy.parent.mkdir()
    with Catalog(legacy):
        pass

    assert main(["catalog"]) == 0

    out = capsys.readouterr().out
    reported = _lines(out)
    assert reported["Catalog in use"] != str(legacy), (
        "a catalog in the working directory was reported as in use, so `cd` still decides which "
        "library this is"
    )
    assert "old location" not in out


def test_the_cache_line_is_the_cache_that_catalog_actually_uses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not a third opinion about where the cache lives - the same answer `HashCache` gets."""
    monkeypatch.chdir(tmp_path)

    assert main(["catalog"]) == 0

    reported = _lines(capsys.readouterr().out)
    assert reported["Cache"] == str(cache_path_for(default_catalog_path()))
    assert reported["Cache"] != reported["Catalog in use"]


def test_move_copies_into_the_location_this_install_will_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The serious half: the destination is the same variable that was printed.

    Copying to the un-overridden OS directory puts the catalog where `default_catalog_path` will
    never look - and the report then tells the user to delete the original once satisfied.

    This is the one test here that *creates* the standard catalog, so it narrows the data root to
    its own ``tmp_path`` first. Writing into the session-wide root would leave a catalog behind
    for every later test, and the ones asserting "No catalog yet" would fail depending on the
    order they ran in.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path / "data"))
    legacy = tmp_path / "reports" / "catalog.sqlite"
    legacy.parent.mkdir()
    with Catalog(legacy):
        pass

    assert main(["catalog", "--move"]) == 0

    capsys.readouterr()
    assert default_catalog_path().is_file(), "the copy did not land where this install reads"
    assert legacy.is_file(), "the original must stay until the user removes it"
