"""The sidecar must not outlive the shell that started it.

**The defect this closes: `(adh)` (f), and (c) with it.** Stage 1 measured a Tauri shell around
the existing app and found that killing the *shell* leaves the *sidecar* running. Nothing in the
sidecar notices: `__main__.release_session_link` is correct and never fires, because no signal was
ever sent to this process. So an orphaned server keeps listening and `session-url.txt` keeps
naming a live port **with a valid token**. That is the security-shaped half of the entry, and it
is why this is the first thing fixed rather than the tidiest.

**Why the fix lives here and not only in the shell.** The entry names two remedies: a
SIGTERM/SIGINT handler in the shell that kills the child, and the child terminating itself when
its parent goes. They are not alternatives. **A shell-side handler cannot cover `SIGKILL`**, which
by definition runs no handler - so the shell-side fix leaves (c) open by construction. Only the
child can close both, and only the child is testable without the shell existing yet.

**One mechanism, chosen rather than collected.** The entry offers `prctl(PR_SET_PDEATHSIG)` or a
stdin-close watchdog. `prctl` needs no cooperation from the parent, which is genuinely better -
but it is **Linux only**, and truestill ships a Windows installer beside the `.deb`. A remedy that
protects one of the two platforms we ship is not the remedy. The stdin watchdog is portable: a
parent that holds the write end of a pipe closes it by dying, whatever kills it and on all three
platforms.

⚠ **It needs the parent's cooperation, so the contract is CHECKED rather than assumed.** The
parent must spawn this process with a pipe on stdin and hold it open. If it does not - stdin is a
terminal, or absent - the watchdog would block forever on a handle nobody will ever close, and the
protection would be **silently absent**: the worst outcome, and the shape of defect this repo
keeps finding. So `require_pipe` refuses to start instead, loudly, naming what the parent did
wrong. See `ENGINEERING_STANDARD.md` §4, fiftieth member.

**Order matters on the way out, and the first step is the security one.** The credential is
cleared *before* the shutdown is requested, so it is gone even if the graceful stop is slow, wedged
behind a long job, or abrupt. A hard exit after `GRACE_SECONDS` is the backstop: a sidecar that
cannot be asked to stop is exactly the orphan this module exists to prevent, and outliving the
shell is worse than an ungraceful exit from a process whose credential is already gone.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Callable
from typing import BinaryIO

#: How long a graceful shutdown gets before the process is stopped outright. Generous enough for
#: uvicorn to finish a request, short enough that an orphan is not left serving while we wait.
GRACE_SECONDS = 5.0


class ParentPipeMissingError(RuntimeError):
    """The parent asked for the watchdog without handing over a pipe to watch."""


def require_pipe(stream: BinaryIO | None) -> BinaryIO:
    """Return ``stream`` once it is something a dying parent will close, or raise.

    **A terminal is the dangerous case, not the absent one.** With no stdin at all the watchdog
    fails obviously; with a terminal it starts, blocks, and reports nothing - a running watchdog
    that can never fire, which reads as protection and is not.
    """
    if stream is None:
        message = (
            "--parent-stdin-watch needs a pipe on stdin and this process has none. "
            "The parent must spawn it with stdin=PIPE and hold the write end open."
        )
        raise ParentPipeMissingError(message)
    try:
        is_terminal = stream.isatty()
    except (AttributeError, ValueError):  # a closed or exotic stream is not a pipe either
        is_terminal = False
    if is_terminal:
        message = (
            "--parent-stdin-watch was given a terminal on stdin, not a pipe. Nothing will ever "
            "close it, so the watchdog could never fire and this process could outlive its parent."
        )
        raise ParentPipeMissingError(message)
    return stream


def _wait_for_close(stream: BinaryIO) -> None:
    """Block until the write end goes away.

    A read of one byte, not a loop over lines: the parent never sends anything, so the only event
    this can see is the close. Any read error is treated as the close too - a pipe that has become
    unreadable is not one the parent is still holding.
    """
    try:
        stream.read(1)
    except (OSError, ValueError):
        return


def start(
    *,
    stream: BinaryIO,
    clear_credential: Callable[[], None],
    request_shutdown: Callable[[], None],
    grace_seconds: float = GRACE_SECONDS,
    hard_exit: Callable[[], None] = lambda: os._exit(0),
) -> threading.Thread:
    """Watch ``stream`` on a daemon thread; when the parent goes, stop this process.

    Returns the thread so a caller can join it in a test. Daemon, so it never holds up an
    ordinary exit - this is a safety net for an *abnormal* one.

    ``hard_exit`` is injected rather than called directly so the backstop is testable. It is
    `os._exit` in production deliberately: at that point the graceful path has already failed and
    running interpreter shutdown is exactly what we cannot rely on.
    """

    def watch() -> None:
        _wait_for_close(stream)
        # THE SECURITY STEP, FIRST AND UNCONDITIONALLY. Everything after this is tidiness; the
        # live token on disk is the part that must not survive the parent by any margin.
        clear_credential()
        request_shutdown()
        # A plain sleep, and not an Event somebody might expect to be set: **the thing that ends
        # this wait is the process exiting**, which kills this daemon thread mid-sleep. Reaching
        # the line below therefore means the graceful stop did not happen, which is the only
        # condition the backstop exists for.
        time.sleep(grace_seconds)
        hard_exit()

    thread = threading.Thread(target=watch, name="parent-watch", daemon=True)
    thread.start()
    return thread


def stdin_stream() -> BinaryIO | None:
    """This process's binary stdin, or ``None`` when it has none.

    A frozen, console-less Windows build has `sys.stdin` set to ``None``, and a detached process
    can have it closed. Both are the parent failing its side of the contract, and both must reach
    `require_pipe` as ``None`` rather than as an exception from attribute access.
    """
    stream = getattr(sys, "stdin", None)
    if stream is None:
        return None
    return getattr(stream, "buffer", None)
