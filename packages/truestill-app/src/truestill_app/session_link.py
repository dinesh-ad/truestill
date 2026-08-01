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

**It is a credential.** The URL contains the token, so the file is created with mode ``0600``
by the call that creates it, never chmod-ed afterwards. Windows ignores POSIX modes; there the
protection is that the data directory lives inside the user's own profile, whose ACL is
user-scoped. That is weaker than ``0600`` and is stated rather than glossed: on a shared Windows
machine an administrator can read it, exactly as they can read anything else in the profile.

**The mode is verified, not assumed.** FAT32 and exFAT have no permission bits at all: they
accept ``0600``, ignore it, and report whatever the mount's ``fmask`` says - commonly ``0777``.
A portable install, a live USB, or a home directory on a removable drive puts this file exactly
there. So the mode is read back after creation and, when it did not take, **the file says so and
the console says so**.

*Warn, do not refuse.* Refusing to write would restore the exact defect above - a running,
listening, unreachable app - and trading a confidentiality weakening for a total loss of access
is the worse deal. Writing it somewhere else was rejected too: `app_paths` owns where every such
file lives, and a credential that relocates to a second, unpredictable place is harder to find
and harder to clean up than one that is where it always is and admits what it could not do.

**It is replaced, never appended.** Two URLs in one file is two guesses, and only the newest is
a way in.

**It is removed when the process exits**, including on a crash, because a file that outlives its
process is a link that fails confusingly tomorrow.
"""

from __future__ import annotations

import stat
import webbrowser
from dataclasses import dataclass
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


#: Appended when the filesystem discarded the mode. Names the filesystem family rather than the
#: mechanism, because "0600 was not applied" is not something a photo user can act on and
#: "this drive cannot keep files private" is.
_NOT_PRIVATE = """
NOTE: this file could not be made private on this drive. Drives formatted
FAT32 or exFAT do not store file permissions, so anyone with an account on
this computer can read the address above. Stop Truestill when you are done,
which removes this file.
"""


def path() -> Path:
    """Where the file lives. Delegates to `app_paths`, which owns every such answer."""
    return session_url_path()


def mode_is_private(mode: int) -> bool:
    """Whether ``mode`` keeps other users out.

    Asks the question that matters - can anyone else read this - rather than comparing against
    ``0600`` exactly, which would call a correct ``0400`` file a failure and would still say
    nothing about who can read it.
    """
    return not mode & (stat.S_IRWXG | stat.S_IRWXO)


@dataclass(frozen=True, slots=True)
class SessionLink:
    """Where the way back in was written, and whether it could be kept to this user."""

    path: Path
    #: ``False`` when the filesystem ignored the mode (FAT32, exFAT). Never silently ``True``:
    #: it is read back from the file that was actually created.
    private: bool


def write(url: str) -> SessionLink:
    """Record ``url`` as the way into this session, readable only by this user where possible.

    Created private, replacing whatever was there, and never appended. When the filesystem
    ignores the mode, the file is still written - see the module docstring for why warning beats
    refusing - and it carries the warning itself, because the person reading it is by definition
    someone with no console to have seen one on.
    """
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Remove first, then create with the mode, then write. All three steps matter and none is
    # ceremony - see ENGINEERING_STANDARD's pathlib rule, where the measurements live:
    #
    #   unlink   - a mode is applied only when a file is CREATED, so writing over an existing
    #              file keeps whatever mode it already had. It also drops a symlink sitting at
    #              this path instead of writing the token through it to somewhere else.
    #   touch    - `Path.touch(mode=...)` sets permissions at creation. `Path.open` has no
    #              permissions parameter at all, and `write_text` alone yields the umask default
    #              (0664 on this machine) - the token readable by the whole group.
    #   write    - truncating is safe now: the file it truncates is the empty 0600 one above.
    target.unlink(missing_ok=True)
    target.touch(mode=0o600)
    # Read back rather than trusted: `touch` reports success on a filesystem that discarded the
    # mode, so the only honest source for "is this private" is the file that now exists.
    private = mode_is_private(stat.S_IMODE(target.stat().st_mode))
    warning = "" if private else _NOT_PRIVATE
    target.write_text(f"{url}\n{_NOTE}{warning}", encoding="utf-8")
    return SessionLink(path=target, private=private)


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
