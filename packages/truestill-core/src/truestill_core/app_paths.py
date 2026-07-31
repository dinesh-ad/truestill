"""Where truestill's own files live: the catalog, and the cache that is not the same thing.

**The defect this closes ((aae)).** The catalog default was ``Path("reports/catalog.sqlite")`` -
**relative to the working directory** - and the cache sat beside it. A double-clicked desktop
app has no meaningful working directory, so on the day an installer ships that path is not
untidy, it is *undefined*. And a disposable cache sharing a directory with the custody record
means anything true of one is true of the other: an OS that clears its cache location, or a
backup tool that skips it, hits both.

**Backwards-compatible by default.** A new install resolves to the platform's own locations. An
existing ``reports/catalog.sqlite`` **keeps being used exactly where it is** - upgrading changes
nothing, and moving it is an explicit act the user chooses. Nothing here writes, creates a
directory, or migrates: these functions answer *where*, and startup asks before it knows whether
the user intends to do anything at all.

**The cache lives in the cache counterpart of wherever the catalog lives.** One rule, two
consequences: the default catalog (in the data directory) gets the OS cache directory, which is
the whole point of `(aae)`; an explicit ``--db`` keeps its cache beside it, which keeps a
``--db`` invocation self-contained and, not incidentally, keeps the test suite hermetic - a
machine-wide cache would have every test that organizes or attaches write into the developer's
real cache directory.

Sharing a cache between catalogs **would** be safe - rows are keyed by absolute path, the values
are a pure function of the file and the requested tags, ``size``/``mtime_ns`` guard staleness,
and pruning only removes rows whose file is genuinely gone. That is worth knowing and is not what
decided this: the decision is about lifetime and isolation. The "moving a catalog takes its cache
along" argument is illusory anyway - `hash_cache` states that its keys are **machine-specific**,
so a carried cache is a hundred percent misses.

**Dependency justification, per `ENGINEERING_STANDARD.md` §4** (every runtime dep argued in
writing against a stdlib alternative). `platformdirs` is added deliberately:

* The stdlib has **no** equivalent. The alternative is hand-rolling three platform conventions -
  XDG (with its ``XDG_DATA_HOME`` / ``XDG_CACHE_HOME`` overrides and their defaults),
  ``~/Library/Application Support`` and ``~/Library/Caches``, and ``%APPDATA%`` /
  ``%LOCALAPPDATA`` - each with edge cases we would rediscover as bug reports on machines we do
  not have.
* It is **small and single-purpose**: pure Python, no dependencies of its own, and its entire
  API surface here is two function calls.
* It is the **de facto standard** for exactly this (Black, pip and pipx use it), so its edge
  cases have been found by people with more platforms than we have.
* Getting it wrong is not cosmetic: a wrong data directory is where someone's custody record
  goes missing.

**Complexity: O(1)** - string joins and at most one ``exists()`` probe. No I/O beyond that.
"""

from __future__ import annotations

from pathlib import Path

import platformdirs

#: Application name for the platform directory lookup. One name, used for both roots, so a
#: user can find everything truestill owns without knowing which kind of file it is.
APP_NAME = "truestill"

#: Where the catalog lived before `(aae)`, relative to the working directory. Still honoured
#: when it is really there - see :func:`default_catalog_path`.
LEGACY_CATALOG_PATH = Path("reports/catalog.sqlite")

#: Filename of the catalog in the OS data directory.
CATALOG_FILENAME = "catalog.sqlite"

#: Filename of the shared hash/metadata cache in the OS cache directory.
CACHE_FILENAME = "hashes.cache.sqlite"


def default_catalog_path() -> Path:
    """The catalog to use when the caller did not name one. **Never creates anything.**

    An existing legacy catalog wins, and that ordering is the backwards-compatibility promise:
    an upgrade must not silently start writing to a different, empty catalog while the real one
    sits where the user left it. That failure would look exactly like data loss, which is why
    the legacy path is checked first rather than migrated automatically.
    """
    if LEGACY_CATALOG_PATH.exists():
        return LEGACY_CATALOG_PATH
    return Path(platformdirs.user_data_dir(APP_NAME)) / CATALOG_FILENAME


def default_cache_path() -> Path:
    """The cache for the default catalog: the OS **cache** directory, never the data one."""
    return Path(platformdirs.user_cache_dir(APP_NAME)) / CACHE_FILENAME


def cache_path_for(catalog: Path) -> Path:
    """The cache belonging to ``catalog`` - its cache counterpart, wherever that is.

    For the OS-conventional catalog the counterpart is the OS cache directory. For any other
    path - an explicit ``--db``, a test fixture, a catalog on an external drive - there is no
    counterpart, so the cache sits beside it and travels with it.
    """
    if catalog == Path(platformdirs.user_data_dir(APP_NAME)) / CATALOG_FILENAME:
        return default_cache_path()
    return catalog.with_suffix(".cache.sqlite")
