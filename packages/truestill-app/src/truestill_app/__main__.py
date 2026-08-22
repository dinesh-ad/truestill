"""Launch the local app: pick a port, bind 127.0.0.1 only, open the browser at the token URL.

Port strategy (Syncthing/qBittorrent style): try a fixed default, fall back to an ephemeral free
port if it is taken. The browser is opened at the exact URL including the session token, so the
first request is authenticated and no configuration is needed.
"""

from __future__ import annotations

import argparse
import contextlib
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn
from truestill_core import binaries
from truestill_core.app_paths import (
    default_catalog_path,
    resolve_catalog_choice,
    session_url_path,
)
from truestill_core.catalog_startup import (
    CATALOG_UNUSABLE_EXIT,
    CatalogUnusableError,
    format_startup_lines,
    inspect_catalog,
    refuse_unusable_catalog,
)
from truestill_core.drive_unwritable import explain_unwritable_folder
from truestill_core.selfcheck import is_complete, render, write_findings

from truestill_app import parent_watch, session_link
from truestill_app.security import new_token
from truestill_app.selfcheck import app_findings
from truestill_app.server import create_app

_HOST = "127.0.0.1"
_DEFAULT_PORT = 7357

#: Where a windowed self-check leaves its report - beside `session-url.txt`, in the data
#: directory, for the same reason: the one place a confused user can be pointed at.
_REPORT_FILENAME = "self-check.txt"

#: Pending-connection queue depth for the listening socket. Only ever one browser, but the
#: kernel default varies and a named constant is cheaper than wondering.
_BACKLOG = 128

#: How often readiness is re-checked, and how long to wait before giving up on the server ever
#: starting. A poll interval, not a guess at startup time - the difference from the timer this
#: replaced is that nothing is assumed about how long binding takes.
_READY_POLL_SECONDS = 0.02
_READY_TIMEOUT_SECONDS = 30.0


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


#: Signals that mean "stop now" and are worth cleaning up for. ``SIGBREAK`` exists only on
#: Windows, so it is looked up rather than imported.
_TERMINATING_SIGNALS = tuple(
    sig
    for sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGBREAK", None))
    if sig is not None
)


def release_session_link(signum: int, _frame: object) -> None:
    """Remove the session URL file, then die the way the signal asked.

    **Why a handler and not just the ``finally``.** uvicorn's `Server.capture_signals` installs
    its own handlers, shuts down gracefully, restores the **original** ones, and then re-raises
    the captured signal at itself so the parent sees the conventional exit status. By then the
    restored handler is in charge, so on ``SIGTERM`` the process dies *inside* ``server.run()``
    and the ``finally`` below it is never reached. Measured: a bare ``try/finally`` around
    ``server.run()`` leaves no marker after a ``SIGTERM``.

    ``SIGINT`` happened to work already, for a reason worth knowing rather than relying on:
    Python's default ``SIGINT`` handler raises `KeyboardInterrupt`, which propagates out of
    ``server.run()`` and *does* reach the ``finally``. So Ctrl-C cleaned up and ``kill`` did not.

    This rides uvicorn's mechanism instead of fighting it. Installed **before** ``server.run()``,
    this is the handler uvicorn snapshots and restores, so the re-raise lands here: clear the
    file, put the default back, and re-raise so the exit status is still the conventional one.
    """
    session_link.clear()
    signal.signal(signum, signal.SIG_DFL)
    signal.raise_signal(signum)


def _attempt_browser(url: str, written: Path | None) -> None:
    """Open the app, and say where the address is when that fails.

    ``webbrowser.open`` returns ``False`` when it finds no browser at all - the ordinary case on
    a headless Linux box - and discarding that return value is what left a running app
    unreachable. When there is no console this message goes nowhere, which is precisely why the
    file is written first and why its location is fixed rather than announced.

    ⚠ **``written`` is ``None`` when the file could not be written**, and then the address is
    given directly. Pointing someone at a path that does not exist is the failure `(aey)` is
    about - *not there* offered as though it were *there* - and it would have been introduced by
    the very guard that stopped the launch crashing. `(aeo)`
    """
    if session_link.open_browser(url):
        return
    if written is None:
        _say(f"Could not open a browser. The address is: {url}", error=True)
        return
    _say(f"Could not open a browser. The address is in {written}", error=True)


def bind_listening_socket(preferred: int) -> socket.socket | None:
    """A socket bound and **listening** on ``preferred``, else an ephemeral port, else ``None``.

    Listening here rather than leaving it to uvicorn is what removes the browser race. From the
    moment ``listen`` returns, the kernel **queues** incoming connections until uvicorn calls
    ``accept`` - so a browser opened now waits rather than being refused. Measured: a connect to
    a listening socket nobody has accepted yet succeeds.

    It also closes a second race that was never noticed. The previous version bound a socket to
    discover a free port, **closed it**, and let uvicorn bind again - leaving a window in which
    another process could take the port truestill had just announced. The socket is now held
    from discovery until it is handed over.

    ``None`` means neither the requested port nor any ephemeral one could be bound, which is a
    reason not to start rather than something to work around.
    """
    for candidate in (preferred, 0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((_HOST, candidate))
            sock.listen(_BACKLOG)
        except OSError:
            sock.close()
            continue
        return sock
    return None


def open_when_ready(server: Any, url: str, written: Path | None) -> None:
    """Open the browser once ``server`` reports itself started, and not before or otherwise.

    **Not uvicorn's ASGI startup hook, which is not the guarantee it looks like.**
    ``Server.startup`` awaits ``lifespan.startup()`` *before* creating any socket, so a connect
    from inside that hook is refused. Using it would have traded the timer for a second race
    wearing a more reassuring name.

    ``server.started`` is set after the listening sockets are in place - the same signal
    `tests/e2e/conftest.py` waits on. Polling it is a *readiness wait*, not a guess at how long
    startup takes, which is the difference between this and the timer it replaces.

    If the server exits or never comes up, the browser is **not** opened: a window pointing at
    an app that failed to start shows a broken page and blames the wrong thing.
    """
    deadline = time.monotonic() + _READY_TIMEOUT_SECONDS
    while not server.started:
        if server.should_exit or time.monotonic() > deadline:
            return
        time.sleep(_READY_POLL_SECONDS)
    _attempt_browser(url, written)


def _run_self_check(destination: str) -> int:
    """`--self-check`: say what this installation contains, then exit. Never starts a server.

    **The exit code is the machine-readable half and is not optional.** A packaging job should be
    able to fail on a broken bundle without parsing prose, and `(aad)`'s acceptance criteria are
    exactly the kind of thing a job must be able to gate on.

    **A path is offered because a windowed build has no console.** `_say` goes nowhere there -
    stated in its own docstring - so on the platform this check exists for, printing is not a
    delivery mechanism. `write_findings` is; it is the same reasoning, and the same atomic write,
    the windowed-launch probe already established.

    It runs **before** anything binds a socket or opens a catalog: an install being asked whether
    it is intact must not have to be working in order to answer.
    """
    findings = app_findings()
    if destination:
        written = write_findings(findings, Path(destination))
        _say(f"self-check written to {written}")
    elif sys.stdout is None:
        # NO CONSOLE - the Start-menu case. `_say` is a silent no-op here, so printing would make
        # the shortcut appear to do nothing at all, which is worse than not offering it. Write the
        # report where the user's own files live and hand it to whatever they open text with.
        # This is the thing `exif.py`'s "this installation looks incomplete" has never had: an
        # answer the reader can actually reach.
        written = write_findings(findings, session_url_path().with_name(_REPORT_FILENAME))
        opener = binaries.os_opener()
        if opener is not None:
            with contextlib.suppress(OSError):
                binaries.popen(
                    [opener, str(written)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
    else:
        for line in render(findings):
            _say(line)
    return 0 if is_complete(findings) else 1


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
    parser.add_argument(
        "--parent-stdin-watch",
        action="store_true",
        help=(
            "stop when the parent process does, by watching for stdin to close. The parent must "
            "spawn this with stdin=PIPE and hold the write end open"
        ),
    )
    parser.add_argument(
        "--self-check",
        nargs="?",
        const="",
        default=None,
        metavar="PATH",
        help=(
            "report what this installation contains and exit; with PATH, write the report there "
            "as JSON instead of printing it"
        ),
    )
    args = parser.parse_args(argv)

    if args.self_check is not None:
        return _run_self_check(args.self_check)

    explicit_db = args.db is not None
    db = args.db if explicit_db else default_catalog_path()
    info = inspect_catalog(db, explicit_db=explicit_db)
    # See the CLI's copy: the choice is only meaningful when nobody named a path. `(adv)`.
    for line in format_startup_lines(info, None if explicit_db else resolve_catalog_choice()):
        # By tone rather than by presence, for the reason the CLI's copy of this gives.
        _say(line, error=info.tone == "alert")
    try:
        # BEFORE THE SOCKET, deliberately. Refusing after the bind would leave a listener and a
        # session-url file behind for a process that then quits - something claiming an address
        # it never served, which is the state `bind_listening_socket`'s own failure path exists
        # to avoid. `(adr)`.
        refuse_unusable_catalog(info)
    except CatalogUnusableError:
        return CATALOG_UNUSABLE_EXIT

    sock = bind_listening_socket(args.port)
    if sock is None:
        # No socket, no app. Nothing is announced and no URL file is written, so nothing is
        # left claiming an address that was never served.
        _say(
            f"Could not listen on {_HOST}. Is another copy of Truestill already running?",
            error=True,
        )
        return 1

    # From here to the handover the process owns two things it must not abandon: the listening
    # socket, and - once written - the credential file. `ExitStack` rather than nested `try`
    # blocks because they have different lifetimes (the socket's ownership ends AT the handover,
    # the link's continues past it) and because any of the eleven statements between can raise.
    with contextlib.ExitStack() as launching:
        launching.callback(sock.close)

        token = new_token()
        port = int(sock.getsockname()[1])
        url = f"http://{_HOST}:{port}/?token={token}"
        app = create_app(token=token, db=db, explicit_db=explicit_db)

        _say(f"truestill UI on {url}")

        # BEFORE the file is written, not after. uvicorn snapshots the handlers that exist when it
        # starts and restores them before re-raising, so these are the ones the re-raise lands on -
        # that is why they go in before `server.run`. They go in before `session_link.write` for a
        # second, separate reason: between writing the credential and installing these, a SIGTERM
        # hit Python's default disposition, the process died without running `release_session_link`,
        # and the file survived. Small window, real: it showed up as an intermittent failure in
        # `test_a_real_process_leaves_no_url_file_behind`, which signals the instant the file
        # appears. A flaky test and a stale credential left on a user's disk were the same bug seen
        # from two sides. Installing first is free - the handler only unlinks, and unlinking a file
        # that does not exist yet is already a no-op.
        for terminating in _TERMINATING_SIGNALS:
            signal.signal(terminating, release_session_link)

        # Before the browser is attempted, never after: a failed open must still leave a way in.
        #
        # ⚠ **DEGRADE, NEVER REFUSE, AND THE MODULE HAD ALREADY RULED THIS TWICE.** `(aeo)` left
        # "stop the launch or degrade" undecided; `session_link`'s own docstring answers it -
        # when a filesystem discards the mode the file is still written, because *"warning beats
        # refusing"* - and `session_link.clear` is documented *"never raises: failing to clean up
        # must not take the app down with it"*. A full or read-only home directory used to end
        # the launch in an interpreter stack trace before anything was served. The server IS the
        # product; this file is one of two ways in and the browser below is the other, so losing
        # it costs a fallback, not the app.
        link: session_link.SessionLink | None
        try:
            link = session_link.write(url)
        except OSError as exc:
            # §9: a sentence, never an errno, and the FOLDER wording rather than the drive's -
            # there is no drive in this story and naming one sends the user after hardware.
            link = None
            _say(
                f"Could not save the address to {session_link.path()}: "
                f"{explain_unwritable_folder(exc)}. Truestill is still starting.",
                error=True,
            )
        else:
            launching.callback(session_link.clear)
        if link is not None and not link.private:
            # A drive with no permission bits (FAT32, exFAT) discarded the mode. Said here as well
            # as in the file, because a user who is watching a console is exactly the one who can
            # still act on it before anyone else reads the token.
            _say(
                f"Note: {link.path} could not be made private on this drive - drives formatted "
                f"FAT32 or exFAT do not store file permissions, so anyone with an account on this "
                f"computer can read the address.",
                error=True,
            )

        server = uvicorn.Server(
            uvicorn.Config(app, host=_HOST, port=port, log_config=uvicorn_log_config())
        )

        if args.parent_stdin_watch:
            # `(adh)` (f)/(c): a shell that dies leaves this process serving, with
            # `session-url.txt` still naming a live port and a valid token. No signal reaches us,
            # so `release_session_link` never runs. See `parent_watch` for why the fix has to be
            # here rather than only in the shell, and why the pipe is checked rather than assumed.
            #
            # Wired AFTER the link exists, so `clear_credential` can only ever remove a file this
            # process actually wrote - and before `server.run`, so the watch covers the whole time
            # there is anything to serve.
            parent_watch.start(
                stream=parent_watch.require_pipe(parent_watch.stdin_stream()),
                clear_credential=session_link.clear,
                # `should_exit` rather than a signal: it unwinds uvicorn the same way on all three
                # platforms, where `os.kill(SIGTERM)` on Windows is an abrupt TerminateProcess
                # that would skip every cleanup below.
                request_shutdown=lambda: setattr(server, "should_exit", True),
            )
        if not args.no_browser:
            threading.Thread(
                # `None` when the write failed, so the fallback message below cannot send someone
                # to a file that does not exist - which is the defect the guard above would
                # otherwise have created. `(aeo)`
                target=open_when_ready,
                args=(server, url, link.path if link is not None else None),
                daemon=True,
            ).start()

        # OWNERSHIP BOUNDARY - the line a refactor will move without realising what it means.
        # Past here uvicorn owns the socket and closes it in `Server.shutdown()`, so closing it
        # ourselves would make two owners; closing it any earlier hands over a dead socket and
        # breaks every normal start. `pop_all` drops both cleanups: the link's is picked up
        # again by the `finally` below, which has to run after a clean shutdown as well.
        #
        # Cleanups run in reverse registration order, so a failure clears the credential BEFORE
        # releasing the port. That way nothing can take the port while a file still names it
        # with a live token.
        launching.pop_all()

    try:
        server.run(sockets=[sock])
    finally:
        # Also on crash and on Ctrl-C: a file that outlives its process is a link that fails
        # confusingly tomorrow, against a port that is dead or, worse, answering for someone
        # else's session.
        session_link.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
