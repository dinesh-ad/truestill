"""A folder that cannot be read must be reported as unreadable, never as missing (audit F21).

**The defect is not the one the audit described, and the correction matters.** The audit read
``filesystem_relationship`` and reported that a ``PermissionError`` was being *worded* as
"The source folder was not found". Running it showed two things wrong with that:

1. `Path.exists` and `Path.is_dir` swallow ``OSError`` only for the "not there" errno family
   (pathlib's ``_ignore_error``) and **re-raise ``EACCES``**. A permission-denied folder never
   reached the message - it raised, which is an HTTP 500 on three routes and a dead organize
   preview.
2. Both "was not found" branches were unreachable anyway: a path that simply does not exist
   resolves through its nearest existing ancestor, so the walk answers rather than failing.

So the strings the audit wanted reworded had never been shown to anyone. What this module pins
is the behaviour that replaced them:

* the folder is there and usable -> answer the question;
* nothing is there yet -> still answer it, from the parent it would be created in;
* something is there and the OS refused to describe it -> say *that*, name the folder, and do
  **not** offer to create it (the create fails with the same ``EACCES``).

Every test is paired: one half proves the unreadable case is handled, the other proves the guard
does not cry wolf on a missing or ordinary folder. A probe that called everything unreadable
would pass the first half of each pair alone.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient
from truestill_app.service.fs_browse import fs_dirs, fs_validate
from truestill_app.service.organize import filesystem_relationship
from truestill_app.service.path_probe import PathReach, nearest_device, probe_dir


def _deny(monkeypatch: pytest.MonkeyPatch, target: Path) -> None:
    """Make ``target`` - and only it - raise ``PermissionError`` from the stat-backed probes.

    Faithful to a real ``chmod 000`` parent, which
    ``test_a_real_locked_directory_raises_from_is_dir`` proves on POSIX. Monkeypatching rather
    than chmod-ing keeps these assertions running on the Windows CI runner, where a mode of 000
    does not deny the owner.
    """
    for name in ("exists", "is_dir", "stat"):
        original = getattr(Path, name)

        def patched(self: Path, *args: Any, _orig: Any = original, **kwargs: Any) -> Any:
            if self == target:
                raise PermissionError(13, "Permission denied", str(self))
            return _orig(self, *args, **kwargs)

        monkeypatch.setattr(Path, name, patched)


@contextmanager
def _really_locked(path: Path) -> Iterator[bool]:
    """Yield whether ``path`` is genuinely unreadable after a real ``chmod 000``.

    Yields False - so the caller skips - rather than passing vacuously when the mode does not
    actually deny (running as root, or a filesystem that ignores it). A test that cannot
    reproduce its condition must say so rather than report success.
    """
    path.chmod(0o000)
    try:
        try:
            (path / "child").is_dir()
            denied = False
        except PermissionError:
            denied = True
        yield denied
    finally:
        path.chmod(0o755)


# --- the premise, and the probe -------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="chmod 000 does not deny the owner on Windows")
def test_a_real_locked_directory_raises_from_is_dir(tmp_path: Path) -> None:
    """The premise, proven on a real filesystem rather than taken from the documentation.

    If `Path.is_dir` ever starts swallowing ``EACCES``, this fails - which is exactly when
    someone should be made to re-read this module's rationale.
    """
    locked = tmp_path / "locked"
    (locked / "inner").mkdir(parents=True)
    with _really_locked(locked) as denied:
        if not denied:
            pytest.skip("chmod 000 did not deny this process")
        with pytest.raises(PermissionError):
            (locked / "inner").is_dir()


def test_probe_dir_separates_unreadable_from_missing_and_from_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readable = tmp_path / "readable"
    readable.mkdir()
    a_file = tmp_path / "a-file.txt"
    a_file.write_text("x", encoding="utf-8")
    denied = tmp_path / "denied"
    denied.mkdir()

    assert probe_dir(readable) is PathReach.DIRECTORY
    assert probe_dir(tmp_path / "nothing-here") is PathReach.MISSING
    assert probe_dir(a_file) is PathReach.NOT_A_DIRECTORY

    _deny(monkeypatch, denied)
    assert probe_dir(denied) is PathReach.UNREADABLE


def test_nearest_device_answers_for_a_missing_folder_but_stops_at_a_denied_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The distinction the whole fix rests on.

    A destination that does not exist yet is the *normal* case - it will be created on its
    parent's filesystem, so walking up is the right answer, not a failure. A denied directory
    is different: walking past it would answer the question with a different folder's device,
    confidently and sometimes wrongly.
    """
    readable = tmp_path / "readable"
    readable.mkdir()
    assert nearest_device(readable).device_id is not None
    assert nearest_device(readable).blocked_at is None

    not_yet = nearest_device(tmp_path / "not-yet" / "deeper")
    assert not_yet.device_id is not None, "a missing folder answers from its nearest parent"
    assert not_yet.blocked_at is None

    denied = tmp_path / "denied"
    denied.mkdir()
    _deny(monkeypatch, denied)
    blocked = nearest_device(denied)
    assert blocked.device_id is None
    assert blocked.blocked_at == denied


# --- fs_dirs (the Browse picker) ------------------------------------------------------


def test_fs_dirs_reports_a_denied_folder_instead_of_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    denied = tmp_path / "denied"
    denied.mkdir()
    _deny(monkeypatch, denied)

    result = fs_dirs(str(denied))

    assert "error" in result
    message = result["error"].lower()
    assert "permission" in message or "access" in message, result["error"]
    assert "not a folder" not in message


def test_fs_dirs_still_says_not_a_folder_for_a_file(tmp_path: Path) -> None:
    """Cry-wolf half: an ordinary file must not be reported as a permissions problem."""
    a_file = tmp_path / "a-file.txt"
    a_file.write_text("x", encoding="utf-8")

    result = fs_dirs(str(a_file))

    assert "error" in result
    assert "not a folder" in result["error"].lower()
    assert "permission" not in result["error"].lower()


def test_fs_dirs_still_lists_an_ordinary_folder(tmp_path: Path) -> None:
    """Cry-wolf half: the happy path must be untouched."""
    (tmp_path / "sub-a").mkdir()
    (tmp_path / "sub-b").mkdir()

    result = fs_dirs(str(tmp_path))

    assert "error" not in result
    assert [entry["name"] for entry in result["entries"]] == ["sub-a", "sub-b"]


def test_browsing_into_a_denied_folder_is_not_a_500(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The user-visible shape of the defect: the picker answered 500, so Browse simply died."""
    denied = tmp_path / "denied"
    denied.mkdir()
    _deny(monkeypatch, denied)

    response = client.get("/api/fs/dirs", params={"path": str(denied)})

    assert response.status_code == 200
    assert "error" in response.json()


# --- fs_validate (the hint under every folder field) ----------------------------------


def test_fs_validate_marks_a_denied_folder_unreadable_not_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``exists: false`` for a denied folder is what made the UI offer to create it."""
    denied = tmp_path / "denied"
    denied.mkdir()
    _deny(monkeypatch, denied)

    result = fs_validate(str(denied))

    assert result["unreadable"] is True
    assert result["writable"] is False


def test_fs_validate_leaves_a_genuinely_missing_folder_creatable(tmp_path: Path) -> None:
    """Cry-wolf half: a folder that really is absent must stay offerable to create."""
    result = fs_validate(str(tmp_path / "not-yet"))

    assert result["unreadable"] is False
    assert result["exists"] is False


def test_fs_validate_is_unchanged_for_an_ordinary_folder(tmp_path: Path) -> None:
    source = tmp_path / "photos"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"x")

    result = fs_validate(str(source))

    assert result["unreadable"] is False
    assert result["exists"] is True
    assert result["is_dir"] is True
    assert result["media"] == 1


def test_validate_on_a_denied_folder_is_not_a_500(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    denied = tmp_path / "denied"
    denied.mkdir()
    _deny(monkeypatch, denied)

    response = client.get("/api/fs/validate", params={"path": str(denied)})

    assert response.status_code == 200
    assert response.json()["unreadable"] is True


# --- filesystem_relationship (the organize mode briefing) -----------------------------


def test_filesystem_relationship_says_access_denied_and_names_the_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "dest"
    destination.mkdir()
    denied = tmp_path / "denied"
    denied.mkdir()
    _deny(monkeypatch, denied)

    result = filesystem_relationship(denied, destination)

    assert result["ok"] is False
    error = result["error"]
    assert "not found" not in error.lower(), error
    assert "denied" in error.lower() or "permission" in error.lower(), error
    assert str(denied) in error, "the message must name the folder it is about"


def test_filesystem_relationship_answers_for_a_not_yet_created_destination(
    tmp_path: Path,
) -> None:
    """Cry-wolf half, and the common case: a new backup folder does not exist yet.

    It will be created on its parent's filesystem, so the question is answerable and must be
    answered - reporting a problem here would block the normal first-run flow.
    """
    source = tmp_path / "src"
    source.mkdir()

    result = filesystem_relationship(source, tmp_path / "BackupA")

    assert result["ok"] is True
    assert result["same_filesystem"] is True


def test_filesystem_relationship_is_unchanged_for_two_readable_folders(tmp_path: Path) -> None:
    source = tmp_path / "src"
    destination = tmp_path / "dst"
    source.mkdir()
    destination.mkdir()

    result = filesystem_relationship(source, destination)

    assert result["ok"] is True
    assert result["same_filesystem"] is True


def test_the_relationship_route_does_not_die_on_a_denied_destination(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_mode_mechanism`` sits on the organize preview path and probed the same way."""
    source = tmp_path / "src"
    source.mkdir()
    denied = tmp_path / "denied"
    denied.mkdir()
    _deny(monkeypatch, denied)

    response = client.get(
        "/api/fs/relationship",
        params={"source": str(source), "destination": str(denied)},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
