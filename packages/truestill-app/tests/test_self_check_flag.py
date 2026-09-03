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
from truestill_app.selfcheck import app_findings
from truestill_core.selfcheck import Status, is_complete

#: Raised by the stub below. A named message so the assertion that expects it can match on
#: something stable rather than on a sentence that will be reworded.
_BOUND_A_SOCKET = "--self-check bound a listening socket; it must never start a server"


def _refuse_to_bind(_port: int) -> None:
    raise AssertionError(_BOUND_A_SOCKET)


def _exit_this_install_earns() -> int:
    """The exit code the report justifies: 0 when this checkout is complete, 1 when the ONLY thing
    it lacks is the React bundle - the honest verdict on a machine with no Node, which is what the
    CI check lanes are (`(ajv)`, 2026-09-03). Anything else missing fails here, as before."""
    findings = app_findings()
    # The same rule `is_complete` applies: only DEGRADED and MISSING make an install incomplete.
    lacking = [f for f in findings if f.status in {Status.DEGRADED, Status.MISSING}]
    assert all(f.name.startswith("bundle ") for f in lacking), [f.name for f in lacking]
    assert all("make frontend" in f.detail for f in lacking), [f.detail for f in lacking]
    return 0 if is_complete(findings) else 1


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

    assert code == _exit_this_install_earns()
    assert "exiftool" in out
    assert "font DejaVuSansMono.ttf" in out, "the app's own surface is missing from its own check"
    complete = _exit_this_install_earns() == 0
    assert ("This install looks complete." in out) is complete, out
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

    assert code == _exit_this_install_earns()
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["complete"] is (_exit_this_install_earns() == 0)
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


def test_with_no_console_it_writes_a_report_and_opens_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The Start-menu case, and the reason the shortcut is worth offering at all.

    With no console `_say` is a silent no-op, so a printed report makes the shortcut appear to do
    nothing - worse than not offering it. The report goes beside `session-url.txt`, in the data
    directory, and is handed to whatever the user opens text with.

    ``sys.stdout`` is set **in the test body**, not a fixture: pytest's capture plugin re-assigns
    both streams for the call phase, so a fixture-set ``None`` is gone by the time the body runs
    (`ENGINEERING_STANDARD.md` §4, seventh member - and that instance was this same flag).
    """
    monkeypatch.setattr(app_main, "bind_listening_socket", _refuse_to_bind)
    monkeypatch.setenv("TRUESTILL_DATA_DIR", str(tmp_path / "data"))
    opened: list[list[str]] = []
    monkeypatch.setattr(app_main.binaries, "os_opener", lambda: "opener")
    monkeypatch.setattr(app_main.binaries, "popen", lambda cmd, **_kw: opened.append(list(cmd)))
    monkeypatch.setattr(sys, "stdout", None)
    assert sys.stdout is None, "the precondition did not survive to the assertion"

    code = app_main.main(["--self-check"])

    report = tmp_path / "data" / "self-check.txt"
    assert code == _exit_this_install_earns()
    assert report.is_file(), "nothing was written, so the shortcut would do nothing visible"
    assert opened == [["opener", str(report)]], "the report was written but never opened"


def test_a_machine_with_no_opener_still_writes_the_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """THE CRY-WOLF HALF: a headless box has no opener, and that must not lose the report.

    `os_opener` returning ``None`` is a real answer rather than an error - the file is still
    there to be read by whoever is helping.
    """
    monkeypatch.setattr(app_main, "bind_listening_socket", _refuse_to_bind)
    monkeypatch.setenv("TRUESTILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(app_main.binaries, "os_opener", lambda: None)
    monkeypatch.setattr(sys, "stdout", None)
    assert sys.stdout is None

    code = app_main.main(["--self-check"])

    assert code == _exit_this_install_earns()
    assert (tmp_path / "data" / "self-check.txt").is_file()


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
