"""The Starlette application: routes, SSE, static assets, wired to the service + job manager.

The app is built by :func:`create_app`, which takes the session token so tests can construct it
directly. Every data route is guarded by :class:`~truestill_app.security.LocalGuard`.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from truestill_core.catalog import Catalog
from truestill_core.event_review import EventDecision, commit_catalog
from truestill_core.events import InvalidEventSettingsError, split_candidate
from truestill_core.trip_review import (
    ReviewCard,
    TripDecision,
    TripMergeError,
    commit_trips,
    merge_review_cards,
    split_trip,
)

from truestill_app import __version__, service
from truestill_app.jobs import JobManager
from truestill_app.security import LocalGuard

_PKG = Path(__file__).resolve().parent
_TEMPLATES = _PKG / "templates"
_STATIC = _PKG / "static"

#: Default catalog the app reads/writes (same default as the CLI).
_DEFAULT_DB = Path("reports/catalog.sqlite")

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


def create_app(*, token: str, db: Path = _DEFAULT_DB) -> Starlette:
    jobs = JobManager()
    started_fingerprint = _static_fingerprint()

    def _db() -> Path:
        return db

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

    async def organize_preview(request: Request) -> JSONResponse:
        # A job like every other long operation -- on a large source this is the first long
        # wait a user meets, so it gets the same progress display rather than a frozen card.
        # Still a dry run: the job writes nothing.
        body = await request.json()
        target = service.organize_preview_run(
            Path(body["source"]), Path(body["destination"]), _db()
        )
        return JSONResponse({"job_id": jobs.start(target)})

    async def organize_run(request: Request) -> JSONResponse:
        body = await request.json()
        target = service.organize_run(
            Path(body["source"]),
            Path(body["destination"]),
            _db(),
            skip_undated=bool(body.get("skip_undated", False)),
        )
        return JSONResponse({"job_id": jobs.start(target)})

    async def verify_run(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse({"job_id": jobs.start(service.verify_run(Path(body["path"]), _db()))})

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
        job = service.backup_run(Path(body["source"]), Path(body["target"]), _db())
        return JSONResponse({"job_id": jobs.start(job)})

    async def ingest_preview(request: Request) -> JSONResponse:
        body = await request.json()
        report = service.ingest_preview(Path(body["takeout"]), Path(body["destination"]), _db())
        return JSONResponse(report)

    # --- folder picker + library status -------------------------------------------------

    async def fs_dirs(request: Request) -> JSONResponse:
        return JSONResponse(service.fs_dirs(request.query_params.get("path", "")))

    async def fs_validate(request: Request) -> JSONResponse:
        return JSONResponse(service.fs_validate(request.query_params.get("path", "")))

    async def fs_create(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(service.fs_create(body["path"]))

    async def library_status(_request: Request) -> JSONResponse:
        return JSONResponse(service.library_status(_db()))

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

    async def migrate_preview(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(service.migration_preview(Path(body["path"]), _db()))

    async def migrate_run(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(
            {"job_id": jobs.start(service.migration_apply(Path(body["path"]), _db()))}
        )

    # --- Trip/event review (session-based; merge/split are UI-only, no CLI path) ---
    sessions: dict[str, dict[str, Any]] = {}

    def _cards_payload(session_id: str, **extra: Any) -> JSONResponse:
        cards = sessions[session_id]["cards"]
        return JSONResponse(
            {
                "session": session_id,
                "cards": [service.review_card_json(c) for c in cards],
                **extra,
            }
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
        sessions[session_id] = {
            "path": str(path),
            "cards": proposal["cards"],
            "day_totals": proposal["day_totals"],
        }
        return _cards_payload(
            session_id, ok=True, label=proposal["label"], declines=proposal["declines"]
        )

    async def events_merge(request: Request) -> JSONResponse:
        """Combine two or more cards the detector did not join into one trip (the gap case).

        Refuses - reporting why, nothing merged - rather than producing a trip that would cross
        a year boundary or exceed the max-span cap (§3e/§3f); the two rules a manual merge must
        obey exactly like detection does.
        """
        session_id = request.path_params["session"]
        indices: list[int] = (await request.json())["indices"]
        session = sessions[session_id]
        cards: list[ReviewCard] = session["cards"]
        chosen = [cards[i] for i in indices]
        rest = [c for j, c in enumerate(cards) if j not in set(indices)]
        try:
            merged = merge_review_cards(chosen, session["day_totals"])
        except TripMergeError as exc:
            return JSONResponse({"error": str(exc)})
        session["cards"] = [ReviewCard(trip=merged), *rest]
        return _cards_payload(session_id)

    async def events_split(request: Request) -> JSONResponse:
        """Break a wrongly-joined run into two - the primary adjustment.

        An event card splits by file count (unchanged, `events.split_candidate`); a trip card
        splits at a day boundary (`trip_review.split_trip`) - the two mirror each other, but a
        trip's natural unit is the day, never an individual file.
        """
        session_id = request.path_params["session"]
        body = await request.json()
        cards: list[ReviewCard] = sessions[session_id]["cards"]
        card = cards[body["index"]]
        if card.event is not None:
            first_event, second_event = split_candidate(card.event, body["at"])
            new_cards = [ReviewCard(event=first_event), ReviewCard(event=second_event)]
        else:
            assert card.trip is not None
            first_trip, second_trip = split_trip(card.trip, date.fromisoformat(body["after_day"]))
            new_cards = [ReviewCard(trip=first_trip), ReviewCard(trip=second_trip)]
        cards[body["index"] : body["index"] + 1] = new_cards
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
        session = sessions[session_id]
        cards: list[ReviewCard] = session["cards"]
        with Catalog(_db()) as catalog:
            event_decisions = [
                EventDecision(card.event, name)
                for card, name in zip(cards, names, strict=True)
                if card.event is not None
            ]
            named_events_count = commit_catalog(catalog, event_decisions)

            trip_decisions = [
                TripDecision(card.trip, name)
                for card, name in zip(cards, names, strict=True)
                if card.trip is not None
            ]
            named_trips_count = commit_trips(catalog, trip_decisions)

            # Remembered so apply-to-disk can report each named item's real destination folder
            # once the migration has actually placed its files there (13.3a) -- not a rename or a
            # guess, just this session's own decisions, looked up again now that they are
            # persisted.
            named_events = []
            for card, name in zip(cards, names, strict=True):
                if card.event is None or not name or not name.strip():
                    continue
                existing = catalog.event_by_signature(card.event.signature)
                if existing is None:
                    continue
                named_events.append(
                    {
                        "event_id": int(existing["id"]),
                        "name": str(existing["name"]),
                        "start": card.event.start.isoformat(),
                        "end": card.event.end.isoformat(),
                    }
                )
            # A trip's id is not returned by `commit_trips` (it persists a count, not the rows),
            # so it is looked up the same way name-once already does: `trip_for_day` on one of the
            # trip's own claimed days, after the commit above has made that lookup answer it.
            named_trips = []
            for card, name in zip(cards, names, strict=True):
                if card.trip is None or not name or not name.strip():
                    continue
                first_day = min(card.trip.days)
                trip_id = catalog.trip_for_day(first_day.isoformat())
                if trip_id is None:
                    continue
                named_trips.append(
                    {
                        "trip_id": trip_id,
                        "name": name.strip(),
                        "start": first_day.isoformat(),
                        "end": max(card.trip.days).isoformat(),
                    }
                )
        session["named_events"] = named_events
        session["named_trips"] = named_trips
        return JSONResponse({"events": named_events_count, "trips": named_trips_count})

    async def events_preview(request: Request) -> JSONResponse:
        """Preview where the just-named trips will move the drive's files (moves nothing)."""
        session = sessions[request.path_params["session"]]
        return JSONResponse(service.migration_preview(Path(session["path"]), _db()))

    async def events_apply_to_disk(request: Request) -> JSONResponse:
        """Apply the trip placement: a journalled, resumable relocation on the drive."""
        session = sessions[request.path_params["session"]]
        job_id = jobs.start(
            service.migration_apply(
                Path(session["path"]),
                _db(),
                session.get("named_events", []),
                session.get("named_trips", []),
            )
        )
        return JSONResponse({"job_id": job_id})

    routes = [
        Route("/", home),
        Route("/api/organize/preview", organize_preview, methods=["POST"]),
        Route("/api/organize/run", organize_run, methods=["POST"]),
        Route("/api/verify/run", verify_run, methods=["POST"]),
        Route("/api/ingest/preview", ingest_preview, methods=["POST"]),
        Route("/api/fs/dirs", fs_dirs),
        Route("/api/fs/validate", fs_validate),
        Route("/api/fs/create", fs_create, methods=["POST"]),
        Route("/api/library/status", library_status),
        Route("/api/layout", layout, methods=["GET", "POST"]),
        Route("/api/layout/preview", layout_preview, methods=["POST"]),
        Route("/api/events/settings", event_settings, methods=["GET", "POST"]),
        Route("/api/migrate/preview", migrate_preview, methods=["POST"]),
        Route("/api/migrate/run", migrate_run, methods=["POST"]),
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
    app.add_middleware(LocalGuard, token=token)  # type: ignore[arg-type]
    app.state.token = token
    return app


def app_summary(app: Starlette) -> dict[str, Any]:  # pragma: no cover - convenience
    return {"token": app.state.token}
