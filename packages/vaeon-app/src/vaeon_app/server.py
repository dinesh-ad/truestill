"""The Starlette application: routes, SSE, static assets, wired to the service + job manager.

The app is built by :func:`create_app`, which takes the session token so tests can construct it
directly. Every data route is guarded by :class:`~vaeon_app.security.LocalGuard`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

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
        target = service.organize_run(Path(body["source"]), Path(body["destination"]), _db())
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

    routes = [
        Route("/", home),
        Route("/api/organize/preview", organize_preview, methods=["POST"]),
        Route("/api/organize/run", organize_run, methods=["POST"]),
        Route("/api/verify/run", verify_run, methods=["POST"]),
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
