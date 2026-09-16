"""The copy taken before a schema upgrade is discoverable. `(akz)`

**The defect was a promise made by a docstring and kept by nothing.**
`cli._report_pre_upgrade_copy` says, in its own words, *"a user who wants it can be told where by
`truestill catalog`"* - and `truestill catalog` printed exactly two lines, the catalog and the
cache, neither of them that one.

⚠ **This matters more since the upgrade notice exists**, because that notice now names the copy as
the way back to the schema an older Truestill will still open. A sentence that points at a file
and a command that will not tell you where the file is are a pair that only works if the user
already knows.
"""

from __future__ import annotations

import pytest
from truestill_cli.cli import main
from truestill_core.app_paths import backup_path_for, default_catalog_path


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    assert main(argv) == 0
    return capsys.readouterr().out


def test_catalog_names_the_pre_upgrade_copy(capsys: pytest.CaptureFixture[str]) -> None:
    """The path, from the same derivation the copy is written to - never retyped."""
    expected = backup_path_for(default_catalog_path())

    out = _run(["catalog"], capsys)

    assert str(expected) in out


def test_it_says_there_is_none_rather_than_naming_a_file_that_is_not_there(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """⚠ **A bare path reads as a promise.**

    On a library that has never been upgraded there is nothing at that location, and printing it
    unqualified would send someone looking for a file that was never owed to them. It is also how
    a user tells a **missing** copy from an **unneeded** one, which is the distinction that
    matters after an upgrade whose copy failed.
    """
    assert not backup_path_for(default_catalog_path()).exists(), (
        "the isolated data dir already holds a pre-upgrade copy; this test's premise is gone"
    )

    out = _run(["catalog"], capsys)

    assert "none kept" in out


def test_the_copy_is_named_once_it_exists(capsys: pytest.CaptureFixture[str]) -> None:
    """The other direction, so the sentence above is not simply always printed."""
    copy = backup_path_for(default_catalog_path())
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(b"SQLite format 3\x00")

    out = _run(["catalog"], capsys)

    assert "none kept" not in out
    assert str(copy) in out


def test_every_path_the_command_prints_is_one_a_person_can_act_on(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Anti-vacuity: three labelled paths, and each says which file it means.

    A version of this command that printed one line, or printed the same path three times, would
    satisfy the assertions above.
    """
    lines = [line for line in _run(["catalog"], capsys).splitlines() if ":" in line]

    paths = {line.split(":", 1)[1].split("  ")[0].strip() for line in lines}
    assert len(lines) == 3, lines
    assert len(paths) == 3, f"two of these labels name the same file: {paths}"
