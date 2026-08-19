"""Folder-picker + library-status endpoints (the UI v2 home screen's backend)."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient
from truestill_app.service.fs_browse import _ERROR_DETAIL_LIMIT, fs_create
from truestill_core.catalog import Catalog


def test_library_status_is_honest_when_empty(client: TestClient) -> None:
    s = client.get("/api/library/status").json()
    assert set(s) == {
        "library_path",
        # Where the user SAID the library lives, and whether they have been asked - `(abx)`,
        # 2026-08-12. Two flat keys beside `library_path` rather than one nested object, because
        # they answer different questions from different sources: `library_path` is OBSERVED
        # (written after a run, cleared when unreachable) and `library_root` is DECLARED (stated
        # once, never auto-cleared). Folding them together would lose exactly the distinction the
        # entry exists for. `needs_library_root` is the gate - no declaration AND no files -
        # computed here so the rule has one home rather than being re-derived in the browser.
        "library_root",
        "needs_library_root",
        "backup_path",
        "files",
        "photos",
        "videos",
        "audio",
        "by_format",
        "places",
        # The AGE of the custody claim, added 2026-08-10 for `(abg)`. Not new tracking:
        # `last_verified` has been on `drives` all along and is already shown per drive; these
        # two carry it to the number a person reads. `custody_checked_at` is the OLDEST check
        # across the places counted and is None when any of them has never been checked, in
        # which case `never_checked_drives` NAMES them - no date would be true of the whole
        # claim, and the name is the only clue to what happened.
        "custody_checked_at",
        "never_checked_drives",
        # The CONSEQUENCE of that age, added 2026-08-19 for `(abg)` Stage 3. `custody_dated_at`
        # is the oldest check across the drives that HAVE one and, unlike `custody_checked_at`
        # above, a never-checked drive does not blank it: the two answer different questions,
        # and without the second a library with one unchecked place could say nothing at all
        # about its other places. `custody_tier` is fresh/softening/stale from that date, decided
        # in core so the two surfaces cannot hold different thresholds.
        "custody_dated_at",
        "custody_dated_days",
        "custody_tier",
        "single_copy",
        # Per-file custody, added 2026-08-05. `places` counts DRIVES and stays for callers that
        # want it, but no sentence about files may be written against it again.
        "files_no_copy",
        "files_one_copy",
        "redundancy_floor",
        # Files that HAVE a copy, and the weakest of those. The rail reports on these; a file
        # with no copy at all is a Stats finding and must not drag the rail's floor to zero.
        "files_on_a_drive",
        "held_floor",
        "bytes",
        "catalog_path",
        "catalog_presence",
        "catalog_detail",
        "catalog_tone",
    }
    assert s["photos"] == 0
    assert s["videos"] == 0
    assert s["places"] == 0  # honest zero -> never a fake count
    # An empty library has no exposed files and no redundancy to claim; the strip reads
    # "nothing organized yet" rather than reassuring about nothing.
    assert s["files_no_copy"] == 0
    assert s["files_one_copy"] == 0
    assert s["redundancy_floor"] == 0
    assert s["files_on_a_drive"] == 0
    assert s["held_floor"] == 0
    assert s["catalog_path"].endswith("c.sqlite")
    assert s["catalog_presence"] in ("will_create", "empty")  # created on open may flip
    assert "error" not in (s.get("catalog_detail") or "").lower()


def test_library_status_empty_with_drives_is_alert(client: TestClient, tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="D1", label="Cabinet")
    s = client.get("/api/library/status").json()
    assert s["catalog_presence"] == "empty_with_drives"
    assert s["catalog_tone"] == "alert"
    assert "0 files but 1 drive" in s["catalog_detail"]
    assert s["files"] == 0


def _seed_media(db: Path) -> None:
    from truestill_core.catalog import Catalog  # noqa: PLC0415 - test-local

    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="D1", label="BackupA")
        rows = [
            ("IMG_1.jpg", "Camera/2023/08/IMG_1.jpg"),
            ("IMG_2.heic", "Camera/2023/08/IMG_2.heic"),
            ("VID_1.mp4", "Camera/2023/08/VID_1.mp4"),
        ]
        for i, (name, rel) in enumerate(rows):
            sha = f"{i:064x}"
            catalog.record_uploaded(
                source_path=f"/src/{name}",
                original_name=name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=1000,
                captured_at=None,
                category="Camera",
                relative=rel,
                drive_uuid="D1",
            )


def test_library_status_splits_photos_and_videos(client: TestClient, tmp_path: Path) -> None:
    _seed_media(tmp_path / "c.sqlite")
    s = client.get("/api/library/status").json()
    assert s["photos"] == 2  # jpg + heic
    assert s["videos"] == 1  # mp4
    assert s["by_format"]["photos"] == {"jpg": 1, "heic": 1}
    assert s["by_format"]["videos"] == {"mp4": 1}


def test_drives_split_photos_and_videos(client: TestClient, tmp_path: Path) -> None:
    _seed_media(tmp_path / "c.sqlite")
    payload = client.get("/api/drives").json()
    assert set(payload) == {"drives", "at_risk"}
    drives = payload["drives"]
    assert len(drives) == 1
    assert set(drives[0]) == {
        "label",
        "uuid",
        "files",
        "photos",
        "videos",
        "audio",
        "size",
        "last_seen",
        "last_verified",
        "path",
        "reach",
        # Added 2026-08-09 with the drive card's decisions lines. ONE nested field rather than
        # five flat ones, so this contract grows by a single key and a consumer that does not
        # care about decisions is unchanged.
        "decisions",
        # Added 2026-08-11 - `(abg)` Stage 2. Copies recorded here that a check looked for and
        # did not find, and when. Two flat keys rather than one nested field, unlike `decisions`
        # above: a count and its date are a single fact read together on one line, and nesting
        # them would put a `.length` between the card and the number it prints.
        "not_found",
        "not_found_at",
    }
    assert drives[0]["photos"] == 2
    assert drives[0]["videos"] == 1
    assert set(payload["at_risk"][0]) == {"name", "drive"}


def test_fs_dirs_returns_roots_when_no_path(client: TestClient) -> None:
    data = client.get("/api/fs/dirs").json()
    assert set(data) == {"path", "parent", "roots", "entries"}
    assert any(r["label"] == "Home" for r in data["roots"])
    assert data["entries"] == []


def test_fs_dirs_lists_subdirectories(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "sub-a").mkdir()
    (tmp_path / "sub-b").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    data = client.get("/api/fs/dirs", params={"path": str(tmp_path)}).json()
    assert set(data) == {"path", "parent", "roots", "entries"}
    names = [e["name"] for e in data["entries"]]
    assert names == ["sub-a", "sub-b"]  # dirs only, hidden excluded, sorted


def test_fs_validate_counts_media(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.mp4").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")
    v = client.get("/api/fs/validate", params={"path": str(tmp_path)}).json()
    assert set(v) == {
        "exists",
        "is_dir",
        "readable",
        "writable",
        "is_drive",
        "media",
        "media_capped",
        "unreadable",
    }
    assert v["is_dir"] is True
    assert v["media"] == 2  # jpg + mp4, not the txt


def test_fs_validate_missing_path(client: TestClient, tmp_path: Path) -> None:
    v = client.get("/api/fs/validate", params={"path": str(tmp_path / "nope")}).json()
    # resolve() succeeds for a missing leaf; the full resolved key set is returned with exists=False.
    assert set(v) == {
        "exists",
        "is_dir",
        "readable",
        "writable",
        "is_drive",
        "media",
        "media_capped",
        "unreadable",
    }
    assert v["exists"] is False
    assert v["media"] == 0


def test_fs_create_makes_a_new_backup_folder(client: TestClient, tmp_path: Path) -> None:
    target = tmp_path / "new" / "BackupA"  # a nested, not-yet-existing destination
    r = client.post("/api/fs/create", json={"path": str(target)}).json()
    assert set(r) == {
        "created",
        "exists",
        "is_dir",
        "readable",
        "writable",
        "is_drive",
        "media",
        "media_capped",
        "unreadable",
    }
    assert r["created"] is True
    assert r["is_dir"] is True
    assert r["writable"] is True
    assert target.is_dir()


def test_clean_empty_preview_and_apply_key_sets(client: TestClient, tmp_path: Path) -> None:
    """Empty-folder cleanup JSON shape for the post-move offer (shared with completion cards)."""
    root = tmp_path / "drive"
    (root / "Camera" / "2013" / "09").mkdir(parents=True)
    emptied = ["Camera/2013/09", "Camera/2013", "Camera"]

    preview = client.post(
        "/api/clean-empty/preview", json={"path": str(root), "emptied": emptied}
    ).json()
    assert set(preview) == {"ok", "path", "backend", "removable", "occupied"}
    assert preview["ok"] is True
    assert "Camera/2013/09" in preview["removable"]

    applied = client.post(
        "/api/clean-empty/apply", json={"path": str(root), "emptied": emptied}
    ).json()
    assert set(applied) == {"ok", "path", "removed", "trashed", "deleted", "failures"}
    assert applied["ok"] is True
    # Removal may trash, delete, or fail (gio trash often refuses under /tmp); key set is the pin.
    assert isinstance(applied["removed"], int)
    assert isinstance(applied["failures"], list)


def _a_path_that_cannot_be_created(tmp_path: Path, long_name: str) -> Path:
    """A path whose creation must fail: a long child of a plain **file**.

    The obstacle is the file, never the length. Which component the OS names in the resulting
    error differs by platform - see :func:`_mkdir_failure` - and no assertion below depends on
    it. Shared by the three tests that follow so the only thing that differs between them is
    their subject.
    """
    obstacle = tmp_path / "not-a-dir"
    obstacle.write_bytes(b"x")
    return obstacle / long_name / "leaf"


def _mkdir_failure(target: Path) -> OSError:
    """The `OSError` **this platform** raises for ``target`` - read here, never predicted.

    `ENGINEERING_STANDARD.md` §4, thirty-ninth member: *a test whose subject is an OS-produced
    string is a test of that OS.* The tests below are about what `fs_create` does **to** such a
    string, so the string is an input to be measured rather than a marker to plant in the path
    and look for afterwards.

    **The divergence this exists for, because it cost a red Windows lane** (CI run 31626239285,
    2026-08-12). `Path.mkdir(parents=True)` raises from a *different node of its own recursion*
    per platform. POSIX fails the first `os.mkdir` with `ENOTDIR` - not a `FileNotFoundError`, so
    pathlib re-raises immediately and the message names the **whole** path, long leaf included.
    Windows returns `ERROR_PATH_NOT_FOUND` for that same call, which **is** a
    `FileNotFoundError`, so pathlib recurses upward and finally fails at the obstacle itself with
    `[WinError 183] Cannot create a file when that file already exists` - naming only the parent.
    The leaf is absent from the Windows string entirely. Both are correct; neither is ours.
    """
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        assert not target.exists(), "the probe created the path it was supposed to fail on"
        return exc
    pytest.fail(f"{target} was created - the fixture no longer reproduces a failure")


def test_a_create_failure_is_bounded_for_the_slot_it_lands_in(tmp_path: Path) -> None:
    """`(acw)`. The message goes into a hint span **above a button**, so an unbounded string there
    is a layout defect: two wrapped lines moved `#bk-preview` past the point a centre-aimed click
    leaves it. `str(OSError)` embeds the offending path, which has no length limit at all.

    The bound is on the layout, never on the information - see the next test.
    """
    result = fs_create(str(_a_path_that_cannot_be_created(tmp_path, "a" * 180)))

    assert result["created"] is False
    reason = result["error"].split("(", 1)[1].rsplit(")", 1)[0]
    assert len(reason) <= _ERROR_DETAIL_LIMIT, f"{len(reason)} chars reached the hint: {reason!r}"


def test_the_full_failure_is_still_delivered_beside_the_bounded_one(tmp_path: Path) -> None:
    """**THE CRY-WOLF HALF, and the one that matters most here.** An error truncated into
    unreadability trades a click-miss for an unusable message. `error_detail` carries the
    untruncated failure - the caller puts it in `title` - so the bound costs no information.

    **`error_detail == str(exc)` verbatim is strictly stronger than the marker this used to look
    for.** A truncation that happened to retain a planted 180-character name would satisfy the
    old form; only equality with the platform's own failure says *untruncated*. It is also the
    reason the test now passes on Windows, where the OS never mentions the marker at all.
    """
    target = _a_path_that_cannot_be_created(tmp_path, "b" * 180)
    failure = str(_mkdir_failure(target))
    assert len(failure) > _ERROR_DETAIL_LIMIT, (
        f"the fixture no longer produces a boundable failure ({len(failure)} chars): {failure!r}"
    )

    result = fs_create(str(target))

    assert result["created"] is False
    assert result["error_detail"] == failure, "the untruncated failure did not survive"
    reason = result["error"].split("(", 1)[1].rsplit(")", 1)[0]
    assert len(reason) < len(failure), "nothing was bounded here, so this proves nothing"
    assert failure not in result["error"], "the bounded message is not actually bounded"


def test_the_bounded_message_keeps_the_end_of_the_path(tmp_path: Path) -> None:
    """The tail identifies the folder; the head is a prefix the user typed and already knows.

    **The subject is which end of the failure we keep, not what the failure says.** Asserted
    against the platform's own string, so it holds wherever the OS chose to point.
    """
    target = _a_path_that_cannot_be_created(tmp_path, "c" * 180)
    failure = str(_mkdir_failure(target))
    assert len(failure) > _ERROR_DETAIL_LIMIT, (
        f"the fixture no longer produces a boundable failure ({len(failure)} chars): {failure!r}"
    )

    result = fs_create(str(target))

    assert result["created"] is False
    reason = result["error"].split("(", 1)[1].rsplit(")", 1)[0]
    kept = reason.removeprefix("...")
    assert kept, "nothing of the failure reached the message at all"
    assert failure.endswith(kept), "the bounded message is not the END of the failure"
    # The cry-wolf half, naming the implementation this must reject: a head-keeping bound
    # (`failure[:57] + "..."`). The old assertion could only tell the two apart because the
    # planted leaf happened to sit at the end of a POSIX error - an accident of the platform,
    # not a property of the code.
    assert not failure.startswith(kept), "the head was kept - the tail is what identifies it"


#: Real `str(OSError)` renderings, one per platform, recorded rather than composed. The Windows
#: line is the exact string from the failure this repair closes (CI run 31626239285, job
#: `check (windows-latest)`, 2026-08-12); the POSIX line is from the same fixture on Linux.
#:
#: **They are what makes the shape difference visible on one lane.** `make check` runs on the
#: developer's OS, so a bound that silently depended on POSIX punctuation - splitting on `/`, or
#: assuming a trailing quoted `/`-separated tail - would stay green here and break on Windows.
_RECORDED_FAILURES = {
    "posix": ("[Errno 20] Not a directory: '/tmp/tmp8leyu38h/not-a-dir/" + "b" * 180 + "/leaf'"),
    "windows": (
        "[WinError 183] Cannot create a file when that file already exists: "
        r"'C:\Users\runneradmin\AppData\Local\Temp\pytest-of-runneradmin\pytest-0"
        r"\popen-gw0\test_the_full_failure_is_still0\not-a-dir'"
    ),
}


class _RecordedFailureError(OSError):
    """An `OSError` whose ``str()`` is one a real platform really produced.

    Constructing a `[WinError 183]` rendering is not possible off Windows - ``winerror`` is set
    by the OS - so the rendering is carried rather than rebuilt. Overriding ``__str__`` is the
    whole trick, because `_short_reason` reads exactly that and nothing else.
    """

    def __init__(self, rendered: str) -> None:
        super().__init__(rendered)
        self._rendered = rendered

    def __str__(self) -> str:
        return self._rendered


@pytest.mark.parametrize("platform", sorted(_RECORDED_FAILURES))
def test_the_bound_holds_for_either_platform_s_error_shape(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    """The contract, against both real error shapes, on whichever lane is running.

    **What this does and does not detect, stated so it is not read as more than it is.** It does
    **not** catch the defect that produced it - that was a *test* asserting an OS string, and a
    correct implementation passes this either way. It catches the next one: a change to
    `_short_reason` that is right about POSIX punctuation and wrong about a Windows path. That
    class currently has no detector outside the Windows lane, which is a 14-minute round trip.

    Patched on `Path`, the module that owns ``mkdir``, never on a re-export - §4, third member.
    """
    failure = _RECORDED_FAILURES[platform]

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise _RecordedFailureError(failure)

    monkeypatch.setattr(Path, "mkdir", _raise)

    result = fs_create("/anywhere/at/all")

    assert result["created"] is False
    assert result["error_detail"] == failure, "the untruncated failure did not survive"
    reason = result["error"].split("(", 1)[1].rsplit(")", 1)[0]
    assert len(reason) <= _ERROR_DETAIL_LIMIT, f"{len(reason)} chars reached the hint: {reason!r}"
    assert failure.endswith(reason.removeprefix("...")), "the bound did not keep the END"
