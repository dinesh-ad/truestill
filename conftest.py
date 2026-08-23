"""Where the suite writes: the scratch volume, and per-test isolation of the data/cache dirs.

Two concerns, one file, because they are the same concern at two radii - *the suite must not
write where it does not belong*. The ``pytest_configure`` hook keeps it off **RAM**; the fixture
below keeps it out of the developer's **home**. The scratch decision itself lives in
``suite_scratch.py``, which is importable where a conftest is not.

--- the data and cache directories ---

Without the fixture, `app_paths.default_catalog_path` resolves into the **developer's real home**, so
any test that runs a default-``--db`` command writes a catalog there. That is not hypothetical:
when `(aae)` first landed, both CI runners and a local run each created a real
``catalog.sqlite`` under the user's data directory before anyone noticed.

**Per test, not per session - and that is the whole point.** A session-wide root kept tests out
of the developer's home but let them into *each other's*. ``truestill status`` opens
``Catalog(args.db)``, which **creates** the file; a later test asserting the default catalog does
not exist then found one. The suite stayed green only because ``testpaths`` happens to collect
core before cli and app, so the assertion ran before the creation. Plain ``pytest packages/``
collects alphabetically - app, cli, core - and was red at HEAD.

That is green **by arrangement, not by isolation**, and it is the third arrival of this failure
(see `ENGINEERING_STANDARD.md`, the isolation rule). So the remedy is the one that rule asks
for: make it impossible rather than ordered. Each test gets a root **no other test can name**,
so a test that creates a catalog cannot reach a root another test asserts is empty - whatever
order they run in.

The roots live under pytest's own temporary base rather than inside the requesting test's
``tmp_path``: several tests assert their ``tmp_path`` is empty, and hiding an application data
directory inside it would trade this bug for a subtler one.

**Cost:** one ``mkdir`` per test - measured at well under a millisecond, against a suite that
takes a minute.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from truestill_core.app_paths import CACHE_DIR_ENV, DATA_DIR_ENV

from suite_scratch import PREFERRED_SCRATCH, scratch_root

#: Resolved once, at import, so the header and the hook cannot disagree about where it went.
_SCRATCH = scratch_root()


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001 - pytest hook signature
    """Point this process *and everything it spawns* at the scratch root.

    Both assignments are needed. ``tempfile.tempdir`` is a module global that ``gettempdir``
    caches on first call, so a plugin that asked before us would pin the old answer; ``TMPDIR``
    is what a subprocess reads, and the browsers, ``exiftool`` and ``uv`` are subprocesses.
    ``TEMP``/``TMP`` are the Windows spellings.

    Ordering is safe rather than lucky: ``TempPathFactory.from_config`` only *stores* the option
    at configure time, and ``getbasetemp`` reads ``tempfile.gettempdir()`` lazily at the first
    ``tmp_path`` asked for.
    """
    if _SCRATCH is None:
        return
    os.environ["TMPDIR"] = os.environ["TEMP"] = os.environ["TMP"] = str(_SCRATCH)
    tempfile.tempdir = str(_SCRATCH)


def pytest_report_header() -> str:
    """One line, every run, naming where the scratch actually went."""
    if _SCRATCH is None:
        return f"scratch: platform default ({tempfile.gettempdir()}) - no {PREFERRED_SCRATCH}"
    return f"scratch: {_SCRATCH}"


@pytest.fixture(autouse=True)
def _isolate_app_dirs(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # resolve() matters on Windows: GitHub's runners hand out TEMP in 8.3 short form
    # (C:\Users\RUNNER~1\...), and anything that resolves the path for display gets the long
    # form (C:\Users\runneradmin\...), so the two never compare equal. Known pytest issue
    # #11895. resolve() expands the short name, so the roots are canonical from the start.
    root = Path(tmp_path_factory.mktemp("truestill-home")).resolve()
    # monkeypatch rather than os.environ directly: restoration is then pytest's job, and a test
    # that sets its own override on top of this one is unwound in the right order.
    monkeypatch.setenv(DATA_DIR_ENV, str(root / "data"))
    monkeypatch.setenv(CACHE_DIR_ENV, str(root / "cache"))
