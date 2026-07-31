"""The Starlette application: routes, SSE, static assets, wired to the service + job manager.

The app is built by :func:`create_app`, which takes the session token so tests can construct it
directly. Every data route is guarded by :class:`~truestill_app.security.LocalGuard`.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from truestill_core.catalog_startup import DEFAULT_CATALOG_PATH
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
    named_events: list[service.NamedEventSelection] = field(default_factory=list)
    named_trips: list[service.NamedTripSelection] = field(default_factory=list)


_PKG = Path(__file__).resolve().parent
_TEMPLATES = _PKG / "templates"
_STATIC = _PKG / "static"

#: Default catalog the app reads/writes (same default as the CLI).
_DEFAULT_DB = DEFAULT_CATALOG_PATH

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


def create_app(*, token: str, db: Path = _DEFAULT_DB, explicit_db: bool = False) -> Starlette:
    jobs = JobManager()
    started_fingerprint = _static_fingerprint()

    def _db() -> Path:
        return db

    def _explicit_db() -> bool:
        return explicit_db

    def _start_drive_job(
        target: JobTarget | Mapping[str, object],
        *,
        paths: list[Path],
        operation: str,
    ) -> JSONResponse:
        """Start a job locked to ``paths``, or return drive-unavailable / drive-busy without racing.

        Soft-fails for a non-drive path the same way undo already did. A second start on an
        occupied drive returns :class:`DriveBusyPayload` (HTTP 200, ``ok: false``) - never queues.

        ``target`` is either a job to run or **any refusal payload already shaped for the UI** -
        drive-unavailable, or a feature's own soft-fail such as the bake's MigrationUnfinished.
        The runtime check has always been "is this a dict", so the annotation says that rather
        than listing every payload type and needing an edit per feature.
        """
        if isinstance(target, Mapping):
            return JSONResponse(dict(target))
        result: str | DriveBusyPayload = jobs.start(
            target,
            drives=[service.drive_ref_for(path) for path in paths],
            operation=operation,
        )
        if isinstance(result, dict):
            return JSONResponse(result)
        return JSONResponse({"job_id": result})

    async def home(_request: Request) -> HTMLResponse:
        html = (_TEMPLATES / "index.html").read_text(encoding="utf-8")
        stale = _static_fingerprint() != started_fingerprint
        if stale:
            _log.warning(
                "static assets on disk have changed since this process started -- "
                "restart truestill-app to serve what is actually on disk"
            )
        html = html.replace("{{TOKEN}}", token)
        html = html.replace("{{STALE_WARNING}}", _STALE_BANNER if stale else "")
        return HTMLResponse(html.replace("{{VERSION}}", __version__))

    async def organize_inventory(request: Request) -> JSONResponse:
        # Sync and cheap: walk + stat only. Not a job - that is the point of (tt).
        body = await request.json()
        return JSONResponse(service.organize_inventory(Path(body["source"])))

    async def organize_preview(request: Request) -> JSONResponse:
        # A job like every other long operation -- on a large source this is the first long
        # wait a user meets, so it gets the same progress display rather than a frozen card.
        # Still a dry run: the job writes nothing. Locked on the destination (where copies land).
        body = await request.json()
        mode = str(body.get("mode", "copy"))
        destination = Path(body["destination"]) if body.get("destination") else Path(body["source"])
        target = service.organize_preview_run(
            Path(body["source"]),
            destination,
            _db(),
            refresh_metadata=bool(body.get("refresh_metadata", False)),
            mode=mode,
        )
        return _start_drive_job(target, paths=[destination], operation="organize preview")

    async def organize_run(request: Request) -> JSONResponse:
        body = await request.json()
        mode = str(body.get("mode", "copy"))
        destination = Path(body["destination"]) if body.get("destination") else Path(body["source"])
        target = service.organize_run(
            Path(body["source"]),
            destination,
            _db(),
            skip_undated=bool(body.get("skip_undated", False)),
            refresh_metadata=bool(body.get("refresh_metadata", False)),
            mode=mode,
        )
        return _start_drive_job(target, paths=[destination], operation="organize")

    async def organize_settings(request: Request) -> JSONResponse:
        if request.method == "POST":
            body = await request.json()
            return JSONResponse(service.set_organize_mode(body.get("mode"), _db()))
        return JSONResponse(service.organize_mode_state(_db()))

    async def sidebar_settings(request: Request) -> JSONResponse:
        if request.method == "POST":
            body = await request.json()
            return JSONResponse(service.set_sidebar_collapsed(body.get("collapsed"), _db()))
        return JSONResponse(service.sidebar_state(_db()))

    async def organize_undo_state(_request: Request) -> JSONResponse:
        return JSONResponse(service.organize_undo_state(_db()))

    async def organize_undo_preview(_request: Request) -> JSONResponse:
        state = service.organize_undo_state(_db())
        if state["armed"] is False:
            return JSONResponse(state)
        target = service.organize_undo(db=_db(), apply=False)
        return _start_drive_job(
            target,
            paths=[Path(state["source_root"]), Path(state["dest_root"])],
            operation="undo organize preview",
        )

    async def organize_undo_apply(_request: Request) -> JSONResponse:
        state = service.organize_undo_state(_db())
        if state["armed"] is False:
            return JSONResponse(state)
        target = service.organize_undo(db=_db(), apply=True)
        return _start_drive_job(
            target,
            paths=[Path(state["source_root"]), Path(state["dest_root"])],
            operation="undo organize",
        )

    async def verify_run(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        return _start_drive_job(service.verify_run(path, _db()), paths=[path], operation="verify")

    async def job_events(request: Request) -> StreamingResponse:
        job_id = request.path_params["job_id"]
        return StreamingResponse(jobs.stream(job_id), media_type="text/event-stream")

    async def job_cancel(request: Request) -> Response:
        ok = jobs.cancel(request.path_params["job_id"])
        return Response(status_code=202 if ok else 404)

    async def drives(_request: Request) -> JSONResponse:
        return JSONResponse(
            {"drives": service.list_drives(_db()), "at_risk": service.at_risk(_db())}
        )

    async def reveal(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(service.reveal_in_file_manager(Path(body["path"])))

    async def where(request: Request) -> JSONResponse:
        params = request.query_params
        try:
            page = int(params.get("page", "1"))
        except ValueError:
            page = 1
        return JSONResponse(service.where(params.get("term", ""), _db(), page=page))

    async def backup_preview(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(
            service.backup_preview(Path(body["source"]), Path(body["target"]), _db())
        )

    async def backup_run(request: Request) -> JSONResponse:
        body = await request.json()
        source, target_path = Path(body["source"]), Path(body["target"])
        return _start_drive_job(
            service.backup_run(source, target_path, _db()),
            paths=[source, target_path],
            operation="backup",
        )

    async def ingest_preview(request: Request) -> JSONResponse:
        body = await request.json()
        destination = Path(body["destination"])
        target = service.ingest_preview_run(Path(body["takeout"]), destination, _db())
        return _start_drive_job(target, paths=[destination], operation="import preview")

    # --- folder picker + library status -------------------------------------------------

    async def fs_dirs(request: Request) -> JSONResponse:
        return JSONResponse(service.fs_dirs(request.query_params.get("path", "")))

    async def fs_validate(request: Request) -> JSONResponse:
        return JSONResponse(service.fs_validate(request.query_params.get("path", "")))

    async def fs_relationship(request: Request) -> JSONResponse:
        source = Path(request.query_params.get("source", ""))
        destination = Path(request.query_params.get("destination", ""))
        return JSONResponse(service.filesystem_relationship(source, destination))

    async def fs_create(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(service.fs_create(body["path"]))

    async def clean_empty_preview(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        emptied = [str(item) for item in body.get("emptied", [])]
        return JSONResponse(service.clean_empty_preview(path, emptied))

    async def clean_empty_apply(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        emptied = [str(item) for item in body.get("emptied", [])]
        return JSONResponse(service.clean_empty_apply(path, emptied))

    async def library_status(_request: Request) -> JSONResponse:
        return JSONResponse(service.library_status(_db(), explicit_db=_explicit_db()))

    async def library_stats(_request: Request) -> JSONResponse:
        return JSONResponse(service.library_stats(_db()))

    # --- Settings: destination layout template + migration ------------------------------

    async def layout(request: Request) -> JSONResponse:
        if request.method == "POST":
            body = await request.json()
            return JSONResponse(service.set_layout(body["template"], _db()))
        return JSONResponse(service.layout_state(_db()))

    async def layout_preview(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(service.preview_layout(body["template"]))

    async def event_settings(request: Request) -> JSONResponse:
        try:
            if request.method == "POST":
                body = await request.json()
                settings = service.set_event_settings(body.get("min_files"), _db())
            else:
                settings = service.event_settings(_db())
        except InvalidEventSettingsError as exc:
            return JSONResponse(service.invalid_event_settings_payload(str(exc)))
        return JSONResponse(service.event_settings_payload(settings))

    async def everyday_day_settings(request: Request) -> JSONResponse:
        try:
            if request.method == "POST":
                body = await request.json()
                return JSONResponse(service.set_everyday_day_settings(body.get("threshold"), _db()))
            settings = service.everyday_day_settings(_db())
        except InvalidEverydayDaySettingsError as exc:
            return JSONResponse(service.invalid_everyday_day_settings_payload(str(exc)))
        return JSONResponse(service.everyday_day_settings_payload(settings))

    async def migrate_preview(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        return _start_drive_job(
            service.migration_preview_run(path, _db()),
            paths=[path],
            operation="migrate preview",
        )

    async def dates_bake_preview(request: Request) -> JSONResponse:
        """Catalog-only, so a plain request rather than a job: no file is read to build a plan."""
        body = await request.json()
        return JSONResponse(service.bake_preview(Path(body["path"]), _db()))

    async def dates_bake_run(request: Request) -> JSONResponse:
        """Through `_start_drive_job`, so the per-drive lock covers a write to user files."""
        body = await request.json()
        path = Path(body["path"])
        return _start_drive_job(service.bake_run(path, _db()), paths=[path], operation="set dates")

    async def migrate_run(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        return _start_drive_job(
            service.migration_apply(path, _db()), paths=[path], operation="migrate"
        )

    async def migrate_undo_armed(request: Request) -> JSONResponse:
        path = Path(request.query_params.get("path", ""))
        return JSONResponse(service.migration_armed_state(path, _db()))

    async def migrate_undo_preview(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        return _start_drive_job(
            service.migration_undo(path, _db(), apply=False),
            paths=[path],
            operation="undo preview",
        )

    async def migrate_undo_apply(request: Request) -> JSONResponse:
        body = await request.json()
        path = Path(body["path"])
        return _start_drive_job(
            service.migration_undo(path, _db(), apply=True),
            paths=[path],
            operation="undo",
        )

    # --- Trip/event review (session-based; merge/split are UI-only, no CLI path) ---
    sessions: dict[str, EventReviewSession] = {}

    def remember_session(session_id: str, session: EventReviewSession) -> None:
        """Store a review session, evicting the oldest past the cap.

        Nothing ever removed one before (audit F17), so a long-lived local server grew by a
        whole proposal's cards per "Find trips and events" click, for the life of the process.
        Bounded by count rather than expired on a timer: the only reader is the person who just
        created it, insertion order makes the oldest the safest to drop, and a cap cannot fire
        in the middle of the flow the way a timeout could.
        """
        remember_session(session_id, session)
        while len(sessions) > MAX_REVIEW_SESSIONS:
            sessions.pop(next(iter(sessions)))

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
            service.review_cards_payload(session_id, session.cards, session.min_files)
        )

    async def events_propose(request: Request) -> JSONResponse:
        """Review trips and events on an already-organized connected drive (not a fresh import).

        A genuine multi-day run (Stage 2b's `detect_trips`) assembles into ONE card; a standalone
        active day still renders as its own (unchanged) day-event card - the 13.3b inversion.
        """
        path = Path((await request.json())["path"])
        try:
            proposal = service.propose_events(path, _db())
        except InvalidEventSettingsError as exc:
            return JSONResponse(service.invalid_event_proposal_payload(str(exc)))
        if not proposal["ok"]:
            return JSONResponse({"ok": False, "error": proposal["error"]})
        session_id = uuid.uuid4().hex
        session = EventReviewSession(
            path=str(path),
            cards=proposal["cards"],
            day_totals=proposal["day_totals"],
            min_files=proposal["min_files"],
        )
        sessions[session_id] = session
        return JSONResponse(
            service.proposed_review_cards_payload(
                session_id,
                session.cards,
                session.min_files,
                proposal["label"],
                proposal["declines"],
            )
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
        result = service.merge_event_review_cards(session.cards, session.day_totals, indices)
        if "error" in result:
            return JSONResponse({"error": result["error"]})
        session.cards = result["cards"]
        return _cards_payload(session_id)

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
        session.cards = service.split_event_review_card(
            session.cards,
            int(body["index"]),
            at=body.get("at"),
            after_day=body.get("after_day"),
        )
        return _cards_payload(session_id)

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
        result = service.apply_event_review_names(_db(), session.cards, names)
        session.named_events = result["named_events"]
        session.named_trips = result["named_trips"]
        return JSONResponse({"events": result["events"], "trips": result["trips"]})

    async def events_preview(request: Request) -> JSONResponse:
        """Preview where the just-named trips will move the drive's files (moves nothing)."""
        session = sessions.get(request.path_params["session"])
        if session is None:
            return expired_session()
        path = Path(session.path)
        return _start_drive_job(
            service.migration_preview_run(path, _db()),
            paths=[path],
            operation="trip preview",
        )

    async def events_apply_to_disk(request: Request) -> JSONResponse:
        """Apply the trip placement: a journalled, resumable relocation on the drive."""
        session = sessions.get(request.path_params["session"])
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
        )

    routes = [
        Route("/", home),
        Route("/api/organize/inventory", organize_inventory, methods=["POST"]),
        Route("/api/organize/preview", organize_preview, methods=["POST"]),
        Route("/api/organize/run", organize_run, methods=["POST"]),
        Route("/api/organize/settings", organize_settings, methods=["GET", "POST"]),
        Route("/api/sidebar/settings", sidebar_settings, methods=["GET", "POST"]),
        Route("/api/organize/undo", organize_undo_state),
        Route("/api/organize/undo/preview", organize_undo_preview, methods=["POST"]),
        Route("/api/organize/undo/apply", organize_undo_apply, methods=["POST"]),
        Route("/api/verify/run", verify_run, methods=["POST"]),
        Route("/api/ingest/preview", ingest_preview, methods=["POST"]),
        Route("/api/fs/dirs", fs_dirs),
        Route("/api/fs/validate", fs_validate),
        Route("/api/fs/relationship", fs_relationship),
        Route("/api/fs/create", fs_create, methods=["POST"]),
        Route("/api/clean-empty/preview", clean_empty_preview, methods=["POST"]),
        Route("/api/clean-empty/apply", clean_empty_apply, methods=["POST"]),
        Route("/api/library/status", library_status),
        Route("/api/library/stats", library_stats),
        Route("/api/layout", layout, methods=["GET", "POST"]),
        Route("/api/layout/preview", layout_preview, methods=["POST"]),
        Route("/api/layout/everyday-day-threshold", everyday_day_settings, methods=["GET", "POST"]),
        Route("/api/events/settings", event_settings, methods=["GET", "POST"]),
        Route("/api/migrate/preview", migrate_preview, methods=["POST"]),
        Route("/api/migrate/run", migrate_run, methods=["POST"]),
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
        Route("/api/backup/preview", backup_preview, methods=["POST"]),
        Route("/api/backup/run", backup_run, methods=["POST"]),
    ]
    app = Starlette(routes=routes)
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    app.add_middleware(LocalGuard, token=token)
    app.state.token = token
    return app
