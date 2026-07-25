"""The Starlette application: routes, SSE, static assets, wired to the service + job manager.

The app is built by :func:`create_app`, which takes the session token so tests can construct it
directly. Every data route is guarded by :class:`~vaeon_app.security.LocalGuard`.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from vaeon_core import event_review
from vaeon_core.catalog import Catalog
from vaeon_core.event_review import EventDecision, commit
from vaeon_core.events import merge_candidates, split_candidate

from vaeon_app import service
from vaeon_app.jobs import JobManager
from vaeon_app.security import LocalGuard

_PKG = Path(__file__).resolve().parent
_TEMPLATES = _PKG / "templates"
_STATIC = _PKG / "static"

#: Default catalog the app reads/writes (same default as the CLI).
_DEFAULT_DB = Path("reports/catalog.sqlite")


def create_app(*, token: str, db: Path = _DEFAULT_DB) -> Starlette:
    jobs = JobManager()

    def _db() -> Path:
        return db

    async def home(_request: Request) -> HTMLResponse:
        html = (_TEMPLATES / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(html.replace("{{TOKEN}}", token))

    async def organize_preview(request: Request) -> JSONResponse:
        body = await request.json()
        summary = service.organize_preview(Path(body["source"]), Path(body["destination"]), _db())
        return JSONResponse(summary)

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

    async def where(request: Request) -> JSONResponse:
        return JSONResponse({"copies": service.where(request.query_params.get("term", ""), _db())})

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

    async def migrate_preview(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(service.migration_preview(Path(body["path"]), _db()))

    async def migrate_run(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(
            {"job_id": jobs.start(service.migration_apply(Path(body["path"]), _db()))}
        )

    # --- Event review (session-based; merge/split are UI-only, no CLI path) ---
    sessions: dict[str, dict[str, Any]] = {}

    def _clusters_payload(session_id: str) -> JSONResponse:
        clusters = sessions[session_id]["clusters"]
        return JSONResponse(
            {"session": session_id, "clusters": [service.cluster_json(c) for c in clusters]}
        )

    async def events_propose(request: Request) -> JSONResponse:
        body = await request.json()
        resolutions, metadata = service.plan_resolve(Path(body["source"]), _db())
        clusters = event_review.propose(resolutions, metadata)
        session_id = uuid.uuid4().hex
        sessions[session_id] = {"resolutions": resolutions, "clusters": clusters}
        return _clusters_payload(session_id)

    async def events_merge(request: Request) -> JSONResponse:
        session_id = request.path_params["session"]
        indices: list[int] = (await request.json())["indices"]
        clusters = sessions[session_id]["clusters"]
        chosen = [clusters[i] for i in indices]
        rest = [c for j, c in enumerate(clusters) if j not in set(indices)]
        sessions[session_id]["clusters"] = [merge_candidates(chosen), *rest]
        return _clusters_payload(session_id)

    async def events_split(request: Request) -> JSONResponse:
        session_id = request.path_params["session"]
        body = await request.json()
        clusters = sessions[session_id]["clusters"]
        first, second = split_candidate(clusters[body["index"]], body["at"])
        clusters[body["index"] : body["index"] + 1] = [first, second]
        return _clusters_payload(session_id)

    async def events_apply(request: Request) -> JSONResponse:
        session_id = request.path_params["session"]
        names: list[str | None] = (await request.json())["names"]
        session = sessions[session_id]
        decisions = [
            EventDecision(cluster, name)
            for cluster, name in zip(session["clusters"], names, strict=True)
        ]
        with Catalog(_db()) as catalog:
            outcome = commit(session["resolutions"], decisions, catalog)
        session["resolutions"] = outcome.resolutions  # event-applied, ready for a run
        placements = [
            {"name": r.decision.source.name, "relative": r.decision.relative.as_posix()}
            for r in outcome.resolutions
            if r.decision.category.rule == "device"
        ]
        return JSONResponse({"events": len(outcome.event_ids), "placements": placements})

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
        Route("/api/migrate/preview", migrate_preview, methods=["POST"]),
        Route("/api/migrate/run", migrate_run, methods=["POST"]),
        Route("/api/events/propose", events_propose, methods=["POST"]),
        Route("/api/events/{session}/merge", events_merge, methods=["POST"]),
        Route("/api/events/{session}/split", events_split, methods=["POST"]),
        Route("/api/events/{session}/apply", events_apply, methods=["POST"]),
        Route("/api/jobs/{job_id}/events", job_events),
        Route("/api/jobs/{job_id}/cancel", job_cancel, methods=["POST"]),
        Route("/api/drives", drives),
        Route("/api/where", where),
    ]
    app = Starlette(routes=routes)
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    app.add_middleware(LocalGuard, token=token)  # type: ignore[arg-type]
    app.state.token = token
    return app


def app_summary(app: Starlette) -> dict[str, Any]:  # pragma: no cover - convenience
    return {"token": app.state.token}
