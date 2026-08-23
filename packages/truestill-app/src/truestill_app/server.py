"""The Starlette application: routes, SSE, static assets, wired to the service + job manager.

The app is built by :func:`create_app`, which takes the session token so tests can construct it
directly. Every data route is guarded by :class:`~truestill_app.security.LocalGuard`.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from truestill_core.app_paths import default_catalog_path
from truestill_core.catalog_busy import (
    CATALOG_BUSY_CODE,
    CATALOG_BUSY_REQUEST_MESSAGE,
    is_catalog_busy,
)
from truestill_core.events import InvalidEventSettingsError
from truestill_core.layout import InvalidEverydayDaySettingsError
from truestill_core.trip_review import ReviewCard

from truestill_app import __version__, service
from truestill_app.jobs import DriveBusyPayload, JobManager, JobTarget
from truestill_app.security import LocalGuard


@dataclass(slots=True)
class EventReviewSession:
    """Mutable UI-only review state; persistence still happens only on explicit confirmation."""

    path: str
    cards: list[ReviewCard]
    day_totals: dict[date, int]
    min_files: int
    #: What the catalog had already named when this review opened. Merge and split rebuild cards
    #: without touching the catalog, so re-reading per action could answer the same question
    #: differently within one review; holding it on the session cannot drift.
    existing_names: service.ExistingNames | None = None
    #: Where the clustered files came from, read once when this review opened. Merge and split
    #: rebuild cards without touching the catalog, so re-reading per action would spend a full
    #: drive scan on every click and could answer differently mid-review.
    source_hints: service.SourceHints | None = None
    named_events: list[service.NamedEventSelection] = field(default_factory=list)
    named_trips: list[service.NamedTripSelection] = field(default_factory=list)


_PKG = Path(__file__).resolve().parent
_TEMPLATES = _PKG / "templates"
_STATIC = _PKG / "static"

#: Review sessions kept per process. See `remember_session` (audit F17).
MAX_REVIEW_SESSIONS = 32

_log = logging.getLogger(__name__)

_STALE_BANNER = (
    '<div class="banner warn"><div><div class="b-title">This server needs a restart</div>'
    "The app's own files on disk have changed since this process started, so the page you are "
    "looking at may not match what the running server actually does. Stop truestill-app and "
    "start it again to pick up the change.</div></div>"
)


def _static_fingerprint() -> str:
    """A content hash of the served page + script, read fresh from disk right now.

    `create_app` captures this once, at process start; `home` recomputes it on every request.
    A mismatch means the files on disk have changed since this process was started -- exactly
    the state that let a stale backend silently serve a fresh frontend a response shape it no
    longer understood (Stage 2d, 13.4's soak finding). This is a proxy, not a proof: it catches
    every case in this repo's own practice, where a user-facing change always ships its static
    assets and its backend in the same commit, but a backend-only change with no template/script
    diff would not move it. Flagged as a known, accepted gap rather than built around -- catching
    that case too would mean hashing the whole installed package on every request.
    """
    index_html = (_TEMPLATES / "index.html").read_bytes()
    app_js = (_STATIC / "app.js").read_bytes()
    return hashlib.sha256(index_html + app_js).hexdigest()


async def _catalog_busy_refusal(_request: Request, exc: Exception) -> JSONResponse:
    """A busy catalog is a refusal a person can act on, never a 500. `(agp)` part 1.

    ⚠ **Only busy is translated; everything else re-raises unchanged.** `is_catalog_busy` keys on
    SQLite's primary result code, so a genuine fault - a missing table, a corrupt file - keeps
    its 500 and its traceback rather than being dressed up as transient. Dressing a fault as
    busy would tell the user to retry something that will never succeed.

    **503 with `Retry-After`**, because that is what the condition is: the service is briefly
    unavailable and the honest remedy is trying again - which the sentence says in words and the
    header says to machines.
    """
    if not is_catalog_busy(exc):
        raise exc
    return JSONResponse(
        {"error": CATALOG_BUSY_REQUEST_MESSAGE, "code": CATALOG_BUSY_CODE},
        status_code=503,
        headers={"Retry-After": "5"},
    )


def create_app(*, token: str, db: Path | None = None, explicit_db: bool = False) -> Starlette:
    """Build the app. ``db`` defaults to the catalog this install resolves **at call time**.

    It used to default to a module constant, `_DEFAULT_DB = default_catalog_path()`, evaluated
    at import - and doubly frozen, since a default argument is itself bound once at def-time.
    `app_paths.default_catalog_path` documents the opposite contract in its own docstring:
    resolved on every call, never cached in a module constant, "an override set after import
    must still be honoured, and a constant computed at import time is unpatchable by a test and
    therefore un-isolatable". That is `(aae)`'s rule, and this file was the one place still
    breaking it.

    Latent rather than live: `__main__.py` resolves per call and passes ``db`` explicitly, so
    the shipped launch never used the frozen default. What it cost was every caller that omits
    ``db`` - test harnesses above all, which is precisely the isolation `(aae)` exists to give.
    """
    jobs = JobManager()
    started_fingerprint = _static_fingerprint()
    resolved_db = db if db is not None else default_catalog_path()

    # PRESENCE FIRST, THEN MIGRATE. The order is the whole of `(aae)`'s first-run message
    # surviving this: `library_status` inspects the catalog on every request, and after the
    # migration below the file always exists - so `WILL_CREATE` would become unreachable for an
    # implementation reason rather than because the world changed, and a genuine first run would
    # be told it may have opened the wrong catalog.
    #
    # ⚠ WHAT BOUNDS THIS VALUE'S LIFETIME, because a value cached at boot that outlives the truth
    # is the next defect: it is consulted **only when the live inspection says EMPTY**. Any real
    # content makes the live reading `READY` or `EMPTY_WITH_DRIVES` first and this is ignored, so
    # it cannot survive contact with data. A user who deletes the catalog mid-session gets
    # `WILL_CREATE` from the live reading anyway, which is the same answer. It is therefore a
    # one-way "there was nothing here at boot" fact, not a cache of the current state.
    boot_catalog = service.prepare_catalog(resolved_db, explicit_db=explicit_db)

    # MIGRATE ONCE, BEFORE SERVING. Otherwise the six requests a page load fires all reach
    # `Catalog._migrate` on a fresh catalog, one builds the schema and five queue behind it.
    # Measured in CI run 31821214510, after the cross-process fix and with no startup migration:
    # 7828 opens reached `_migrate`, and the wait at `BEGIN IMMEDIATE` ran to **2832 ms** with
    # 155 waits over a second. Correct, and still paid by every first-run user on their own disk.

    def _db() -> Path:
        return resolved_db

    def _explicit_db() -> bool:
        return explicit_db

    def _start_drive_job(
        target: JobTarget | Mapping[str, object],
        *,
        paths: list[Path],
        operation: str,
        mutating: bool,
        on_started: Callable[[], None] | None = None,
    ) -> JSONResponse:
        """Start a job locked to ``paths``, or return drive-unavailable / drive-busy without racing.

        Soft-fails for a non-drive path the same way undo already did. A second start on an
        occupied drive returns :class:`DriveBusyPayload` (HTTP 200, ``ok: false``) - never queues.

        ``target`` is either a job to run or **any refusal payload already shaped for the UI** -
        drive-unavailable, or a feature's own soft-fail such as the bake's MigrationUnfinished.
        The runtime check has always been "is this a dict", so the annotation says that rather
        than listing every payload type and needing an edit per feature.

        ``on_started`` runs **only when a job was actually accepted**, after the refusal paths
        have returned. It exists because "the work is under way" is not something a caller can
        read back out of the `JSONResponse` without parsing its body, and both refusals here are
        retryable - a caller that cleaned up eagerly would destroy the state a retry needs.
        Optional, so every existing call site is unchanged.
        """
        if isinstance(target, Mapping):
            return JSONResponse(dict(target))
        result: str | DriveBusyPayload = jobs.start(
            target,
            drives=[service.drive_ref_for(path) for path in paths],
            operation=operation,
            mutating=mutating,
        )
        if isinstance(result, dict):
            return JSONResponse(result)
        if on_started is not None:
            on_started()
        return JSONResponse({"job_id": result})

    def home(_request: Request) -> HTMLResponse:
        html = (_TEMPLATES / "index.html").read_text(encoding="utf-8")
        stale = _static_fingerprint() != started_fingerprint
        if stale:
            _log.warning(
                "static assets on disk have changed since this process started -- "
                "restart truestill-app to serve what is actually on disk"
            )
        html = html.replace("{{TOKEN}}", token)
        html = html.replace("{{STATIC_FINGERPRINT}}", started_fingerprint)
        html = html.replace("{{STALE_WARNING}}", _STALE_BANNER if stale else "")
        return HTMLResponse(html.replace("{{VERSION}}", __version__))

    async def organize_inventory(request: Request) -> JSONResponse:
        # Sync and cheap: walk + stat only. Not a job - that is the point of (tt).
        body = await request.json()
        return JSONResponse(
            await run_in_threadpool(service.organize_inventory, Path(body["source"]))
        )

    async def organize_preview(request: Request) -> JSONResponse:
        # A job like every other long operation -- on a large source this is the first long
        # wait a user meets, so it gets the same progress display rather than a frozen card.
        # Still a dry run: the job writes nothing. Locked on the destination (where copies land).
        body = await request.json()
        mode = str(body.get("mode", "copy"))
        destination = Path(body["destination"]) if body.get("destination") else Path(body["source"])
        target = await run_in_threadpool(
            service.organize_preview_run,
            Path(body["source"]),
            destination,
            _db(),
            refresh_metadata=bool(body.get("refresh_metadata", False)),
            # The run endpoint has always taken this; the preview did not, so a preview with
            # "skip files with no date" ticked promised files the run would not take. `(acx)`.
            skip_undated=bool(body.get("skip_undated", False)),
            mode=mode,
        )
        return await run_in_threadpool(
            _start_drive_job,
            target,
            paths=[destination],
            operation="organize preview",
            mutating=False,
        )

    async def organize_run(request: Request) -> JSONResponse:
        body = await request.json()
        mode = str(body.get("mode", "copy"))
        destination = Path(body["destination"]) if body.get("destination") else Path(body["source"])
        target = await run_in_threadpool(
            service.organize_run,
            Path(body["source"]),
            destination,
            _db(),
            skip_undated=bool(body.get("skip_undated", False)),
            refresh_metadata=bool(body.get("refresh_metadata", False)),
            mode=mode,
        )
        return await run_in_threadpool(
            _start_drive_job,
            target,
            paths=[destination],
            operation="organize",
            mutating=True,
        )

    async def organize_settings(request: Request) -> JSONResponse:
        if request.method == "POST":
            body = await request.json()
            return JSONResponse(
                await run_in_threadpool(service.set_organize_mode, body.get("mode"), _db())
            )
        return JSONResponse(await run_in_threadpool(service.organize_mode_state, _db()))

    async def sidebar_settings(request: Request) -> JSONResponse:
        if request.method == "POST":
            body = await request.json()
            return JSONResponse(
                await run_in_threadpool(service.set_sidebar_collapsed, body.get("collapsed"), _db())
            )
        return JSONResponse(await run_in_threadpool(service.sidebar_state, _db()))

    async def text_size_settings(request: Request) -> JSONResponse:
        if request.method == "POST":
            body = await request.json()
            return JSONResponse(
                await run_in_threadpool(service.set_text_size, body.get("size"), _db())
            )
        return JSONResponse(await run_in_threadpool(service.text_size_state, _db()))

    def organize_undo_state(_request: Request) -> JSONResponse:
        return JSONResponse(service.organize_undo_state(_db()))

    def organize_undo_preview(_request: Request) -> JSONResponse:
        state = service.organize_undo_state(_db())
        if state["armed"] is False:
            return JSONResponse(state)
        target = service.organize_undo(db=_db(), apply=False)
        return _start_drive_job(
            target,
            paths=[Path(state["source_root"]), Path(state["dest_root"])],
            operation="undo organize preview",
            mutating=False,
        )

    def organize_undo_apply(_request: Request) -> JSONResponse:
        state = service.organize_undo_state(_db())
        if state["armed"] is False:
            return JSONResponse(state)
        target = service.organize_undo(db=_db(), apply=True)
        return _start_drive_job(
            target,
            paths=[Path(state["source_root"]), Path(state["dest_root"])],
            operation="undo organize",
            mutating=True,
        )

    async def verify_run(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        return await run_in_threadpool(
            _start_drive_job,
            await run_in_threadpool(service.verify_run, path, _db()),
            paths=[path],
            operation="verify",
            mutating=False,
        )

    def job_events(request: Request) -> StreamingResponse:
        job_id = request.path_params["job_id"]
        return StreamingResponse(jobs.stream(job_id), media_type="text/event-stream")

    def job_cancel(request: Request) -> Response:
        ok = jobs.cancel(request.path_params["job_id"])
        return Response(status_code=202 if ok else 404)

    def drives(_request: Request) -> JSONResponse:
        return JSONResponse(
            {"drives": service.list_drives(_db()), "at_risk": service.at_risk(_db())}
        )

    async def reveal(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(
            await run_in_threadpool(service.reveal_in_file_manager, Path(body["path"]))
        )

    async def thumb(request: Request) -> Response:
        """A WebP thumbnail for catalogued content. See `service/thumbs.py` for the boundary.

        **Three refusals, three different truths**, because a grid that cannot draw a tile should
        be able to say which of them happened:

        * `400` - the id is not a sha256. A client bug, never a user's.
        * `404` - nothing holding this content can be opened. Unknown content answers the same,
          deliberately: a distinct code would turn this into a membership oracle over the library.
        * `415` - the file is right there and is not a decodable image.

        Runs on the threadpool via `run_in_threadpool`: a cold thumbnail is ~23 ms of CPU-bound
        decode, and doing that on the event loop would stall every other request behind each tile
        - which on a fifty-tile grid is the whole page.
        """
        sha = request.path_params["sha256"]
        try:
            data = await run_in_threadpool(service.thumbnail_bytes, sha, _db())
        except service.BadContentIdError:
            return PlainTextResponse("not a content id", status_code=400)
        except service.NoReachableCopyError:
            return PlainTextResponse("no reachable copy of that content", status_code=404)
        except service.UnidentifiedImageError:
            return PlainTextResponse("that file is not a decodable image", status_code=415)
        except service.UndecodableImageError:
            # 422, not 415: the format IS supported, the bytes are damaged. 5 of 4,108 real
            # corpus photos do this, and they used to reach the browser as a 500.
            return PlainTextResponse("that photo will not decode", status_code=422)
        return Response(
            data, media_type="image/webp", headers={"Cache-Control": service.THUMB_CACHE_CONTROL}
        )

    def where(request: Request) -> JSONResponse:
        params = request.query_params
        try:
            page = int(params.get("page", "1"))
        except ValueError:
            page = 1
        return JSONResponse(service.where(params.get("term", ""), _db(), page=page))

    async def backup_preview(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(
            await run_in_threadpool(
                service.backup_preview, Path(body["source"]), Path(body["target"]), _db()
            )
        )

    async def backup_run(request: Request) -> JSONResponse:
        body = await request.json()
        source, target_path = Path(body["source"]), Path(body["target"])
        return await run_in_threadpool(
            _start_drive_job,
            await run_in_threadpool(service.backup_run, source, target_path, _db()),
            paths=[source, target_path],
            operation="backup",
            mutating=True,
        )

    async def ingest_archives_precheck(request: Request) -> JSONResponse:
        # NOT a job: header reads only, so it answers in seconds and writes nothing - which is
        # what makes declining free. A job here would put a progress bar on a question.
        body = await request.json()
        return JSONResponse(
            await run_in_threadpool(
                service.archive_precheck, Path(body["takeout"]), Path(body["destination"])
            )
        )

    async def ingest_archives_run(request: Request) -> JSONResponse:
        # ⚠ **THIS WRITES, AND SAID OTHERWISE UNTIL 2026-08-23** (`(agg)`). It unpacks the archive
        # set into a staging tree ON THE DESTINATION DRIVE (`archive_extract.extract_archive_set`)
        # and only then previews it, so `mutating=False` meant `(aaw)`'s cross-process lock never
        # engaged for a route that writes gigabytes to a drive a CLI run may be organizing.
        #
        # **The label was the defect, not the location.** Staging lives on the destination on
        # purpose - `archive_set.space_for` records why: `/tmp` is a tmpfs or a small partition on
        # many machines, and a 200 GB export fails there in the least informative way available.
        # `"import preview"` is what was false: a step that unpacks archives is not a preview,
        # and the route below - which previews an already-extracted folder - is the one that is.
        body = await request.json()
        destination = Path(body["destination"])
        target = await run_in_threadpool(
            service.archive_ingest_run, Path(body["takeout"]), destination, _db()
        )
        return await run_in_threadpool(
            _start_drive_job,
            target,
            paths=[destination],
            operation="archive unpack",
            mutating=True,
        )

    async def ingest_preview(request: Request) -> JSONResponse:
        body = await request.json()
        destination = Path(body["destination"])
        target = await run_in_threadpool(
            service.ingest_preview_run, Path(body["takeout"]), destination, _db()
        )
        return await run_in_threadpool(
            _start_drive_job,
            target,
            paths=[destination],
            operation="import preview",
            mutating=False,
        )

    # --- folder picker + library status -------------------------------------------------

    def fs_dirs(request: Request) -> JSONResponse:
        return JSONResponse(service.fs_dirs(request.query_params.get("path", "")))

    def fs_validate(request: Request) -> JSONResponse:
        return JSONResponse(service.fs_validate(request.query_params.get("path", "")))

    def fs_relationship(request: Request) -> JSONResponse:
        source = Path(request.query_params.get("source", ""))
        destination = Path(request.query_params.get("destination", ""))
        return JSONResponse(service.filesystem_relationship(source, destination))

    async def fs_create(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(await run_in_threadpool(service.fs_create, body["path"]))

    async def clean_empty_preview(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        emptied = [str(item) for item in body.get("emptied", [])]
        return JSONResponse(await run_in_threadpool(service.clean_empty_preview, path, emptied))

    async def clean_empty_apply(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        emptied = [str(item) for item in body.get("emptied", [])]
        return JSONResponse(await run_in_threadpool(service.clean_empty_apply, path, emptied))

    def library_status(_request: Request) -> JSONResponse:
        return JSONResponse(
            service.library_status(_db(), explicit_db=_explicit_db(), boot_catalog=boot_catalog)
        )

    async def library_root(request: Request) -> JSONResponse:
        """Record where the user says their library should live. `(abx)`."""
        body = await request.json()
        return JSONResponse(
            await run_in_threadpool(service.set_library_root, body.get("path", ""), _db())
        )

    def library_stats(_request: Request) -> JSONResponse:
        return JSONResponse(service.library_stats(_db()))

    # --- Settings: destination layout template + migration ------------------------------

    async def layout(request: Request) -> JSONResponse:
        if request.method == "POST":
            body = await request.json()
            return JSONResponse(
                await run_in_threadpool(service.set_layout, body["template"], _db())
            )
        return JSONResponse(await run_in_threadpool(service.layout_state, _db()))

    async def layout_preview(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(await run_in_threadpool(service.preview_layout, body["template"]))

    async def event_settings(request: Request) -> JSONResponse:
        try:
            if request.method == "POST":
                body = await request.json()
                settings = await run_in_threadpool(
                    service.set_event_settings, body.get("min_files"), _db()
                )
            else:
                settings = await run_in_threadpool(service.event_settings, _db())
        except InvalidEventSettingsError as exc:
            return JSONResponse(
                await run_in_threadpool(service.invalid_event_settings_payload, str(exc))
            )
        return JSONResponse(await run_in_threadpool(service.event_settings_payload, settings))

    async def everyday_day_settings(request: Request) -> JSONResponse:
        try:
            if request.method == "POST":
                body = await request.json()
                return JSONResponse(
                    await run_in_threadpool(
                        service.set_everyday_day_settings, body.get("threshold"), _db()
                    )
                )
            settings = await run_in_threadpool(service.everyday_day_settings, _db())
        except InvalidEverydayDaySettingsError as exc:
            return JSONResponse(
                await run_in_threadpool(service.invalid_everyday_day_settings_payload, str(exc))
            )
        return JSONResponse(
            await run_in_threadpool(service.everyday_day_settings_payload, settings)
        )

    async def migrate_preview(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        return await run_in_threadpool(
            _start_drive_job,
            await run_in_threadpool(service.migration_preview_run, path, _db()),
            paths=[path],
            operation="migrate preview",
            mutating=False,
        )

    def dates_tier_files(request: Request) -> JSONResponse:
        """The files behind one row of the honesty view. Read-only, catalog-only.

        ``source`` absent means the *not recorded* tier, which is a real group and the
        commonest one on a library organized before schema v13 - not an error.
        """
        source = request.query_params.get("source")
        return JSONResponse(service.date_tier_files(_db(), source or None))

    async def dates_confirm(request: Request) -> JSONResponse:
        """Record a human-confirmed capture date for one file. Catalog-only, so not a job."""
        body = await request.json()
        return JSONResponse(
            await run_in_threadpool(
                service.confirm_file_date,
                _db(),
                sha256=str(body["sha256"]),
                date_text=str(body.get("date", "")),
                time_text=body.get("time"),
            )
        )

    async def dates_bake_preview(request: Request) -> JSONResponse:
        """Catalog-only, so a plain request rather than a job: no file is read to build a plan."""
        body = await request.json()
        return JSONResponse(
            await run_in_threadpool(service.bake_preview, Path(body["path"]), _db())
        )

    async def dates_bake_run(request: Request) -> JSONResponse:
        """Through `_start_drive_job`, so the per-drive lock covers a write to user files."""
        body = await request.json()
        path = Path(body["path"])
        return await run_in_threadpool(
            _start_drive_job,
            await run_in_threadpool(service.bake_run, path, _db()),
            paths=[path],
            operation="set dates",
            mutating=True,
        )

    async def migrate_run(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        return await run_in_threadpool(
            _start_drive_job,
            await run_in_threadpool(service.migration_apply, path, _db()),
            paths=[path],
            operation="migrate",
            mutating=True,
        )

    def migrate_undo_armed(request: Request) -> JSONResponse:
        path = Path(request.query_params.get("path", ""))
        return JSONResponse(service.migration_armed_state(path, _db()))

    async def migrate_undo_preview(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        return await run_in_threadpool(
            _start_drive_job,
            await run_in_threadpool(service.migration_undo, path, _db(), apply=False),
            paths=[path],
            operation="undo preview",
            mutating=False,
        )

    async def migrate_undo_apply(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        return await run_in_threadpool(
            _start_drive_job,
            await run_in_threadpool(service.migration_undo, path, _db(), apply=True),
            paths=[path],
            operation="undo",
            mutating=True,
        )

    # --- Trip/event review (session-based; merge/split are UI-only, no CLI path) ---
    sessions: dict[str, EventReviewSession] = {}

    #: Guards the read-modify-write in `remember_session`. Same type and idiom as
    #: `JobManager._lock`, and for a weaker but real reason: session **values** leave the event
    #: loop - `events_preview` and `events_apply_to_disk` hand `named_events`/`named_trips` to a
    #: job that runs on a worker thread - so "only the loop touches this" is an assumption rather
    #: than a fact anyone checks. It makes insert-and-evict indivisible; it does not make a
    #: session's contents thread-safe, and nothing mutates them from a worker today.
    sessions_lock = threading.Lock()

    def remember_session(session_id: str, session: EventReviewSession) -> None:
        """Store a review session, evicting the oldest past the cap.

        Nothing ever removed one before (audit F17), so a long-lived local server grew by a
        whole proposal's cards per "Find trips and events" click, for the life of the process.
        Bounded by count rather than expired on a timer: the only reader is the person who just
        created it, insertion order makes the oldest the safest to drop, and a cap cannot fire
        in the middle of the flow the way a timeout could.

        **This function existed and did nothing.** Its first statement was a call to itself
        instead of the store write, and no caller ever reached it - `events_propose` assigned to
        `sessions` directly - so the cap, the constant and this docstring all described a bound
        the process did not have. A helper nothing calls is how that survived review; the write
        now goes through here, and the test observes an eviction rather than the constant.

        **Complexity: O(1) amortized per insert.** One insert, then at most one eviction per
        call in steady state, since the store can only exceed the cap by the entry just added.
        `next(iter(sessions))` reads the first key of an insertion-ordered dict without walking
        it, so each eviction is O(1) too - nothing here is a function of library size, and the
        loop is a `while` only so a lowered cap drains rather than leaking the difference.
        """
        with sessions_lock:
            sessions[session_id] = session
            while len(sessions) > MAX_REVIEW_SESSIONS:
                sessions.pop(next(iter(sessions)))

    def discard_session(session_id: str) -> None:
        """Drop a session whose work is finished. Idempotent; a missing id is not an error.

        The cap is a backstop for reviews the user walked away from. This is the one moment a
        session is *provably* done, so the common case stops relying on the backstop.
        """
        with sessions_lock:
            sessions.pop(session_id, None)

    def expired_session() -> JSONResponse:
        """A stale session id is a 409 with a sentence, not a KeyError and a 500.

        Reachable in normal use: reload the page after a restart, or come back to a tab whose
        session has since been evicted. `app.js`'s `api()` raises on a non-2xx and puts the body
        in the banner, so this arrives as something a user can act on.
        """
        return JSONResponse(
            {
                "ok": False,
                "error": (
                    "This review has expired - the app restarted, or newer reviews replaced it. "
                    "Run Find trips and events again to start a fresh one."
                ),
            },
            status_code=409,
        )

    def _cards_payload(session_id: str) -> JSONResponse:
        session = sessions.get(session_id)
        if session is None:
            return expired_session()
        return JSONResponse(
            service.review_cards_payload(
                session_id,
                session.cards,
                session.min_files,
                session.existing_names,
                session.source_hints,
            )
        )

    async def events_propose(request: Request) -> JSONResponse:
        """Review trips and events on an already-organized connected drive (not a fresh import).

        A genuine multi-day run (Stage 2b's `detect_trips`) assembles into ONE card; a standalone
        active day still renders as its own (unchanged) day-event card - the 13.3b inversion.
        """
        path = Path((await request.json())["path"])
        try:
            proposal = await run_in_threadpool(service.propose_events, path, _db())
        except InvalidEventSettingsError as exc:
            return JSONResponse(
                await run_in_threadpool(service.invalid_event_proposal_payload, str(exc))
            )
        if not proposal["ok"]:
            return JSONResponse({"ok": False, "error": proposal["error"]})
        session_id = uuid.uuid4().hex
        session = EventReviewSession(
            path=str(path),
            cards=proposal["cards"],
            day_totals=proposal["day_totals"],
            min_files=proposal["min_files"],
            existing_names=proposal["existing_names"],
            source_hints=proposal["source_hints"],
        )
        remember_session(session_id, session)
        return JSONResponse(
            await run_in_threadpool(service.proposed_review_cards_payload, session_id, proposal)
        )

    async def events_merge(request: Request) -> JSONResponse:
        """Combine two or more cards the detector did not join into one trip (the gap case).

        Refuses - reporting why, nothing merged - rather than producing a trip that would cross
        a year boundary or exceed the max-span cap (§3e/§3f); the two rules a manual merge must
        obey exactly like detection does.
        """
        session_id = request.path_params["session"]
        indices: list[int] = (await request.json())["indices"]
        session = sessions.get(session_id)
        if session is None:
            return expired_session()
        result = await run_in_threadpool(
            service.merge_event_review_cards, session.cards, session.day_totals, indices
        )
        if "error" in result:
            return JSONResponse({"error": result["error"]})
        session.cards = result["cards"]
        return await run_in_threadpool(_cards_payload, session_id)

    async def events_split(request: Request) -> JSONResponse:
        """Break a wrongly-joined run into two - the primary adjustment.

        An event card splits by file count (unchanged, `events.split_candidate`); a trip card
        splits at a day boundary (`trip_review.split_trip`) - the two mirror each other, but a
        trip's natural unit is the day, never an individual file.
        """
        session_id = request.path_params["session"]
        body = await request.json()
        session = sessions.get(session_id)
        if session is None:
            return expired_session()
        session.cards = await run_in_threadpool(
            service.split_event_review_card,
            session.cards,
            int(body["index"]),
            at=body.get("at"),
            after_day=body.get("after_day"),
        )
        return await run_in_threadpool(_cards_payload, session_id)

    async def events_apply(request: Request) -> JSONResponse:
        """Name the reviewed trips and events: persist each decision.

        This is the 'Save names' step. It changes only the catalog: an event links its files
        (`files.event_id`, unchanged) via `commit_catalog`; a trip persists `trips`/`trip_days`
        via `commit_trips` (13.1) - no file is placed or moved by either. On-disk placement is a
        separate, previewed, journalled migration (events_preview / events_apply_to_disk), which
        now understands both (Stage 13.4).
        """
        session_id = request.path_params["session"]
        names: list[str | None] = (await request.json())["names"]
        session = sessions.get(session_id)
        if session is None:
            return expired_session()
        result = await run_in_threadpool(
            service.apply_event_review_names, _db(), session.cards, names
        )
        session.named_events = result["named_events"]
        session.named_trips = result["named_trips"]
        return JSONResponse({"events": result["events"], "trips": result["trips"]})

    def events_preview(request: Request) -> JSONResponse:
        """Preview where the just-named trips will move the drive's files (moves nothing)."""
        session = sessions.get(request.path_params["session"])
        if session is None:
            return expired_session()
        path = Path(session.path)
        return _start_drive_job(
            service.migration_preview_run(path, _db()),
            paths=[path],
            operation="trip preview",
            mutating=False,
        )

    def events_apply_to_disk(request: Request) -> JSONResponse:
        """Apply the trip placement: a journalled, resumable relocation on the drive.

        Discards the session **once the job is accepted**, not before: this is the one point a
        review is provably finished, so the count cap goes back to being the backstop for
        abandoned reviews rather than the only thing that ever removes an entry.

        Ordering is the whole of the safety argument. `migration_apply` is called eagerly and
        binds the names into the job target, so the worker never reads `sessions` again; and the
        discard runs through `on_started`, after both refusal paths, because drive-unavailable
        and drive-busy are retryable and a session dropped on refusal would leave the user with
        a hidden button and nothing to retry. A later call on this id answers `expired_session`,
        which is the honest reply once the files have moved - re-previewing an applied session
        would plan from state that no longer exists.
        """
        session_id = request.path_params["session"]
        session = sessions.get(session_id)
        if session is None:
            return expired_session()
        path = Path(session.path)
        return _start_drive_job(
            service.migration_apply(
                path,
                _db(),
                session.named_events,
                session.named_trips,
            ),
            paths=[path],
            operation="trip apply",
            mutating=True,
            on_started=lambda: discard_session(session_id),
        )

    routes = [
        Route("/", home),
        Route("/api/organize/inventory", organize_inventory, methods=["POST"]),
        Route("/api/organize/preview", organize_preview, methods=["POST"]),
        Route("/api/organize/run", organize_run, methods=["POST"]),
        Route("/api/organize/settings", organize_settings, methods=["GET", "POST"]),
        Route("/api/sidebar/settings", sidebar_settings, methods=["GET", "POST"]),
        Route("/api/text-size/settings", text_size_settings, methods=["GET", "POST"]),
        Route("/api/organize/undo", organize_undo_state),
        Route("/api/organize/undo/preview", organize_undo_preview, methods=["POST"]),
        Route("/api/organize/undo/apply", organize_undo_apply, methods=["POST"]),
        Route("/api/verify/run", verify_run, methods=["POST"]),
        Route("/api/ingest/preview", ingest_preview, methods=["POST"]),
        Route("/api/ingest/archives/precheck", ingest_archives_precheck, methods=["POST"]),
        Route("/api/ingest/archives/run", ingest_archives_run, methods=["POST"]),
        Route("/api/fs/dirs", fs_dirs),
        Route("/api/fs/validate", fs_validate),
        Route("/api/fs/relationship", fs_relationship),
        Route("/api/fs/create", fs_create, methods=["POST"]),
        Route("/api/clean-empty/preview", clean_empty_preview, methods=["POST"]),
        Route("/api/clean-empty/apply", clean_empty_apply, methods=["POST"]),
        Route("/api/library/status", library_status),
        Route("/api/library/root", library_root, methods=["POST"]),
        Route("/api/library/stats", library_stats),
        Route("/api/layout", layout, methods=["GET", "POST"]),
        Route("/api/layout/preview", layout_preview, methods=["POST"]),
        Route("/api/layout/everyday-day-threshold", everyday_day_settings, methods=["GET", "POST"]),
        Route("/api/events/settings", event_settings, methods=["GET", "POST"]),
        Route("/api/migrate/preview", migrate_preview, methods=["POST"]),
        Route("/api/migrate/run", migrate_run, methods=["POST"]),
        Route("/api/dates/files", dates_tier_files),
        Route("/api/dates/confirm", dates_confirm, methods=["POST"]),
        Route("/api/dates/bake/preview", dates_bake_preview, methods=["POST"]),
        Route("/api/dates/bake/run", dates_bake_run, methods=["POST"]),
        Route("/api/migrate/undo", migrate_undo_armed),
        Route("/api/migrate/undo/preview", migrate_undo_preview, methods=["POST"]),
        Route("/api/migrate/undo/apply", migrate_undo_apply, methods=["POST"]),
        Route("/api/events/propose", events_propose, methods=["POST"]),
        Route("/api/events/{session}/merge", events_merge, methods=["POST"]),
        Route("/api/events/{session}/split", events_split, methods=["POST"]),
        Route("/api/events/{session}/apply", events_apply, methods=["POST"]),
        Route("/api/events/{session}/preview", events_preview, methods=["POST"]),
        Route("/api/events/{session}/apply-to-disk", events_apply_to_disk, methods=["POST"]),
        Route("/api/jobs/{job_id}/events", job_events),
        Route("/api/jobs/{job_id}/cancel", job_cancel, methods=["POST"]),
        Route("/api/drives", drives),
        Route("/api/reveal", reveal, methods=["POST"]),
        Route("/api/where", where),
        Route("/api/thumb/{sha256}", thumb),
        Route("/api/backup/preview", backup_preview, methods=["POST"]),
        Route("/api/backup/run", backup_run, methods=["POST"]),
    ]

    class StampStaticFingerprint:
        """Put this process's static fingerprint on every response.

        The page compares it with the one baked into its own HTML, so a TAB older than the
        server can say so. `_static_fingerprint` already covers the other direction (a server
        older than the files); this is the half that was missing, and it is what a user
        experiences as "the new setting does nothing".

        Read once at startup, not per response: this answers "which build served this page",
        which cannot change while the process lives - and `home` already recomputes from disk
        for its own, different question.
        """

        def __init__(self, app: ASGIApp) -> None:
            self._app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] != "http":
                await self._app(scope, receive, send)
                return

            async def stamped(message: Message) -> None:
                if message["type"] == "http.response.start":
                    message.setdefault("headers", []).append(
                        (b"x-truestill-static", started_fingerprint.encode("ascii"))
                    )
                await send(message)

            await self._app(scope, receive, stamped)

    app = Starlette(
        routes=routes,
        # ⚠ **ONE recognition per surface, at the top - the CLI's own shape.** `cli.py`'s main()
        # catches `sqlite3.Error`, asks `is_catalog_busy`, and words the refusal once for every
        # subcommand; this is the same catch for every route. `(agp)`'s census found SEVEN
        # direct-write service calls across four files with no handler at all, so a busy
        # settings write surfaced as a raw Starlette 500 reading "Internal Server Error" - the
        # exact SQLite-prose-on-screen class `(afe)` exists to keep off the screen. Per-route
        # handlers would be that census re-run by hand every time a route is added; the
        # app-level handler makes a new unhandled route structurally impossible.
        exception_handlers={sqlite3.Error: _catalog_busy_refusal},
    )
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    app.add_middleware(StampStaticFingerprint)
    app.add_middleware(LocalGuard, token=token)
    app.state.token = token
    return app
