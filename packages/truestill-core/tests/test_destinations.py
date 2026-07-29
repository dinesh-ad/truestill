"""Destination backends: local reference impl, and rclone construction guard."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from truestill_core.destinations import LocalDestination
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.rclone import RcloneDestination


def test_local_upload_exists_list_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / "src.jpg"
    source.write_bytes(b"payload")
    dest = LocalDestination(tmp_path / "out")

    rel = "Camera/2025/08/src.jpg"
    assert dest.exists(rel) is False
    dest.upload(source, rel)
    assert dest.exists(rel) is True
    assert dest.list() == [rel]
    assert (tmp_path / "out" / rel).read_bytes() == b"payload"


def test_local_describe(tmp_path: Path) -> None:
    assert LocalDestination(tmp_path).describe() == f"local:{tmp_path}"


def test_rclone_missing_binary_raises() -> None:
    with pytest.raises(DestinationError):
        RcloneDestination("pcloud:Photos", binary="rclone-does-not-exist-xyz")


def test_rclone_target_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/rclone")
    dest = RcloneDestination("pcloud:Photos/GoogleBackup")
    assert dest.describe() == "pcloud:Photos/GoogleBackup"
    assert dest._target("Camera/2025/08/a.jpg") == "pcloud:Photos/GoogleBackup/Camera/2025/08/a.jpg"


def test_rclone_stamps_the_uploaded_remote_without_creating_a_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/rclone")
    dest = RcloneDestination("pcloud:Photos")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(dest, "_run", lambda *args: calls.append(args))

    dest.set_timestamp(
        "Camera/2025/08/a.jpg",
        datetime(2025, 8, 20, 14, 30, tzinfo=UTC),
    )

    assert calls == [
        (
            "touch",
            "--no-create",
            "--timestamp",
            "2025-08-20T14:30:00.000000",
            "pcloud:Photos/Camera/2025/08/a.jpg",
        )
    ]
