"""Server security + endpoints via Starlette's TestClient."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from app_support import TOKEN
from starlette.testclient import TestClient
from truestill_app import __version__, server
from truestill_app.server import create_app
from truestill_core.catalog import Catalog


def test_missing_token_is_rejected(tmp_path: Path) -> None:
    """Built token-less on purpose, rather than leaning on a fixture that forgot the header.

    This used to depend on this module's private `client` fixture silently omitting
    `x-truestill-token` - one of the two drifted copies the shared fixture replaced (audit F28).
    A security assertion that passes because of an omission somewhere else is one edit away from
    passing for no reason at all.
    """
    app = create_app(token=TOKEN, db=tmp_path / "c.sqlite")
    tokenless = TestClient(app, headers={"host": "127.0.0.1:7357"})
    assert tokenless.get("/api/drives").status_code == 403


def test_bad_host_is_rejected(tmp_path: Path) -> None:
    app = create_app(token=TOKEN, db=tmp_path / "c.sqlite")
    evil = TestClient(app, headers={"host": "evil.example.com"})
    assert evil.get(f"/api/drives?token={TOKEN}").status_code == 421


def test_cross_origin_is_rejected(client: TestClient) -> None:
    r = client.get(f"/api/drives?token={TOKEN}", headers={"origin": "http://evil.example.com"})
    assert r.status_code == 403


def test_static_is_exempt_from_token(client: TestClient) -> None:
    # An asset the page actually links -- a test pointing at an orphan file would keep the
    # orphan alive and stop proving the exemption works for anything real.
    assert client.get("/static/app.css").status_code == 200


def test_home_shows_the_real_version(client: TestClient) -> None:
    """The Settings footer must carry the installed version, not an unsubstituted template
    placeholder -- a version a user can read is the point of putting it there."""
    body = client.get(f"/?token={TOKEN}").text
    assert f"truestill {__version__}" in body
    assert "{{VERSION}}" not in body


def test_home_serves_and_injects_token(client: TestClient) -> None:
    r = client.get(f"/?token={TOKEN}")
    assert r.status_code == 200
    assert TOKEN in r.text
    assert "{{TOKEN}}" not in r.text  # placeholder was replaced


def test_stale_static_assets_render_a_restart_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Found for real: a long-running process kept serving an old backend while its own
    templates/app.js changed underneath it on disk - no cards, no error, nothing to say a
    restart was overdue. `home()` now fingerprints its own served files at process start and
    on every request; a mismatch means this process is stale, and it says so on the page
    itself (server-rendered, not JS - visible even if the frontend never runs at all).
    """
    templates = tmp_path / "templates"
    static = tmp_path / "static"
    templates.mkdir()
    static.mkdir()
    templates_html = "<html>{{TOKEN}}{{VERSION}}{{STALE_WARNING}}</html>"
    (templates / "index.html").write_text(templates_html)
    (static / "app.js").write_text("console.log(1);")
    monkeypatch.setattr(server, "_TEMPLATES", templates)
    monkeypatch.setattr(server, "_STATIC", static)

    app = create_app(token=TOKEN, db=tmp_path / "c.sqlite")
    fresh_client = TestClient(app, headers={"host": "127.0.0.1:7357"})
    fresh = fresh_client.get(f"/?token={TOKEN}").text
    assert "needs a restart" not in fresh

    # The files this same running app would serve change on disk - exactly what a git pull or
    # a redeploy does while the process keeps running its already-imported code.
    (static / "app.js").write_text("console.log(2); // a real change, not this process's")
    stale = fresh_client.get(f"/?token={TOKEN}").text
    assert "needs a restart" in stale


def test_drives_and_where_empty(client: TestClient) -> None:
    drives = client.get(f"/api/drives?token={TOKEN}").json()
    assert drives == {"drives": [], "at_risk": []}
    where = client.get(f"/api/where?token={TOKEN}&term=x").json()
    assert set(where) == {"copies", "total", "page", "pages", "page_size"}
    assert where["copies"] == []
    assert where["total"] == 0
    assert where["pages"] == 1  # an empty result is still "page 1 of 1", never "of 0"


def test_library_stats_reports_custody_and_shape(client: TestClient, tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        catalog.upsert_drive(uuid="B", label="Drive B")
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256="sha-a",
            copy_sha256="sha-a",
            perceptual="phash-1",
            size=100,
            captured_at="2020-01-01T10:00:00",
            category="Camera",
            relative="2020/2020-01/a.jpg",
            drive_uuid="A",
        )
        catalog.record_uploaded(
            source_path="/src/b.mp4",
            original_name="b.mp4",
            sha256="sha-b",
            copy_sha256="sha-b",
            perceptual="phash-1",
            size=200,
            captured_at="2021-01-01T10:00:00",
            category="Camera",
            relative="2021/2021-01/b.mp4",
            drive_uuid="A",
        )
        catalog.record_uploaded(
            source_path="/src/c.jpg",
            original_name="c.jpg",
            sha256="sha-c",
            copy_sha256="sha-c",
            perceptual=None,
            size=300,
            captured_at=None,
            category="Saved",
            relative="Saved/Undated/c.jpg",
            drive_uuid=None,
        )
        catalog.record_copy(
            sha256="sha-a",
            drive_uuid="B",
            relative="2020/2020-01/a.jpg",
            copy_sha256="sha-a",
            size=100,
        )
        catalog.mark_copy_verified(sha256="sha-a", drive_uuid="A", when="2026-07-30T10:00:00")
        catalog.set_drive_verified("A", "2026-07-30T10:00:00")

    body = client.get(f"/api/library/stats?token={TOKEN}").json()
    assert set(body) == {"safety", "completeness", "shape", "dates", "complexity"}
    assert set(body["safety"]) == {
        "total_files",
        "total_size",
        "photos",
        "videos",
        "audio",
        "files_on_two_plus_drives",
        "files_on_one_drive",
        "files_on_zero_drives",
        "zero_drive_samples",
        "never_verified_files",
        "drives",
    }
    assert set(body["completeness"]) == {
        "undated_files",
        "undated_samples",
        "timeline_files",
        "side_bin_files",
        "near_duplicates_flagged",
        "exact_duplicates_found",
        "exact_duplicates_omission_reason",
    }
    assert set(body["shape"]) == {"by_year", "by_format", "oldest_capture", "newest_capture"}
    assert body["safety"]["photos"] == 2
    assert body["safety"]["videos"] == 1
    assert body["safety"]["total_size"] == 600
    assert body["safety"]["files_on_two_plus_drives"] == 1
    assert body["safety"]["files_on_one_drive"] == 1
    assert body["safety"]["files_on_zero_drives"] == 1
    assert body["completeness"]["undated_files"] == 1
    assert body["completeness"]["timeline_files"] == 2
    assert body["completeness"]["side_bin_files"] == 1
    assert body["shape"]["oldest_capture"] == "2020-01-01T10:00:00"
    assert body["shape"]["newest_capture"] == "2021-01-01T10:00:00"
    assert body["shape"]["by_year"] == [{"year": "2020", "count": 1}, {"year": "2021", "count": 1}]
    assert body["shape"]["by_format"]["jpg"] == 2
    assert body["shape"]["by_format"]["mp4"] == 1
    assert body["completeness"]["near_duplicates_flagged"] == 2
    assert body["completeness"]["exact_duplicates_found"] is None


def test_organize_preview_no_media(client: TestClient, tmp_path: Path) -> None:
    src = tmp_path / "empty"
    src.mkdir()
    started = client.post(
        f"/api/organize/preview?token={TOKEN}",
        json={"source": str(src), "destination": str(tmp_path / "out")},
    )
    assert started.status_code == 200
    done = _stream_to_done(client, started.json()["job_id"])
    assert done["type"] == "done"
    summary = done.get("summary") or done
    assert set(summary) == {
        "tier",
        "files",
        "folders",
        "skipped",
        "unreadable_folders",
        "mode",
        "mechanism",
        "elapsed_seconds",
    }
    assert summary["files"] == 0
    # "no media found" must never be the whole answer when a folder could not be opened - the
    # reason would be indistinguishable from an empty source. Empty here, and honestly so.
    assert summary["unreadable_folders"] == []
    assert summary["tier"] == "dedup"


def test_organize_mode_setting_round_trips_through_catalog(client: TestClient) -> None:
    state = client.get(f"/api/organize/settings?token={TOKEN}").json()
    assert set(state) == {"mode", "modes"}
    assert state["mode"] == "copy"
    saved = client.post(f"/api/organize/settings?token={TOKEN}", json={"mode": "inplace"}).json()
    assert set(saved) == {"ok", "mode"}
    assert saved == {"ok": True, "mode": "inplace"}
    assert client.get(f"/api/organize/settings?token={TOKEN}").json()["mode"] == "inplace"


def test_sidebar_collapsed_setting_round_trips_through_catalog(client: TestClient) -> None:
    state = client.get(f"/api/sidebar/settings?token={TOKEN}").json()
    assert set(state) == {"collapsed"}
    assert state["collapsed"] is False
    saved = client.post(f"/api/sidebar/settings?token={TOKEN}", json={"collapsed": True}).json()
    assert set(saved) == {"ok", "collapsed"}
    assert saved == {"ok": True, "collapsed": True}
    assert client.get(f"/api/sidebar/settings?token={TOKEN}").json()["collapsed"] is True
    restored = client.post(f"/api/sidebar/settings?token={TOKEN}", json={"collapsed": False}).json()
    assert restored == {"ok": True, "collapsed": False}


def test_filesystem_relationship_reports_same_filesystem(
    client: TestClient, tmp_path: Path
) -> None:
    source = tmp_path / "src"
    destination = tmp_path / "dest"
    source.mkdir()
    destination.mkdir()
    body = client.get(
        "/api/fs/relationship",
        params={"token": TOKEN, "source": str(source), "destination": str(destination)},
    ).json()
    assert set(body) == {"ok", "same_filesystem"}
    assert body["ok"] is True
    assert body["same_filesystem"] is True


def test_organize_inventory_is_sync_and_cheap(client: TestClient, tmp_path: Path) -> None:
    """Inventory is not a job: the response is the summary, with no SSE and no destination."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"one")
    (src / "b.mp4").write_bytes(b"videodata")
    (src / "c.pdf").write_bytes(b"%PDF")

    r = client.post(f"/api/organize/inventory?token={TOKEN}", json={"source": str(src)})
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "inventory"
    assert body["files"] == 2
    assert body["photos"] == 1
    assert body["videos"] == 1
    assert body["total_bytes"] == 3 + 9
    assert body["skipped"]["documents"] == {".pdf": 1}
    assert "job_id" not in body


def test_preview_is_a_job_that_still_writes_nothing(client: TestClient, tmp_path: Path) -> None:
    """Preview moved onto the job/SSE path so it can show progress. It is still a dry run:
    the whole point of the conversion was *how* the answer arrives, not what it costs."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"preview-bytes-one")
    (src / "b.jpg").write_bytes(b"preview-bytes-two")
    out = tmp_path / "out"

    started = client.post(
        f"/api/organize/preview?token={TOKEN}",
        json={"source": str(src), "destination": str(out)},
    )
    done = _stream_to_done(client, started.json()["job_id"])
    summary = done.get("summary") or done

    assert set(summary) >= {
        "tier",
        "files",
        "photos",
        "videos",
        "audio",
        "by_format",
        "new_unique",
        "near_dup",
        "exact_dup",
        "undated",
        "sentinel_rejected",
        "suspect_default",
        "inferred_local_shifts",
        "folders",
        "destination_is_drive",
        "skipped",
        "mode",
        "mechanism",
        "elapsed_seconds",
    }
    assert summary["files"] == 2
    assert not out.exists()  # nothing written to the destination
    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert catalog.count() == 0  # and nothing recorded in the catalog


def test_verify_job_streams_error_for_non_drive(client: TestClient, tmp_path: Path) -> None:
    """A verify on a path with no marker soft-fails immediately with a correction payload.

    Mutation: starting a job that errors over SSE would put ``job_id`` in the body.
    """
    started = client.post(f"/api/verify/run?token={TOKEN}", json={"path": str(tmp_path / "nope")})
    body = started.json()
    assert body["ok"] is False
    assert "job_id" not in body
    assert "Can't reach" in body["error"] or "isn't set up as a backup drive" in body["error"]


def _stream_to_done(client: TestClient, job_id: str) -> dict:
    """Collect a job's SSE stream and return the terminal (done/error) event."""
    events = []
    with client.stream("GET", f"/api/jobs/{job_id}/events?token={TOKEN}") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
                if events[-1]["type"] in ("done", "error"):
                    break
    return events[-1]


def test_organize_run_summary_matches_files_on_disk(client: TestClient, tmp_path: Path) -> None:
    """Regression for the 'Done / nothing to do' blocker.

    The UI reads the run outcome as ``(d.summary || d).outcomes`` (same shape Verify/Migrate use).
    This pins that contract: the organize done-event must carry ``summary.outcomes`` whose counts
    equal what actually landed on disk -- so a successful run can never report "nothing to do".
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"first-unique-bytes")
    (src / "b.jpg").write_bytes(b"second-unique-bytes")
    out = tmp_path / "out"

    started = client.post(
        f"/api/organize/run?token={TOKEN}",
        json={"source": str(src), "destination": str(out), "skip_undated": False},
    )
    done = _stream_to_done(client, started.json()["job_id"])

    assert done["type"] == "done"
    # The frontend unwraps the target's return from under ``summary`` (jobs.py contract).
    summary = done.get("summary") or done
    assert summary.get("organized"), (
        "organize done-event must report what it organized (else 'nothing to do')"
    )
    assert set(summary) >= {
        "outcomes",
        "organized",
        "photos",
        "videos",
        "audio",
        "bytes_organized",
        "duplicates",
        "bytes_saved",
        "near_dup",
        "bytes_near_dup",
        "folders",
        "oldest",
        "newest",
        "moved_in_place",
        "moved_by_copy",
        "failed",
        "mode",
        "mechanism",
        "drive_label",
        "single_copy",
        "elapsed_seconds",
    }
    assert set(summary["mechanism"]) == {
        "same_filesystem",
        "reversible",
        "uses_rename",
        "requires_destination",
    }

    # The drive marker is truestill's own bookkeeping, not an organized photo.
    files_on_disk = [p for p in out.rglob("*") if p.is_file() and p.name != ".truestill-drive.json"]
    assert summary["organized"] == len(files_on_disk) == 2  # summary == on-disk reality
    assert summary["bytes_organized"] == sum(p.stat().st_size for p in files_on_disk)
    # "uploaded" is backend vocabulary for something that did not happen on a local disk.
    assert "uploaded" not in json.dumps(summary)


def test_terminal_job_events_are_normalized_before_any_handler_sees_them(
    client: TestClient,
) -> None:
    """Guard two blockers at once, both caused by handlers reading raw terminal events.

    A completion carries ``summary``; a failure carries ``message``. Handlers used to read
    ``summary.outcomes`` (which a failure lacks -> "Done / nothing to do") and ``summary.error``
    (which a failure also lacks -> ``nfmt(undefined)`` rendering as **NaN**). streamJob now
    hands every handler one shape, so neither mistake is reachable. No JS runtime here, so the
    contract is pinned in source.
    """
    app_js = client.get(f"/static/app.js?token={TOKEN}").text
    assert "ok: !failed" in app_js  # streamJob normalizes before calling back
    assert "d.summary || d" not in app_js  # no handler reads the raw event any more
    assert "s.error" not in app_js  # nor the field a failure never has
    assert "jobErrorCard" in app_js  # failures render through one shared path


def test_a_non_drive_verify_is_answered_with_a_next_step(
    client: TestClient, tmp_path: Path
) -> None:
    """Checking an ordinary folder must not start a job that dies with NaN tallies.

    Soft-fails immediately with the drive-correction payload (same shape as migration), so the
    UI can offer the next step without waiting on SSE. Mutation: returning a JobTarget that
    raises NotABackupDriveError mid-job would make ``started.json()["job_id"]`` succeed and
    this assertion fail.
    """
    plain = tmp_path / "not-a-drive"
    plain.mkdir()
    started = client.post(f"/api/verify/run?token={TOKEN}", json={"path": str(plain)})
    body = started.json()

    assert body.get("ok") is False
    assert "job_id" not in body
    assert "isn't set up as a backup drive" in body["error"]
    assert "Copy photos here once" in body["error"] or "register this drive" in body["error"]
    assert body["can_register"] is True
    assert body["suggested_root"] is None

    app_js = client.get(f"/static/app.js?token={TOKEN}").text
    assert "startRefusedCard" in app_js  # soft-fail path renders a card, not NaN tallies
    assert "Copy your library to another drive" in app_js  # and names the next step
    assert "What happened:" not in app_js  # 3-part structure is a writing guide, not labels
    assert "What to do:" not in app_js


def test_no_backend_jargon_reaches_the_user(client: TestClient) -> None:
    """ "Uploaded" describes an event that does not happen on a local disk, and contradicts the
    promise that files never leave the machine. It is honest inside the code -- `Destination`
    covers rclone remotes -- but it must never be rendered. Guards the whole visible surface."""
    page = client.get(f"/?token={TOKEN}").text
    app_js = client.get(f"/static/app.js?token={TOKEN}").text
    for banned in ("uploaded", "Uploaded", "upload"):
        assert banned not in page, f"{banned!r} is visible in the page"
        assert banned not in app_js, f"{banned!r} is visible in the app script"


def test_dark_theme_toggle_defines_every_media_dark_token(client: TestClient) -> None:
    """Guard the dark-mode contrast fix: the ``[data-theme="dark"]`` toggle block must define every
    token the ``@media (prefers-color-scheme: dark)`` block does. A token omitted from the toggle
    falls back to the light :root default -- which is exactly how the amber warning banners once
    rendered light-on-light when a user toggled dark. Keeps the two dark palettes from drifting."""
    css = client.get(f"/static/tokens.css?token={TOKEN}").text
    media = re.search(r"@media \(prefers-color-scheme: dark\).*?:root\s*\{(.*?)\}", css, re.S)
    toggle = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\}', css, re.S)
    assert media is not None
    assert toggle is not None
    media_tokens = set(re.findall(r"(--[\w-]+):", media.group(1)))
    toggle_tokens = set(re.findall(r"(--[\w-]+):", toggle.group(1)))
    missing = media_tokens - toggle_tokens
    assert not missing, f"[data-theme=dark] is missing tokens (fall back to light): {missing}"


def test_catalog_db_is_created(client: TestClient, tmp_path: Path) -> None:
    client.get(f"/api/drives?token={TOKEN}")  # opening the catalog creates it
    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert catalog.schema_version >= 6


def test_the_two_backup_drive_fields_share_what_the_user_typed(client: TestClient) -> None:
    """Within the Backups page, "Drive folder" and "To" name the same thing: the backup drive.

    Typing it in one offers it to the other. Two properties make that safe rather than
    presumptuous, and both are pinned here because getting either wrong is worse than the
    duplication it replaces:

    * only *user* input carries across -- `prefill` assigns without dispatching, and the Check
      field is prefilled with the **library** path when no backup exists, so reacting to
      programmatic fills would silently propose copying the library onto itself;
    * a field the user has already filled is never overwritten.
    """
    app_js = client.get(f"/static/app.js?token={TOKEN}").text

    assert '["verify-path", "bk-target"]' in app_js  # the two backup-drive fields, and only those
    assert "bk-source" not in app_js.split("BACKUP_DRIVE_FIELDS =")[1].split("]")[0]
    assert "if (!el || el.value.trim()) continue" in app_js  # never clobbers a typed value
    # Carried values are labelled, and the label clears once the user makes the value theirs.
    page = client.get(f"/?token={TOKEN}").text
    assert 'id="bk-target-carried"' in page
    assert 'id="verify-path-carried"' in page


def _seed_matches(db: Path, n: int) -> None:
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        for i in range(n):
            catalog.record_uploaded(
                source_path=f"/src/holiday{i:04d}.jpg",
                original_name=f"holiday{i:04d}.jpg",
                sha256=f"sha-{i}",
                copy_sha256=f"sha-{i}",
                perceptual=None,
                size=10,
                captured_at="2021-06-15T10:30:00",
                category="Camera",
                relative=f"2021/2021-06/holiday{i:04d}.jpg",
                event_id=None,
                albums=[],
                drive_uuid="D1",
            )


def test_find_pages_results_and_reports_the_total(client: TestClient, tmp_path: Path) -> None:
    """A page of results, and an honest count of what is not on it."""
    _seed_matches(tmp_path / "c.sqlite", 120)

    first = client.get(f"/api/where?token={TOKEN}&term=holiday").json()

    assert set(first) == {"copies", "total", "page", "pages", "page_size"}
    assert set(first["copies"][0]) == {"name", "drive", "relative", "last_verified"}
    assert first["total"] == 120
    assert first["page"] == 1
    assert first["pages"] == 3  # 120 over a page size of 50
    assert len(first["copies"]) == first["page_size"] == 50


def test_find_pages_do_not_overlap_or_lose_a_row(client: TestClient, tmp_path: Path) -> None:
    """The off-by-one that pagination exists to introduce, pinned closed."""
    _seed_matches(tmp_path / "c.sqlite", 120)

    seen: list[str] = []
    for page in (1, 2, 3):
        body = client.get(f"/api/where?token={TOKEN}&term=holiday&page={page}").json()
        seen += [c["name"] for c in body["copies"]]

    assert len(seen) == 120
    assert len(set(seen)) == 120  # every row exactly once, none repeated across a boundary
    assert client.get(f"/api/where?token={TOKEN}&term=holiday&page=4").json()["copies"] == []


def test_a_page_is_fetched_from_the_database_not_sliced_in_python(tmp_path: Path) -> None:
    """The property that makes paging worth having at all.

    Fetching every match and slicing would build the whole result set on each keystroke -- the
    shape that only hurts once a library is large, which is exactly when it matters. Asserted
    against the query plan of the SQL ``find_copies`` actually runs (via ``find_copies_query`` and
    a trace of the live execute), not a retyped literal that could drift (audit F11).
    """
    db = tmp_path / "c.sqlite"
    _seed_matches(db, 120)
    with Catalog(db) as catalog:
        sql, params = catalog.find_copies_query("holiday", limit=50, offset=0)
        assert "LIMIT ?" in sql
        assert "OFFSET ?" in sql

        plan = " ".join(
            str(r[3]) for r in catalog._conn.execute(f"EXPLAIN QUERY PLAN {sql}", params)
        )
        assert "USING INDEX" in plan, plan

        traced: list[str] = []
        catalog._conn.set_trace_callback(traced.append)
        assert len(catalog.find_copies("holiday", limit=50, offset=0)) == 50
        catalog._conn.set_trace_callback(None)
        assert any("LIMIT 50 OFFSET 0" in q for q in traced), traced
        assert len(catalog.find_copies("holiday")) == 120  # unpaged still available


def test_reveal_refuses_a_path_that_is_not_a_folder(client: TestClient, tmp_path: Path) -> None:
    """A path that cannot be opened says so, rather than pretending it worked."""
    r = client.post(f"/api/reveal?token={TOKEN}", json={"path": str(tmp_path / "nope")}).json()
    assert r["ok"] is False
    assert "error" in r
    assert "Can't reach" in r["error"]


def test_reveal_degrades_honestly_without_an_opener(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No file manager on this machine is a fact to report, not a button that no-ops.

    The message carries the path, so someone on a headless box can still act on it.
    """
    monkeypatch.setattr("truestill_app.service.drives.shutil.which", lambda _name: None)
    r = client.post(f"/api/reveal?token={TOKEN}", json={"path": str(tmp_path)}).json()

    assert set(r) == {"ok", "error"}
    assert r["ok"] is False
    assert str(tmp_path) in r["error"]
