"""Which SQLite failures are a normal condition, and which are a fault. `(aeu)` `(afe)`

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
code as ``sqlite_errorcode`` on exceptions the module raises (3.11+; this repo requires 3.14), so
the check is exact. Message text would also be a second thing SQLite could reword.

⚠ **``sqlite_errorcode`` carries EXTENDED codes, so every comparison here masks with
``& 0xFF``.** An extended code is ``primary | (sub << 8)``. Measured 2026-08-22: a catalog whose
*directory* is read-only raises **1544**, which is ``SQLITE_READONLY_DIRECTORY`` -- ``8 | (6 <<
8)`` -- and **not** ``SQLITE_READONLY``. The same trap runs the other way and was live here: this
module compared the raw code against ``{5, 6}``, so ``SQLITE_BUSY_RECOVERY`` (261),
``SQLITE_BUSY_SNAPSHOT`` (517) and ``SQLITE_BUSY_TIMEOUT`` (773) all answered *not busy* and would
have stopped a run that should have waited. A plain contended write returns the primary ``5``,
which is why it never bit. `(afe)`

**Why this lives in core.** ``truestill-cli`` and ``truestill-app`` both depend on
``truestill-core`` and neither depends on the other, so core is the only home the two surfaces
share -- and ENGINEERING_STANDARD.md §4 rules that the remedy for one contract written twice is
one home, not a second test. Only *recognition and wording* are here. Presentation stays with
each surface, which is where it differs: the CLI has an exit code and stderr, the app has an SSE
terminal event and an HTTP status.
"""

from __future__ import annotations

import errno
import random
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

#: SQLITE_BUSY (5) is another connection holding the lock; SQLITE_LOCKED (6) is a conflict
#: within the *same* connection's table locks, or a shared cache.
#:
#: ⚠ **They are grouped, and "both mean wait and retry" -- which this comment said until
#: 2026-08-22 -- is FALSE for LOCKED here.** `catalog.py` opens one connection and does not use a
#: shared cache, so a genuine SQLITE_LOCKED would be a conflict with ourselves: we would be
#: waiting for a lock only we could release, and retrying it can never clear. On the evidence it
#: belongs on the permanent side.
#:
#: It stays grouped for one narrow reason: :func:`retry_while_busy` gives up after a bounded
#: number of attempts and the caller then takes the permanent path anyway, so the escalation
#: converges on the right answer. The imprecision costs retry latency on a case that cannot
#: happen without a bug of ours -- and splitting it would be a second vocabulary for a condition
#: with no observed instance. If one is ever observed, this is the comment that says what to do.
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


#: The busy sentence for a single HTTP request, `(agp)` part 1. **A separate sentence from
#: `CATALOG_BUSY_MESSAGE` because the honest claims differ**: a run may have copied files before
#: it stopped, so its message must not say "nothing changed" - but it can talk about copies. A
#: request is one transaction that rolled back, and talking about copied files there would be
#: noise about a run that does not exist.
#:
#: ⚠ **It asserts no second window.** `(agp)`'s reproduction showed the same "close the other
#: Truestill window" sentence for a one-process first-run build and for a non-Truestill holder
#: alike. Until detection exists (the `(agp)` ladder), a window is named only as one possibility
#: among the three real causes - never as an instruction to close something asserted to exist.
CATALOG_BUSY_REQUEST_MESSAGE = (
    "The library catalog is busy right now, so this could not be completed. It usually clears "
    "in a few seconds - try again. If it keeps happening, another program or another Truestill "
    "window may be holding the catalog file."
)

#: How many attempts a single HTTP request makes before refusing, `(agp)` part 1. ⚠ **Two, and
#: the bound is ruled from a measurement, not a feeling.** Each attempt already waits out the
#: driver's 5 s ``busy_timeout``, and the only holder measured above single digits of
#: milliseconds is the once-per-catalog fresh-schema build at <= 5.1 s (`(adt)` M4) - so one
#: extra attempt after the first 5 s wait covers it, and a second click's worth (~10 s worst)
#: is the most a person waiting on a radio button should be held. More attempts would not help
#: anyone: past the build, a still-busy catalog is sustained contention, and hiding that behind
#: a minute of silent retrying is the failure mode `_BUSY_ATTEMPTS`'s own docstring warns about
#: in the other direction. A RUN retries ~10 times because giving up costs an unrecorded file
#: and no human is blocked waiting; a request is watched by a person and costs one click to
#: repeat.
REQUEST_BUSY_ATTEMPTS = 2


def primary_code(exc: BaseException) -> int | None:
    """SQLite's primary result code for ``exc``, or ``None`` if it does not carry one.

    ``getattr`` rather than attribute access because ``sqlite_errorcode`` is set by the module
    on the exceptions it raises, and is absent on one constructed by hand -- which is what a
    test double or a re-raise from our own code looks like.

    The ``& 0xFF`` is the whole point of this function; see the module docstring.
    """
    code = getattr(exc, "sqlite_errorcode", None)
    return None if code is None else int(code) & 0xFF


#: The catalog could not be written for a reason **about reaching or storing it** -- permissions,
#: read-only media, a missing folder, failing hardware, a full disk. Enumerated rather than
#: complemented, and the difference from :func:`is_catalog_write_permanent` is the point:
#:
#: * *"should we retry?"* has a safe default of **no**, so unknown codes fall on the not-busy
#:   side and stop the run.
#: * *"should we tell the user their catalog cannot be written?"* has a safe default of **no**
#:   too -- but that is the *other* side. ``SELECT * FROM no_such_table`` is ``SQLITE_ERROR``: a
#:   bug of ours, and answering it with "check the folder's permissions" is the same cry-wolf as
#:   answering a read-only disk with "wait for the other operation to finish".
#:
#: ⚠ **One predicate cannot serve both**, which a first cut here tried to do -- it reworded every
#: non-busy failure, including a missing table, into advice about folder permissions. `(afe)`
_UNWRITABLE_CODES = frozenset(
    {
        sqlite3.SQLITE_PERM,
        sqlite3.SQLITE_READONLY,
        sqlite3.SQLITE_IOERR,
        sqlite3.SQLITE_FULL,
        sqlite3.SQLITE_CANTOPEN,
    }
)


class CatalogUnwritableError(Exception):
    """The catalog's own location could not be prepared, before SQLite was ever asked.

    ⚠ **Not every way a catalog fails to be writable is a `sqlite3.Error`.** `Catalog.__init__`
    creates the catalog's parent directory before it connects, and on a read-only or full disk
    that ``mkdir`` raises ``PermissionError``/``OSError`` -- which the surfaces' SQLite handlers
    never see, so it reached the terminal as a stack. This is that condition wearing the shape the
    handlers already recognise. `(aen)`

    **A plain ``Exception``, deliberately not an ``OSError``**, even though an ``OSError`` caused
    it: the codebase has many ``except OSError`` blocks around filesystem work, and a catalog that
    cannot be created is not something any of them should quietly absorb.
    """

    def __init__(self, cause: OSError, directory: Path) -> None:
        super().__init__(f"cannot prepare the catalog directory {directory}: {cause}")
        self.cause = cause
        self.directory = directory
        #: Mirrored so `catalog_unwritable_message` reads one attribute whatever it was handed.
        self.errno = cause.errno


def is_catalog_unwritable(exc: BaseException) -> bool:
    """Whether ``exc`` is the catalog being unreachable or unstorable, rather than a bug.

    ⚠ **``SQLITE_CORRUPT`` and ``SQLITE_NOTADB`` are deliberately absent.** A damaged catalog is
    a different situation with different advice, and `catalog_startup` already owns it.
    """
    if isinstance(exc, CatalogUnwritableError):
        return True
    return isinstance(exc, sqlite3.Error) and primary_code(exc) in _UNWRITABLE_CODES


#: Travels the same way `CATALOG_BUSY_CODE` does, and is deliberately a different value: busy
#: means *try again in a minute*, this means *something is wrong with the catalog's folder*.
CATALOG_UNWRITABLE_CODE = "CatalogUnwritable"


def _errno_name(exc: BaseException) -> str | None:
    """``errno.EACCES`` -> ``"EACCES"``, for a failure that never reached SQLite at all."""
    number = getattr(exc, "errno", None)
    return errno.errorcode.get(number) if isinstance(number, int) else None


def catalog_unwritable_message(exc: BaseException) -> str:
    """What to say when a catalog write failed for a reason that will not clear. §9.

    **The backstop wording, deliberately not the detailed one.** `organizer` builds a fuller
    account for a write that fails mid-run, because there it knows what landed, what was
    recorded and which directory to name. This is for the same failure met anywhere else -- the
    end-of-run stamp, a settings write, a command that is not `organize` -- where none of that is
    in scope. Both say the same thing about the same condition; only the detail differs.

    ⚠ **Never ``str(exc)``.** SQLite's own prose ("disk I/O error") describes its internals and
    names no action, which is exactly what §9 exists to keep off the screen. The symbolic code is
    appended instead: it is stable vocabulary, and it is what makes a bug report actionable.

    ⚠ **Every clause must be true of a command that wrote NOTHING**, and a first version of this
    was not: it said the command "stopped rather than continue without recording what it did" and
    sent the reader to ``rescan``, which on a read-only ``status`` describes work that never
    happened. This function is the *backstop* -- it is reached from any command, and it cannot
    know whether anything was written -- so it may not assert that anything was. `rescan` is
    offered against a condition the reader can check ("if a run was interrupted") rather than
    asserted as a consequence. `(aen)`
    """
    name = getattr(exc, "sqlite_errorname", None) or _errno_name(exc)
    diagnostic = f" Diagnostic: {name}." if name else ""
    return (
        "Truestill could not write to the library catalog, so this command stopped. Check that "
        "the folder holding your catalog exists and can be written to - the catalog also creates "
        "temporary files beside itself, so making the catalog file writable is not enough on its "
        "own - and that the drive it is on is not full or disconnected. If a run was interrupted "
        "partway, 'truestill rescan' lists anything on your drives that the catalog does not "
        f"know about.{diagnostic}"
    )


def is_catalog_busy(exc: BaseException) -> bool:
    """Whether ``exc`` is the catalog being held by someone else, rather than a fault.

    Absent code means "not known to be busy", which is the safe answer: an unrecognised failure
    keeps its traceback rather than being dressed up as retryable.
    """
    return isinstance(exc, sqlite3.Error) and primary_code(exc) in _BUSY_CODES


def is_catalog_write_permanent(exc: BaseException) -> bool:
    """Whether a failed catalog write will still fail if we try again inside this run.

    **The complement of :func:`is_catalog_busy`, deliberately expressed as "everything else".**
    Enumerating the permanent codes instead would mean a code nobody listed -- a new SQLite
    release, an extended variant we have not seen -- silently landing on the *retryable* side,
    where the product would wait out a fault that never clears. Unknown must mean permanent.

    ⚠ **``SQLITE_IOERR`` (10) is UNRESOLVED and lands here, on the permanent side.** The evidence
    does not settle it: ``IOERR`` covers a failing disk, which is permanent, *and* a flaky USB or
    network-filesystem blip, which is not, and nothing available at this call site tells them
    apart. The tie is broken by **cost, not evidence** -- calling a blip permanent costs the user
    a run they restart, while calling a dying disk transient keeps writing to failing media.

    ⚠ **And it is not a corner.** Measured 2026-08-22: a catalog whose *directory* is denied
    mid-run fails with ``SQLITE_IOERR_DELETE`` at least as often as with
    ``SQLITE_READONLY_DIRECTORY``, because SQLite reuses a ``-journal`` it already created --
    opening an existing file needs permission on the *file* -- and only removing it needs the
    directory. So the ambiguous code is the **common** presentation of the failure this whole
    module was extended to handle. Had the tie gone the other way, the ordinary case would retry
    ten times and stop anyway. If a transient ``IOERR`` is ever observed in the wild, this is the
    paragraph to revisit; it is a judgement, not a settled classification, and the frequency
    finding is a reason to look again rather than a reason to consider it closed. `(afe)`
    """
    return isinstance(exc, sqlite3.Error) and not is_catalog_busy(exc)


#: Ten attempts, backoff capped at one second. Taken from Haskell Language Server, which retries
#: ``SQLITE_BUSY`` with random exponential backoff on exactly these two bounds -- the closest
#: prior art in a comparable position: a long-lived process sharing one SQLite file with another
#: instance of itself.
#:
#: ⚠ **Each attempt already blocks for up to ``busy_timeout`` (5 s) inside SQLite before it
#: raises**, so ten attempts bound the wait at roughly a minute, not at ten seconds. Deliberate:
#: the alternative is stopping a run because another Truestill window was mid-write, and a minute
#: of waiting is cheaper for the user than a stopped run plus an unrecorded copy.
_BUSY_ATTEMPTS = 10
_BUSY_BACKOFF_CAP_SECONDS = 1.0


def _busy_backoff(attempt: int, jitter: Callable[[], float]) -> float:
    """Full-jitter exponential backoff for ``attempt`` (1-based), capped.

    Full jitter rather than plain exponential because the contending writer is usually *another
    copy of this program* doing the same thing: two runs that back off by the same schedule
    re-collide on the same schedule.
    """
    ceiling = min(_BUSY_BACKOFF_CAP_SECONDS, 0.01 * 2.0 ** (attempt - 1))
    return ceiling * jitter()


def retry_while_busy[T](
    operation: Callable[[], T],
    *,
    attempts: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
) -> T:
    """Run ``operation``, retrying only while the catalog is busy. Never retries a fault.

    ⚠ **A transient failure we give up on is a permanent one, and for a catalog write that
    means an unrecorded file.** This is the function that makes "busy is transient, per file"
    true rather than aspirational: without it, a caller that recorded busy as a per-file failure
    and carried on would copy every file for as long as the other process held the lock and
    record none of them -- manufacturing exactly the orphans the stop exists to bound. `(afe)`

    The last attempt is unguarded, so an exhausted busy reaches the caller as the exception it
    can then treat as permanent. ``sleep`` and ``jitter`` are injectable so a test can prove the retry
    happens without spending the wall-clock on it.
    """
    # Read at call time, not bound as a default, so the bound is one number in one place and a
    # test can lower it without standing up a fake retry.
    limit = _BUSY_ATTEMPTS if attempts is None else attempts
    for attempt in range(1, limit):
        try:
            return operation()
        except sqlite3.Error as exc:
            if not is_catalog_busy(exc):
                raise
            sleep(_busy_backoff(attempt, jitter))
    # The last attempt is this call rather than a branch inside the loop, so there is no
    # unreachable arm to reason about and ``attempts=1`` means exactly one try.
    return operation()
