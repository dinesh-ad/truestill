"""A remembered drive path is absolute, whatever the user typed. `(ahu)`

`truestill organize src dest` stored `dest` verbatim: a path whose meaning depends on the working
directory of whoever reads it next. `decisions.write_decisions` then refused every save for the
life of that drive, so **the only durable copy of a user's trip and event names was never
written** - and `drive_reach` answered `CONNECTED` or `OFFLINE` for the same drive depending on
where the command was run from.

⚠ **Every existing test that wrote this hint passed an absolute `tmp_path`**, which is exactly why
it shipped. So the regression half here drives `main()` with a **relative** destination, from a
real working directory, and never touches the setting itself.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.decisions import DECISIONS_NAME, Decisions, write_decisions
from truestill_core.drive import DriveReach, create_marker, drive_path_hint, drive_reach

#: The one module and function permitted to write `path_hint.`. Anything else is the defect.
_THE_ONE_HOME = ("packages/truestill-core/src/truestill_core/drive.py", "remember_drive_path")


def _hint(db: Path, uuid: str) -> str | None:
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (drive_path_hint(uuid),)
        ).fetchone()
    return None if row is None else str(row[0])


def _uuid(destination: Path) -> str:
    return str(json.loads((destination / ".truestill-drive.json").read_text())["uuid"])


@pytest.fixture
def library(tmp_path: Path) -> Path:
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.txt").write_bytes(b"one")
    return tmp_path


def test_a_relative_destination_is_remembered_as_an_absolute_path(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect, driven the way a person drives it: `organize src dest`, relative, from a cwd.

    Not a helper and not an absolute `tmp_path` - the argparse boundary is where this entered, so
    the test enters there too (`handoff-2026-08-25.md` §1's DO).
    """
    monkeypatch.chdir(library)
    db = library / "c.sqlite"
    assert main(["organize", "src", "dest", "--apply", "--all-files", "--db", str(db)]) == 0

    destination = library / "dest"
    remembered = _hint(db, _uuid(destination))
    assert remembered is not None, "the drive was registered with no remembered path"
    assert Path(remembered).is_absolute(), f"a relative hint was stored: {remembered!r}"
    assert Path(remembered) == destination


def test_the_decisions_document_reaches_a_drive_registered_by_a_relative_path(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The consequence, which is the reason the entry exists rather than the mechanism."""
    monkeypatch.chdir(library)
    db = library / "c.sqlite"
    assert main(["organize", "src", "dest", "--apply", "--all-files", "--db", str(db)]) == 0
    assert (library / "dest" / DECISIONS_NAME).is_file(), (
        "the drive never received the document that carries every name a human typed"
    )


def test_an_absolute_destination_still_works(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **Cry-wolf half.** The path that always worked must keep working, unchanged."""
    monkeypatch.chdir(library)
    db = library / "c.sqlite"
    destination = library / "abs-dest"
    assert (
        main(
            [
                "organize",
                str(library / "src"),
                str(destination),
                "--apply",
                "--all-files",
                "--db",
                str(db),
            ]
        )
        == 0
    )
    remembered = _hint(db, _uuid(destination))
    assert remembered == str(destination)
    assert (destination / DECISIONS_NAME).is_file()


def test_a_relative_hint_already_in_a_catalog_reads_as_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **Existing catalogs carry the bad hint and no migration may repair it.**

    A relative hint cannot be interpreted - the working directory it was written from was never
    recorded - so `drive_reach` reports `UNKNOWN` rather than resolving it against whatever
    directory happens to be current. Before this, the same drive answered `CONNECTED` from one
    directory and `OFFLINE` from every other.
    """
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, label="D")

    # ⚠ `monkeypatch.chdir`, never bare `os.chdir`: the working directory is PROCESS-GLOBAL, so a
    # bare call leaks into every later test on this xdist worker - and when pytest removes
    # `tmp_path` the leaked cwd no longer exists, so the next `os.getcwd()` raises
    # `FileNotFoundError`. Measured: 17 unrelated failures on Linux and macOS from exactly that,
    # while Windows passed because it will not delete a directory that is a live cwd.
    monkeypatch.chdir(tmp_path)
    assert drive_reach("drive", marker.uuid) is DriveReach.UNKNOWN, (
        "a relative hint was resolved against the current working directory"
    )
    assert drive_reach(str(root), marker.uuid) is DriveReach.CONNECTED


def test_a_genuinely_unwritable_drive_still_refuses(tmp_path: Path) -> None:
    """⚠ **Cry-wolf half.** Making the path absolute must not turn a real failure into a success."""
    missing = tmp_path / "not-there"
    outcome = write_decisions(missing, Decisions(drive_uuid="u", drive_label="D"))
    assert not outcome.written
    assert outcome.error == "the drive is not there any more"


def test_no_site_writes_a_drive_path_hint_directly() -> None:
    """The census, looped over the DERIVED inventory and asserted into the DECLARATION.

    ⚠ **Both setters, not just one.** The first census of this defect grepped `set_setting(` and
    reported **five** sites; two more spelled it `set_local_setting(` and were missed. The grep is
    written against the KEY, which is the thing that cannot be spelled two ways.
    """
    root = Path(__file__).resolve().parents[3]
    found = subprocess.run(
        ["git", "grep", "-n", "drive_path_hint(", "--", "packages"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()

    source = [line for line in found if "/src/" in line]
    writers = [line for line in source if "set_setting(" in line or "set_local_setting(" in line]
    offenders = [w for w in writers if not w.startswith(_THE_ONE_HOME[0])]
    assert not offenders, (
        "a drive path hint is written outside "
        f"{_THE_ONE_HOME[0]}:{_THE_ONE_HOME[1]} - it will not be made absolute:\n  "
        + "\n  ".join(offenders)
    )
    assert writers, "the census found no writer at all, so it is asserting nothing"
