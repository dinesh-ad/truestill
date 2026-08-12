"""`truestill-app --self-check` - the entry point an installed copy actually has.

**Why this flag and not only the CLI command.** Installers ship `truestill-app`; the person who
double-clicked an icon has no `truestill` on a PATH and no terminal to type it in. This is also
the only surface that can answer for the bundled typefaces, because the CLI depends on core alone.

**Two properties are load-bearing and neither is obvious from reading the flag:**

1. it must **not start a server** - an install being asked whether it is intact must not have to
   be working in order to answer, and a check that bound a port would fail on a machine already
   running a copy;
2. it must be able to write to a **file**, because a windowed Windows build has ``sys.stdout is
   None`` and `print` is a silent no-op there - which is the platform the whole check exists for.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from truestill_app import __main__ as app_main

#: Raised by the stub below. A named message so the assertion that expects it can match on
#: something stable rather than on a sentence that will be reworded.
_BOUND_A_SOCKET = "--self-check bound a listening socket; it must never start a server"


def _refuse_to_bind(_port: int) -> None:
    raise AssertionError(_BOUND_A_SOCKET)


def test_the_check_prints_a_report_and_never_starts_a_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Patched on `__main__`, the module that OWNS `bind_listening_socket` - §4, third member.

    A patch aimed at a re-export would leave the real call running and this test would pass while
    proving nothing about the thing it names.
    """
    monkeypatch.setattr(app_main, "bind_listening_socket", _refuse_to_bind)

    code = app_main.main(["--self-check"])
    out = capsys.readouterr().out

    assert code == 0
    assert "exiftool" in out
    assert "font DejaVuSansMono.ttf" in out, "the app's own surface is missing from its own check"
    assert "This install looks complete." in out
    assert "Not checked" not in out, (
        "the app can see every surface, so it must not carry the CLI's caveat"
    )


def test_a_path_makes_it_write_json_instead_of_printing_the_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The windowed case. The file is the delivery mechanism there, not a convenience.

    The report itself must not also be printed: on the platform this exists for nobody would see
    it, and a job that reads the file would then have two sources for one answer.
    """
    monkeypatch.setattr(app_main, "bind_listening_socket", _refuse_to_bind)
    destination = tmp_path / "findings" / "self-check.json"

    code = app_main.main(["--self-check", str(destination)])
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["complete"] is True
    assert {f["name"] for f in payload["findings"]} >= {"exiftool", "trash", "font licence"}
    assert str(destination) in out, "nothing said where the report went"
    assert "This install looks complete." not in out, "the report was printed as well as written"


def test_a_broken_install_exits_non_zero_through_this_entry_point_too(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The exit code is what a packaging job gates on, and it has to work on **both** surfaces.

    Asserted here as well as on the CLI deliberately: `(aad)`'s criteria are about the artifact,
    and the artifact runs this one. A job trusting an exit code that only the other entry point
    sets would be reading a green tick from a command nobody frozen will ever run.
    """
    monkeypatch.setattr(app_main, "bind_listening_socket", _refuse_to_bind)
    monkeypatch.setitem(sys.modules, "send2trash", None)
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    destination = tmp_path / "self-check.json"

    code = app_main.main(["--self-check", str(destination)])

    assert code == 1
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["complete"] is False
    assert payload["worst"] == "missing"


def test_the_flag_is_absent_by_default_so_an_ordinary_launch_is_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE CRY-WOLF HALF: adding this must not have turned every launch into a self-check.

    Proved by the opposite of the other tests - a run with no flag reaches the socket, and the
    refusing stub is what makes that observable rather than a matter of trust.
    """
    monkeypatch.setattr(app_main, "bind_listening_socket", _refuse_to_bind)

    with pytest.raises(AssertionError, match="must never start a server"):
        app_main.main(["--no-browser"])
