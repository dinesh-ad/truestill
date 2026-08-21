"""What the filesystem was willing to say about a path: there, not there, or refused.

**Absent and refused are different answers**, and five sites in this product needed the
distinction while asking for it five different ways. `(aey)`

**The defect that collected them here.** `Path.is_dir()`, `exists()` and `is_file()` look total
and are not. Through Python 3.13 they re-raised ``EACCES``; in 3.14 they return ``False`` instead
([cpython#144525](https://github.com/python/cpython/issues/144525)) - `is_dir()` is now literally
``return os.path.isdir(self)``. So a folder that refused became one that was *not there*, which on
this product's surfaces means **creatable**: the app offers to create a directory that already
exists and whose creation will fail exactly as the probe did.

⚠ **3.14 did not invent this; it removed pathlib's exception to it.** `os.path` has swallowed
every ``OSError`` for as long as it has existed. **pathlib was the outlier this code relied on**,
which is why the fix is a primitive of our own rather than a version check: :func:`reach` answers
identically on both interpreters, so nothing here is waiting for an upgrade.

## The classification is CPython 3.13's, copied deliberately

:data:`_ABSENT_ERRNOS` and :data:`_ABSENT_WINERRORS` are ``pathlib._abc._IGNORED_ERRNOS`` and
``_IGNORED_WINERRORS`` from 3.13 - the set 3.14 deleted. **Copying it is what makes this a forward
fix rather than a behaviour change on the version we ship.** Measured, each of the three is a real
trap and not a formality:

* ``ELOOP`` - a symlink loop. ``stat()`` raises it, and `probe_dir` answers ``MISSING`` today. A
  primitive that read *any* ``OSError`` as refusal would flip that to ``UNREADABLE`` on 3.13.
* ``ValueError`` - a path containing a NUL byte. ``stat()`` raises it on **both** versions while
  the predicates return ``False``; not catching it would turn an answer into an exception.
* ``ERROR_NOT_READY`` (21) - a Windows drive that exists with no media. pathlib 3.13 calls that
  *not there*, so this does too. ⚠ **Arguably wrong** - "creatable" is a poor thing to tell
  someone about an empty optical drive - but changing it is a 3.13 behaviour change and belongs
  to its own decision, not to a defect fix. It is also the one branch **no lane but Windows can
  execute**.

## Complexity

**One ``stat`` call, always.** The renderer it replaced spent one for a directory and *two* for
everything else - `is_dir()` then `exists()` - so this is cheaper than what it supersedes, not
merely equal to it. Walks that repeat it stay O(depth), one stat per level.

## Who deliberately does NOT use this

`reclaim.py` asks *"is this a readable regular file?"* and treats every failure as **no**, because
it is the only path in the product that deletes a user's files: a file it cannot examine must
never become a delete candidate, so *not there* and *I could not look* have to land on the same
conservative side. It must not acquire a distinction it would then have to discard. That is stated
at `reclaim._readable_file` and pinned by
`test_reclaim_never_deletes_what_it_cannot_examine.py`.
"""

from __future__ import annotations

import os
import stat
from enum import StrEnum
from errno import EBADF, ELOOP, ENOENT, ENOTDIR
from pathlib import Path

#: ``pathlib._abc._IGNORED_ERRNOS`` as of CPython 3.13. ``EBADF`` is upstream's guard against
#: macOS ``stat`` throwing it; kept for that reason rather than because we have seen it.
_ABSENT_ERRNOS = frozenset({ENOENT, ENOTDIR, EBADF, ELOOP})

#: ``pathlib._abc._IGNORED_WINERRORS`` as of CPython 3.13: drive-not-ready, invalid name
#: (bpo-35306), and a symlink that resolves to itself.
_ABSENT_WINERRORS = frozenset({21, 123, 1921})


class Reach(StrEnum):
    """What one ``stat`` established about a path.

    Five members rather than a boolean because each is **a different next action** for the caller:
    a directory can be walked, a file cannot, a missing path can be created, and a refused one can
    be neither created nor described - only reported.
    """

    #: An existing directory.
    DIRECTORY = "directory"
    #: An existing regular file.
    FILE = "file"
    #: Something is there and is neither - a socket, a device node, a fifo.
    OTHER = "other"
    #: Nothing is there. Creatable.
    MISSING = "missing"
    #: Something is there and the OS refused to describe it. Not creatable, not absent.
    REFUSED = "refused"


def _is_absent(exc: OSError) -> bool:
    """Whether this failure means *not there* rather than *refused*.

    Mirrors ``pathlib._abc._ignore_error`` from 3.13, including the ``winerror`` arm - which is
    the only reason a Windows drive with no media keeps answering the way it does today.
    """
    return exc.errno in _ABSENT_ERRNOS or getattr(exc, "winerror", None) in _ABSENT_WINERRORS


def probe(path: Path) -> tuple[Reach, os.stat_result | None]:
    """Classify ``path`` from a single ``stat``, and hand back the ``stat`` itself. Never raises.

    ⚠ **The second element exists so a caller that needs a field from the stat does not take a
    second one.** `nearest_device` wants ``st_dev``; without this it called `reach` and then
    `path.stat()` again - two syscalls per level of a walk, on a function whose docstring promises
    one. Found by a surviving mutation: with the refusal branch removed the answer was *identical*,
    because the second stat failed the same way the first had. An equivalent mutant is a fair
    signal that a branch is carrying no weight, and the honest fix was to stop taking the stat
    twice rather than to write a test that could not tell the difference.

    ``None`` exactly when the stat did not succeed, so a caller reading a field must handle the
    refused and missing cases rather than discovering them through an ``AttributeError``.

    ⚠ **``Path.stat`` rather than ``os.stat``**, and not by accident: it raises on every supported
    version where the boolean predicates no longer do, *and* it is what
    `test_unreadable_paths._deny` patches - the fixture that carries this area's only Windows
    coverage. Switching to ``os.stat`` would silently un-cover a platform.
    """
    try:
        result = path.stat()
    except ValueError:
        # A path the OS cannot even be asked about - a NUL byte. pathlib's predicates answer
        # False for this, so *not there* keeps the answer this function replaced.
        return Reach.MISSING, None
    except OSError as exc:
        return (Reach.MISSING if _is_absent(exc) else Reach.REFUSED), None
    if stat.S_ISDIR(result.st_mode):
        return Reach.DIRECTORY, result
    return (Reach.FILE if stat.S_ISREG(result.st_mode) else Reach.OTHER), result


def reach(path: Path) -> Reach:
    """Classify ``path`` from a single ``stat``. Never raises. **O(1).**

    The façade four of the five call sites want: they need the verdict and nothing else.
    """
    return probe(path)[0]
