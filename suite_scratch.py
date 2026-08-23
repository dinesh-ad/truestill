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

#: Named for what it is, so a stray directory found later says which tool put it there.
PREFERRED_SCRATCH = Path("/data/tmp/truestill")


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
    """
    requested = os.environ.get(TEST_TMPDIR_ENV)
    root = Path(requested) if requested else PREFERRED_SCRATCH
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        if requested:
            raise
        return None
    return root
