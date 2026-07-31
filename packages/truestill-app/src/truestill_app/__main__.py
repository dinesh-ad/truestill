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
from pathlib import Path
from typing import Any

import uvicorn
from truestill_core.app_paths import default_catalog_path
from truestill_core.catalog_startup import (
    CatalogPresence,
    format_startup_lines,
    inspect_catalog,
)

from truestill_app import session_link
from truestill_app.security import new_token
from truestill_app.server import create_app

_HOST = "127.0.0.1"
_DEFAULT_PORT = 7357

#: Grace before the browser is pointed at the server. Replaced by a real readiness signal in
#: the commit that fixes the race; kept here so adding the URL file does not change timing.
_BROWSER_DELAY_SECONDS = 0.5


def uvicorn_log_config() -> dict[str, Any]:
    """Logging for uvicorn that does not ask the console whether it is a terminal.

    **Why this exists rather than uvicorn's default.** A double-clicked desktop app has no
    console - ``pythonw.exe``, a PyInstaller ``--noconsole`` build and a packaged GUI app all
    leave ``sys.stdout`` and ``sys.stderr`` as ``None``. uvicorn's default formatter calls
    ``.isatty()`` on the stream to decide about colour, so configuring it raises
    ``ValueError: Unable to configure formatter 'default'`` (from ``AttributeError: 'NoneType'
    object has no attribute 'isatty'``) and the process dies **before the server binds**. The
    user sees nothing happen at all.

    Colour is what the sniffing was for, and a local app that mostly runs windowed has no use
    for it, so this drops the question rather than answering it more carefully.

    With no console the handler writes **nowhere** - `logging.NullHandler` - rather than to a
    stream that is not there. With a console it behaves as before.

    **Before simplifying this: the formatter is the load-bearing part, not the handler.** Both
    were mutation-tested and the result was not what it looked like. Removing the
    ``NullHandler`` branch fails only its own test - a `StreamHandler` over a ``None`` stream
    configures perfectly well and fails per *record*, which logging swallows - so that branch is
    a correctness refinement. Reverting to uvicorn's own config is what reproduces the startup
    crash. Anyone collapsing this back to one handler is safe; anyone restoring uvicorn's
    ``log_level=`` default re-breaks every windowed build.
    """
    if sys.stderr is None:
        handler: dict[str, Any] = {"class": "logging.NullHandler"}
    else:
        handler = {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "stream": "ext://sys.stderr",
        }
    return {
        "version": 1,
        # Never disable loggers the rest of the process already set up: this config is about
        # uvicorn's three loggers and has no business silencing anything else.
        "disable_existing_loggers": False,
        "formatters": {"plain": {"format": "%(levelname)s: %(message)s"}},
        "handlers": {"default": handler},
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "WARNING", "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": "WARNING", "propagate": False},
            "uvicorn.access": {"handlers": ["default"], "level": "WARNING", "propagate": False},
        },
    }


def _say(line: str, *, error: bool = False) -> None:
    """Startup output, through one function so there is one place to change where it goes.

    With a console it prints as it always did. **With no console it goes nowhere**, and that is
    a decision rather than an accident: `print` happens to be a silent no-op when
    ``sys.stdout`` is ``None``, and relying on that quietly would leave the next reader unsure
    whether the case had been considered. There is no channel to route it to at this point;
    the session URL gets a durable home of its own, which is the line that actually matters.
    """
    print(line, file=sys.stderr if error else sys.stdout, flush=True)


def _attempt_browser(url: str, written: Path) -> None:
    """Open the app, and say where the address is when that fails.

    ``webbrowser.open`` returns ``False`` when it finds no browser at all - the ordinary case on
    a headless Linux box - and discarding that return value is what left a running app
    unreachable. When there is no console this message goes nowhere, which is precisely why the
    file is written first and why its location is fixed rather than announced.
    """
    if session_link.open_browser(url):
        return
    _say(f"Could not open a browser. The address is in {written}", error=True)


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
        _say(line, error=info.presence is CatalogPresence.EMPTY_WITH_DRIVES)

    token = new_token()
    port = _choose_port(args.port)
    url = f"http://{_HOST}:{port}/?token={token}"
    app = create_app(token=token, db=db, explicit_db=explicit_db)

    _say(f"truestill UI on {url}")
    # Before the browser is attempted, never after: a failed open must still leave a way in.
    written = session_link.write(url)

    if not args.no_browser:
        # Still deferred, still a timer. Opening it synchronously here would guarantee the
        # browser reached a port uvicorn has not bound yet - the race is real and is fixed on
        # its own, not by quietly making it worse while adding the file.
        threading.Timer(_BROWSER_DELAY_SECONDS, _attempt_browser, (url, written)).start()

    try:
        uvicorn.run(app, host=_HOST, port=port, log_config=uvicorn_log_config())
    finally:
        # Also on crash and on Ctrl-C: a file that outlives its process is a link that fails
        # confusingly tomorrow, against a port that is dead or, worse, answering for someone
        # else's session.
        session_link.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
