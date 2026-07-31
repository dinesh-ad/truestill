"""Launch the local app: pick a port, bind 127.0.0.1 only, open the browser at the token URL.

Port strategy (Syncthing/qBittorrent style): try a fixed default, fall back to an ephemeral free
port if it is taken. The browser is opened at the exact URL including the session token, so the
first request is authenticated and no configuration is needed.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn
from truestill_core.app_paths import default_catalog_path
from truestill_core.catalog_startup import (
    CatalogPresence,
    format_startup_lines,
    inspect_catalog,
)

from truestill_app.security import new_token
from truestill_app.server import create_app

_HOST = "127.0.0.1"
_DEFAULT_PORT = 7357


def _choose_port(preferred: int) -> int:
    """Return ``preferred`` if free, else an OS-assigned ephemeral port."""
    for candidate in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((_HOST, candidate))
                return int(sock.getsockname()[1])
            except OSError:
                continue
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="truestill-app", description="truestill local web UI")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"SQLite catalog (default: {default_catalog_path()})",
    )
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    args = parser.parse_args(argv)

    explicit_db = args.db is not None
    db = args.db if explicit_db else default_catalog_path()
    info = inspect_catalog(db, explicit_db=explicit_db)
    for line in format_startup_lines(info):
        stream = sys.stderr if info.presence is CatalogPresence.EMPTY_WITH_DRIVES else sys.stdout
        print(line, file=stream, flush=True)

    token = new_token()
    port = _choose_port(args.port)
    url = f"http://{_HOST}:{port}/?token={token}"
    app = create_app(token=token, db=db, explicit_db=explicit_db)

    print(f"truestill UI on {url}", flush=True)  # noqa: T201 - the URL (with token) is the point
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=_HOST, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
