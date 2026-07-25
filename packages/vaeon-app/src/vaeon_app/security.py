"""Localhost security: per-session token + Host/Origin validation.

A localhost web server is a real attack surface: a malicious page can make the browser hit
127.0.0.1 and, via DNS rebinding, slip past the same-origin policy. Defences (all here + the
127.0.0.1-only bind at launch):

* **Per-session token** minted at startup, required on every request (query ``?token=`` on the
  first open and for SSE URLs, or the ``X-Vaeon-Token`` header for fetch). Not a cookie, so
  rebinding/CSRF cannot ride it.
* **Host check** -- the ``Host`` header must be a localhost binding; a rebinding attack arrives
  with an attacker Host and is rejected.
* **Origin check** -- a cross-origin ``Origin`` on a state-changing request is rejected.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp

_ALLOWED_HOSTNAMES = frozenset({"127.0.0.1", "localhost"})


def new_token() -> str:
    return secrets.token_urlsafe(32)


def _hostname(value: str | None) -> str | None:
    if not value:
        return None
    # value may be "127.0.0.1:7357" (Host) or "http://127.0.0.1:7357" (Origin)
    return urlsplit(value if "//" in value else f"//{value}").hostname


def _request_token(request: Request) -> str | None:
    header = request.headers.get("x-vaeon-token")
    return header or request.query_params.get("token")


class LocalGuard:
    """ASGI middleware enforcing the token + Host/Origin checks. Static assets are exempt."""

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        self._app = app
        self._token = token

    async def __call__(self, scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request = Request(scope, receive)
        rejection = self._reject(request)
        if rejection is not None:
            await rejection(scope, receive, send)
            return
        await self._app(scope, receive, send)

    def _reject(self, request: Request) -> Response | None:
        if request.url.path.startswith("/static/"):
            return None  # inert assets, no data
        if _hostname(request.headers.get("host")) not in _ALLOWED_HOSTNAMES:
            return PlainTextResponse("bad host", status_code=421)
        origin = request.headers.get("origin")
        if origin is not None and _hostname(origin) not in _ALLOWED_HOSTNAMES:
            return PlainTextResponse("bad origin", status_code=403)
        if not secrets.compare_digest(_request_token(request) or "", self._token):
            return PlainTextResponse("missing or bad token", status_code=403)
        return None


Endpoint = Callable[[Request], Awaitable[Response]]
