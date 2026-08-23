"""Where the test suite's temporary files live, and how it decides.

A **uniquely-named sibling** of the root ``conftest.py`` rather than part of it, because
``test_shared_test_helpers.py`` binds the split: fixtures live in a conftest and nobody imports
it; anything a test needs to *import* gets a name no other file in the repo claims. The hook
that applies this lives in the root ``conftest.py``; the decision lives here so the guard can
exercise it directly.

``/tmp`` on the maintainer's machine is **tmpfs** - RAM. Everything the suite writes lands there:
every ``tmp_path``, the per-test data root, every catalog and rollback journal, exiftool's
argfiles, each browser's profile, and pytest-playwright's session video and trace directory (a
plain ``TemporaryDirectory``, which every video and trace is recorded into before the retained
ones are moved to ``--output``). Measured 2026-08-23 from an empty ``/tmp``: ``make test`` writes
**282 MB**, the browser lane peaks at **716 MB**, and ~850 MB stays resident between runs -
against a 15.1 GiB tmpfs on a 30 GiB machine.

`ENGINEERING_STANDARD.md` §4 carries both halves of the argument and this serves both: the
thirty-second member's corollary is the rule it applies - *a RAM-backed scratch directory turns a
download into memory pressure* - and the forty-sixth is the other direction, that a timing test
on tmpfs cannot observe an interruption.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Set to override the volume. An override is for a machine shaped differently, never something
#: anybody has to remember to set: the default below is what an ordinary run uses.
TEST_TMPDIR_ENV = "TRUESTILL_TEST_TMPDIR"

#: The volume the default lives on. Named separately because **its existence is the test** and
#: it is never created: creating a directory is not evidence that the volume behind it is there.
SCRATCH_VOLUME = Path("/data")

#: Named for what it is, so a stray directory found later says which tool put it there.
PREFERRED_SCRATCH = SCRATCH_VOLUME / "tmp" / "truestill"


def scratch_root() -> Path | None:
    """The directory the suite's temporary files live under, or ``None`` for the OS default.

    ``None`` is the CI answer and is not a failure: no runner has a ``/data``, and an absolute
    path that could not be declined would fail all three ``check`` lanes. It is named in the
    pytest header either way, so *"the redirect did nothing"* is never silent - which is what
    §4's twenty-seventh member asks for where a rule cannot be made impossible to break.

    An **explicitly requested** root that cannot be created raises rather than falling back: the
    caller named a location, and quietly writing somewhere else is the failure this repo keeps
    filing entries about. An **absent default** is a different question with a different answer,
    which is why the two are not one branch.

    ⚠ **THE DEFAULT IS DECLINED OFF POSIX BY CONSTRUCTION, NOT BY THE DIRECTORY BEING ABSENT**
    (fixed 2026-08-23, `(agb)`; the Windows lane caught the first version). ``/data/tmp/truestill``
    is **drive-relative on Windows**, so ``mkdir(parents=True)`` cheerfully creates it
    under whatever drive happens to be current - the redirect fires on a platform it was never
    meant for, and on CI it overrode the runner's deliberate ``TEMP`` on the fast drive. **"The directory could not be created" was a machine state standing in for
    an intent**, and it was false on the one platform nobody could check locally. The intent is:
    *this default names one POSIX volume on one machine*. So both halves are asserted - the
    platform, and that the volume is **already there**. It is never created; only the directory
    under it is.
    """
    requested = os.environ.get(TEST_TMPDIR_ENV)
    if requested:
        root = Path(requested)
        root.mkdir(parents=True, exist_ok=True)  # raises: the caller named this location
        return root.resolve()
    if os.name != "posix" or not SCRATCH_VOLUME.is_dir():
        return None
    PREFERRED_SCRATCH.mkdir(parents=True, exist_ok=True)
    # resolve() so the value compares equal to what pytest and a subprocess report back; an
    # unanchored path never does, which is the second half of the same Windows failure.
    return PREFERRED_SCRATCH.resolve()
