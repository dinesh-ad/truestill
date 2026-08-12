"""`truestill self-check` - and specifically, that its output cannot be misread as a pass.

**The rule this file exists to hold.** `truestill-cli` depends on `truestill-core` alone
(`IMPLEMENTATION_STANDARDS.md` §2), so it genuinely cannot see the app's bundled typefaces. The
fence is worth more than a complete sentence in one command's output - but **silence and "ok" are
the same thing to a reader**, so the omission has to be said, with a mark of its own, and repeated
in the closing line that people actually read.

Three states, and the tests keep them apart because a user must be able to tell them apart:
**checked and good**, **checked and broken**, **not checked here**.
"""

from __future__ import annotations

import shutil
import sys

import pytest
from truestill_cli.cli import main


def test_the_output_says_the_fonts_were_not_checked_rather_than_saying_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The requirement in full: named, marked distinctly, told where to go, and repeated at the end.

    A reader who scans only the last line is the one this protects. If the closing sentence said
    *"This install looks complete"* while a third of the install was never looked at, the command
    would be handing out a reassurance it did not earn.
    """
    code = main(["self-check"])
    out = capsys.readouterr().out

    assert code == 0
    assert "app fonts" in out, "the surface this command cannot see is not even named"
    assert "not checked here - run `truestill-app --self-check`" in out
    assert "??" in out, "the unchecked line shares a mark with something else"
    assert "Not checked: app fonts." in out
    assert "This install looks complete." not in out, (
        "the closing line claimed a complete install while the fonts were never looked at"
    )


def test_a_working_install_still_reports_everything_core_can_see(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """THE CRY-WOLF HALF. Without it the command could report nothing but caveats and pass.

    It also pins the three locations onto the surface a user can reach, which is the first time
    they have been written anywhere outside a docstring: where the catalog is, where the cache is,
    and where the address of a running app gets left.
    """
    main(["self-check"])
    out = capsys.readouterr().out

    for expected in ("exiftool", "trash", "catalog", "cache", "session url"):
        assert expected in out
    assert "ok  exiftool" in out.replace("  ", "  ")
    assert "send2trash" in out


def test_a_broken_install_exits_non_zero_so_a_job_need_not_parse_prose(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The machine-readable half. `(aad)`'s criteria are things a packaging job has to gate on.

    Uses the technique `test_trash_backend_is_available.py` established: block the import through
    `sys.modules` and take `gio` off PATH, which is the state a bundle that dropped the dependency
    is in on Windows.
    """
    monkeypatch.setitem(sys.modules, "send2trash", None)
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    code = main(["self-check"])
    out = capsys.readouterr().out

    assert code == 1
    assert "This install looks incomplete." in out
    assert "refuse" in out, "the consequence is not stated, only the fact"


def test_an_unchecked_surface_alone_never_fails_the_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The other half of the honesty rule: claiming a failure nobody observed is the same
    dishonesty pointing the other way. On a healthy machine this exits 0 **while** carrying the
    not-checked line, which is the combination the two assertions above cannot prove separately."""
    code = main(["self-check"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Not checked: app fonts." in out
