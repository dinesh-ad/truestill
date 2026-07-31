"""A drive that vanishes between request and job must be reported, not asserted (audit F20).

``migration_preview_run`` read the marker at **request** time, then its job target ran later on
a **worker thread** and did::

    result = migration_preview(path, db, progress=progress, cancel=cancel)
    assert result["ok"] is True  # marker gated above; soft-fail already returned

The comment's premise is a time-of-check/time-of-use gap. ``migration_preview`` re-reads the
marker itself, so unplugging the drive in between makes it return the drive-correction payload -
and the assertion then fires on a value the function is *designed* to return.

**What the assertion was actually guarding: the type signature, not the user.**
``migration_preview`` returns ``MigrationPreviewOk | DriveUnavailablePayload`` while ``target``
is declared ``-> MigrationPreviewOk``. The assert existed to narrow that union for mypy. Its
runtime effect was incidental, and when the narrowing turned out to be false it converted a
well-formed soft-fail into an unhandled exception: ``jobs.py`` catches it, sets
``code="AssertionError"``, and since a bare assert carries no message, ``app.js`` renders
``friendly || esc(d.error)`` as an **empty banner**. Every sibling path for the same condition -
``migration_apply``, ``backup_run`` - raises ``NotABackupDriveError``, which *is* in
``FRIENDLY_ERRORS`` and answers with a next step.

These tests drive the violated assumption directly, which is the only way to know the gate
holds: the previous version passed every existing test precisely because nothing ever made the
assumption false.
"""

from __future__ import annotations

import ast
import threading
from pathlib import Path

import pytest
from truestill_app.service import migrate as service_migrate
from truestill_app.service.drive_support import NotABackupDriveError
from truestill_core.drive import create_marker


def _soft_fail(*_args: object, **_kwargs: object) -> dict[str, object]:
    """What ``migration_preview`` really returns once the drive is gone."""
    return {
        "ok": False,
        "error": "Can't reach the drive.",
        "suggested_root": None,
        "drive_label": None,
        "can_register": False,
    }


def test_a_drive_that_vanishes_after_the_gate_raises_a_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The assumption violated: marker present at request time, gone when the job runs."""
    drive = tmp_path / "drive"
    drive.mkdir()
    create_marker(drive, "Cabinet")
    db = tmp_path / "c.sqlite"

    target = service_migrate.migration_preview_run(drive, db)
    assert callable(target), "the request-time gate should have passed"

    # Patched on the OWNING module: migration_preview_run calls it through this module's
    # globals, so patching the service facade would not intercept it (audit F21 follow-up).
    monkeypatch.setattr(service_migrate, "migration_preview", _soft_fail)

    with pytest.raises(NotABackupDriveError) as caught:
        target(lambda _p: None, threading.Event())

    message = str(caught.value)
    assert message, "a bare assert carried no message; the replacement must say something"
    assert str(drive) in message or "drive" in message.lower(), message


def test_the_failure_is_a_class_the_ui_already_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`jobs.py` sends ``type(exc).__name__`` and `app.js` matches on it.

    ``AssertionError`` is not in ``FRIENDLY_ERRORS`` and a bare assert has no message, so the
    old failure rendered an empty banner. The class name is the contract here, so it is pinned.
    """
    drive = tmp_path / "drive"
    drive.mkdir()
    create_marker(drive, "Cabinet")
    target = service_migrate.migration_preview_run(drive, tmp_path / "c.sqlite")
    assert callable(target)
    monkeypatch.setattr(service_migrate, "migration_preview", _soft_fail)

    with pytest.raises(Exception) as caught:  # noqa: PT011 - the class IS the assertion
        target(lambda _p: None, threading.Event())

    assert type(caught.value).__name__ == "NotABackupDriveError"
    assert not isinstance(caught.value, AssertionError)


def test_the_gate_survives_python_dash_oh() -> None:
    """The replacement must not be strippable.

    Nothing in this repo runs `python -O` today - the console scripts launch a plain
    interpreter and the wheels ship no ``.pyc`` - so the old assert did execute in production.
    But that is a property of how it happens to be launched, not of the code: ``PYTHONOPTIMIZE=1``
    is a user's environment variable. A gate that a flag can delete is not a gate, so this pins
    that the failure path is a raised exception rather than an assertion.
    """
    tree = ast.parse(Path(service_migrate.__file__).read_text(encoding="utf-8"))
    run = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "migration_preview_run"
    )
    # AST, not a string slice: the next top-level construct here is a class, so slicing on
    # "\ndef " ran past the function and found an assert belonging to something else.
    asserts = [n for n in ast.walk(run) if isinstance(n, ast.Assert)]
    assert not asserts, f"the job target must not gate on an assert (line {asserts[0].lineno})"
    raises = [n for n in ast.walk(run) if isinstance(n, ast.Raise)]
    assert raises, "the violated assumption must raise something"


def test_a_reachable_drive_still_previews(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cry-wolf half: the ordinary path must not start raising."""
    drive = tmp_path / "drive"
    drive.mkdir()
    create_marker(drive, "Cabinet")
    ok = {
        "ok": True,
        "label": "Cabinet",
        "template": "t",
        "unchanged": 0,
        "moves": [],
        "warnings": [],
        "day_folder_reasons": [],
        "pending_drives": [],
    }
    target = service_migrate.migration_preview_run(drive, tmp_path / "c.sqlite")
    assert callable(target)
    monkeypatch.setattr(service_migrate, "migration_preview", lambda *_a, **_k: ok)

    assert target(lambda _p: None, threading.Event()) == ok
