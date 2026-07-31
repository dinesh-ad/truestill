"""The way back into a running app when the browser did not open.

**The defect this closes ((aad)).** The session token is minted per process, never persisted,
and printed once to a console a double-clicked app does not have. The only path to the app was
``webbrowser.open(url)`` with its **return value discarded** - and it returns ``False`` when no
browser is found, which is the normal case on a Linux box with no ``DISPLAY``. The app would be
running, listening, and unreachable; restarting mints a *different* token, so there was no
second chance.

**Why a file.** A tray icon or a desktop notification are per-platform UI dependencies a
local-web app does not otherwise need, and each would have to be bundled and signed. A file
costs nothing, behaves identically on three platforms, and can be read out over the phone or
grepped by whoever is helping.

**It is a credential.** The URL contains the token, so it is created with mode ``0600`` **at
open time** rather than chmod-ed afterwards - the latter leaves a window, however short, in
which the file exists with the default mode. Windows ignores POSIX modes; there the protection
is that the data directory lives inside the user's own profile, whose ACL is user-scoped. That
is weaker than ``0600`` and is stated rather than glossed: on a shared Windows machine an
administrator can read it, exactly as they can read anything else in the profile.

**It is replaced, never appended.** Two URLs in one file is two guesses, and only the newest is
a way in.

**It is removed when the process exits**, including on a crash, because a file that outlives its
process is a link that fails confusingly tomorrow.
"""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path

from truestill_core.app_paths import session_url_path

#: Written under the URL. The reader is someone whose app did not open, so it explains what the
#: file is and why it will not work tomorrow - the two things that would otherwise be guessed.
_NOTE = """
This is the web address of the Truestill window that is running right now.
Open the line above in your browser.

Keep it to yourself: anyone with this address can reach your library while
Truestill is running. It changes every time Truestill starts, and this file
is removed when it stops, so an address you saved earlier will not work.
"""


def path() -> Path:
    """Where the file lives. Delegates to `app_paths`, which owns every such answer."""
    return session_url_path()


def write(url: str) -> Path:
    """Record ``url`` as the way into this session, readable only by this user.

    ``O_CREAT | O_WRONLY | O_TRUNC`` with mode ``0600``: created private, truncated so a previous
    session cannot survive underneath, and never appended.
    """
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # os.open rather than Path.write_text: the mode has to be applied by the syscall that
    # creates the file, not by a chmod afterwards.
    fd = os.open(target, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"{url}\n{_NOTE}")
    return target


def clear() -> None:
    """Remove the file. Never raises: failing to clean up must not take the app down with it."""
    path().unlink(missing_ok=True)


def open_browser(url: str) -> bool:
    """Attempt to open ``url``, reporting honestly whether it worked.

    Wrapped rather than called directly so the launch path has one thing to patch in tests, and
    so a `webbrowser` that raises (rather than returning ``False``) is treated as the failure it
    is instead of taking the process down after the server was already reachable.
    """
    try:
        return bool(webbrowser.open(url))
    except Exception:  # any browser failure is the same outcome to the caller
        return False
