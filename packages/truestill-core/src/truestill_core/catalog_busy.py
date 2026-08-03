"""The one SQLite failure that is a normal condition rather than a fault.

Two truestill processes can want the catalog at the same moment: an ``--apply`` run in a
terminal while the app is open is the ordinary case, not an abuse. SQLite serialises them, so
the catalog **cannot be corrupted** by it -- measured 2026-08-03, and that is what makes this a
presentation fix rather than a data-safety one. What actually happens is that the second writer
waits out ``busy_timeout`` (5 s, Python's ``connect(timeout=5.0)`` default) and then raises
``sqlite3.OperationalError: database is locked``. That exception was caught nowhere, so an
expected, retryable condition arrived as a traceback in the middle of a run.

**Discriminated on the error code, never the message.** ``OperationalError`` also covers a disk
I/O error, a malformed schema and a read-only database, and dressing those up as "try again in a
minute" would send a user to wait out a fault that will never clear. Python exposes SQLite's own
code as ``sqlite_errorcode`` on exceptions the module raises (3.11+; this repo requires 3.13), so
the check is exact. Message text would also be a second thing SQLite could reword.

**Why this lives in core.** ``truestill-cli`` and ``truestill-app`` both depend on
``truestill-core`` and neither depends on the other, so core is the only home the two surfaces
share -- and ENGINEERING_STANDARD.md §4 rules that the remedy for one contract written twice is
one home, not a second test. Only *recognition and wording* are here. Presentation stays with
each surface, which is where it differs: the CLI has an exit code and stderr, the app has an SSE
terminal event and an HTTP status.
"""

from __future__ import annotations

import sqlite3

#: SQLITE_BUSY (5) is another connection holding the lock; SQLITE_LOCKED (6) is a conflict
#: within the same connection's table locks. Both mean *wait and retry*, and both are what the
#: 5 s ``busy_timeout`` has already failed to outlast by the time we see one.
_BUSY_CODES = frozenset({sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED})

#: Travels to the browser as a terminal event's ``code`` and to an HTTP refusal's ``code``.
#: Exception-class-shaped because that is the app's existing convention for a known situation
#: (``jobs.py`` sends ``type(exc).__name__``, ``app.js`` matches on it) -- so a later
#: ``FRIENDLY_ERRORS`` entry can key off it without the payload shape changing.
CATALOG_BUSY_CODE = "CatalogBusy"

#: Deliberately does **not** claim nothing changed. A busy catalog is hit mid-run as often as at
#: the start -- ``_record_organized_file`` writes per file, after each copy -- so "nothing was
#: changed" would be false exactly when the user most needs to trust it. It also does not name
#: the holding process: without the on-disk lock of BACKLOG `(aaw)` we cannot know which process
#: or which operation it is, and a guess here is worse than the gap.
CATALOG_BUSY_MESSAGE = (
    "Another Truestill operation is using the library catalog, so this one stopped rather than "
    "wait any longer. Nothing was left half-written; a file is recorded only after it has been "
    "copied safely, though a run already under way may have copied some files before it "
    "stopped. Wait for the other operation to finish, or close the other Truestill window, or "
    "stop the other command in your terminal, then run this again."
)


def is_catalog_busy(exc: BaseException) -> bool:
    """Whether ``exc`` is the catalog being held by someone else, rather than a fault.

    ``getattr`` rather than attribute access because ``sqlite_errorcode`` is set by the module
    on the exceptions it raises, and is absent on one constructed by hand -- which is what a
    test double or a re-raise from our own code looks like. Absent means "not known to be
    busy", which is the safe answer: an unrecognised failure keeps its traceback.
    """
    return isinstance(exc, sqlite3.Error) and getattr(exc, "sqlite_errorcode", None) in _BUSY_CODES
