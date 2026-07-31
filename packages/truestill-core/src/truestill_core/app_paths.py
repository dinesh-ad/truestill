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

import os
from pathlib import Path

import platformdirs

#: Application name for the platform directory lookup, and the **product** name as a person
#: sees it: **Truestill**, capitalised. The import package stays ``truestill_core`` and the
#: command stays ``truestill`` - those are identifiers, and lowercase is right for both - but a
#: folder in "Application Support" or "AppData" sits among the other installed applications,
#: and a lowercase name there reads like a stray build artefact rather than a product.
#:
#: One name for both roots, so a user finds everything Truestill owns without knowing which
#: kind of file it is.
APP_NAME = "Truestill"

#: Environment overrides for the two roots, honoured on **every** platform.
#:
#: They exist for two reasons and both are load-bearing. A portable install - truestill on a USB
#: stick, or a second isolated library - needs to put its data somewhere the OS convention does
#: not know about; this is the same escape hatch Terraform's ``TF_DATA_DIR`` provides.
#:
#: And **the test suite depends on them for hermeticity**. Without an override the default
#: catalog resolves into the developer's real home, so any test running a default-`--db` command
#: writes there - which is exactly what happened when `(aae)` first landed: CI runs and a local
#: run each created a real ``catalog.sqlite`` in the runner's home. `platformdirs` honours
#: ``XDG_DATA_HOME`` on Linux only, so a portable override has to be ours.
DATA_DIR_ENV = "TRUESTILL_DATA_DIR"
CACHE_DIR_ENV = "TRUESTILL_CACHE_DIR"

#: Where the catalog lived before `(aae)`, relative to the working directory. Still honoured
#: when it is really there - see :func:`default_catalog_path`.
LEGACY_CATALOG_PATH = Path("reports/catalog.sqlite")

#: Filename of the catalog in the OS data directory.
CATALOG_FILENAME = "catalog.sqlite"

#: Filename of the shared hash/metadata cache in the OS cache directory.
CACHE_FILENAME = "hashes.cache.sqlite"


def _data_dir() -> Path:
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override) if override else Path(platformdirs.user_data_dir(APP_NAME))


def _cache_dir() -> Path:
    override = os.environ.get(CACHE_DIR_ENV)
    return Path(override) if override else Path(platformdirs.user_cache_dir(APP_NAME))


def default_catalog_path() -> Path:
    """The catalog to use when the caller did not name one. **Never creates anything.**

    Resolved on **every call**, never cached in a module constant: an override set after import
    must still be honoured, and a constant computed at import time is unpatchable by a test and
    therefore un-isolatable.

    An existing legacy catalog wins, and that ordering is the backwards-compatibility promise:
    an upgrade must not silently start writing to a different, empty catalog while the real one
    sits where the user left it. That failure would look exactly like data loss, which is why
    the legacy path is checked first rather than migrated automatically.
    """
    if LEGACY_CATALOG_PATH.exists():
        return LEGACY_CATALOG_PATH
    return _data_dir() / CATALOG_FILENAME


def standard_catalog_path() -> Path:
    """Where the catalog **belongs** - unlike :func:`default_catalog_path`, which says where it
    currently *is* and prefers a legacy file that exists.

    The pair differ only while someone is still on the old layout, which is precisely when the
    difference matters: it is what the ``catalog`` command compares to decide whether to offer a
    move, and it is the destination that move copies to.

    This exists because it was missing. ``app_paths`` owned "where does the catalog go" but had
    no name for "where does it belong", so the one caller that needed it rebuilt the rule from
    ``platformdirs`` directly and lost the ``TRUESTILL_DATA_DIR`` override in the process - which
    made the ``catalog`` command advertise a path the install never uses, and made ``--move``
    copy to one. A rule with no home gets reimplemented, and the copy is where it goes wrong.
    """
    return _data_dir() / CATALOG_FILENAME


def default_cache_path() -> Path:
    """The cache for the default catalog: the OS **cache** directory, never the data one."""
    return _cache_dir() / CACHE_FILENAME


def cache_path_for(catalog: Path) -> Path:
    """The cache belonging to ``catalog`` - its cache counterpart, wherever that is.

    For the OS-conventional catalog the counterpart is the OS cache directory. For any other
    path - an explicit ``--db``, a test fixture, a catalog on an external drive - there is no
    counterpart, so the cache sits beside it and travels with it.
    """
    if catalog == _data_dir() / CATALOG_FILENAME:
        return default_cache_path()
    return catalog.with_suffix(".cache.sqlite")
