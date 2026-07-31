"""The legacy catalog is looked for only where a working directory means something.

**The defect ((aad)).** ``LEGACY_CATALOG_PATH`` is ``reports/catalog.sqlite`` - **relative** - so
`default_catalog_path` asks *"is there a reports/ here"* where *here* is whatever Explorer or
Finder handed the process: ``C:\\Windows\\System32``, ``/``, or the user's home depending on how
it was launched. For an installed app that question has no meaning, and the answer it gets is
an accident.

**How a meaningful working directory is distinguished, without asking about the directory.**
Not by guessing who is a developer - a user with a ``reports/`` folder is not one, and a rule
that tried to tell them apart would be wrong in both directions. The signal is *how the process
was started*: a **windowed launch has no console**, and that is exactly the case where nobody
chose the working directory. A terminal invocation - a developer in a checkout, a `pip`-
installed user in their own folder - has one, and its working directory is the one they typed
the command in.

**So the `(aae)` promise survives intact for everyone who can have a legacy catalog.** Anyone
holding a ``reports/catalog.sqlite`` today got it by running truestill from a terminal, and
every terminal invocation still finds it. What is skipped is the case that could never have
created one: a double-clicked window whose working directory nobody chose. The installed case is
fixed without touching the case `(aae)` was written for.

**A skipped probe says nothing.** No "legacy location not checked" line anywhere - the `catalog`
command reports which catalog is in use, and reporting on paths it deliberately did not look at
would be noise about a decision the user did not make and cannot act on.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from truestill_core.app_paths import default_catalog_path, standard_catalog_path


def _legacy_in(directory: Path) -> Path:
    legacy = directory / "reports" / "catalog.sqlite"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(b"an existing catalog")
    return legacy


def test_a_terminal_run_still_finds_an_existing_legacy_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `(aae)` promise, unchanged: nobody's setup breaks on upgrade."""
    monkeypatch.chdir(tmp_path)
    legacy = _legacy_in(tmp_path)

    assert default_catalog_path() == legacy


def test_a_windowed_launch_does_not_probe_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fix. With no console the working directory is an accident, so it is not consulted.

    The streams are set here in the body rather than in a fixture: pytest's capture plugin
    re-assigns them for the call phase, so a fixture would be silently undone and this test
    would pass without its precondition (guard rule 7).
    """
    monkeypatch.chdir(tmp_path)
    _legacy_in(tmp_path)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    resolved = default_catalog_path()

    # Compared against the standard location exactly. `not resolved.is_relative_to(tmp_path)`
    # looks equivalent and is not: it is trivially true of any RELATIVE path, so it passed
    # against the unfixed code while proving nothing.
    assert resolved == standard_catalog_path(), (
        f"a double-clicked app adopted a catalog from a directory nobody chose: {resolved}"
    )


def test_the_legacy_path_is_returned_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relative answer means a different file after any chdir, including one inside truestill.

    `Catalog(db)` opens relative to the working directory *at that moment*, so a relative
    default is a catalog whose identity depends on when you ask.
    """
    monkeypatch.chdir(tmp_path)
    _legacy_in(tmp_path)

    assert default_catalog_path().is_absolute()


def test_resolution_still_creates_nothing_when_the_probe_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skipping a probe must not become a reason to make the directory it skipped."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    default_catalog_path()

    assert list(tmp_path.iterdir()) == []


def test_a_skipped_probe_is_not_announced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Say nothing rather than report an absence.

    `default_catalog_path` answers a question; a line about a path it chose not to look at would
    be noise about a decision the user did not make and cannot act on.
    """
    monkeypatch.chdir(tmp_path)
    _legacy_in(tmp_path)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    default_catalog_path()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
