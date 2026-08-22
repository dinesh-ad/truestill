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
  ``~/Library/Application Support`` and ``~/Library/Caches``, and ``%LOCALAPPDATA%`` for
  both on Windows - each with edge cases we would rediscover as bug reports on machines we do
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
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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

#: Where the catalog lived before `(aae)`, relative to the working directory.
#:
#: ⚠ **NOT A RESOLUTION RULE ANY MORE - `truestill catalog --move` is its only consumer.**
#: `(adw)` retired the automatic lookup on 2026-08-19: because this path is *relative*, asking
#: whether it exists asked about the **current directory**, so the same install found a different
#: library depending on where it was launched from, with no environment variable involved.
#:
#: **Retired rather than anchored, and the reasoning has a shelf life.** It was introduced
#: 2026-07-31 (`5db91b9`), no release has ever been published (`release.yml` fires on `tags:
#: ["v*"]`, no such tag exists, and its runs were dispatches with `dry_run` defaulting to true),
#: so the only way to hold one is to have run truestill from a checkout before that date -
#: **a population of one, and it is the maintainer, whose catalog was migrated before this
#: landed.** Anchoring the path would have been machinery for nobody.
#:
#: Kept relative on purpose: `--move` means *"migrate the one in front of me"*, which is exactly
#: the question a relative path answers well - and exactly the one it answers badly when the
#: question is *"which library is this?"*.
LEGACY_CATALOG_PATH = Path("reports/catalog.sqlite")

#: Filename of the catalog in the OS data directory.
CATALOG_FILENAME = "catalog.sqlite"

#: Filename of the shared hash/metadata cache in the OS cache directory.
CACHE_FILENAME = "hashes.cache.sqlite"

#: Filename of the running app's session URL. ``.txt`` on purpose: the one person who ever opens
#: it is doing so because something went wrong, and it must open in whatever they double-click.
SESSION_URL_FILENAME = "session-url.txt"

#: Where per-drive lock files live, under the data dir. `(aaw)`
#:
#: ⚠ **A subdirectory, not loose files beside the catalog.** These are runtime scratch that the OS
#: reclaims by itself, and mixing them in with `catalog.sqlite` and `last-run.json` - which a user
#: is told to look at, copy and keep - invites deleting the wrong one.
LOCKS_DIRNAME = "locks"

#: Filename of the record a run writes about what it did. ``.json`` because it is read by a person
#: looking for one filename among thousands, and by whatever they paste it into.
#:
#: **Rolling: one file, overwritten each run.** One file has no expiry policy; a file per run has
#: to answer "who decides when these go", which is the commitment that ruled out putting this in
#: the catalog. `(afl)`
RUN_RECORD_FILENAME = "last-run.json"


#: ``appauthor=False``, and it is load-bearing on ONE platform. `platformdirs` defaults the
#: author segment to the **app name** when it is ``None``, so Windows produced
#: ``%LOCALAPPDATA%\\Truestill\\Truestill\\catalog.sqlite`` - the name twice. Linux and macOS
#: ignore the author segment entirely, so this moves **nothing** there; it is a Windows-only
#: correction. Made 2026-08-13, before the first Windows installer shipped: with no user holding a
#: catalog at the old path there is nothing to migrate, and the same fix afterwards would mean
#: finding, moving and verifying the one file `(aae)` calls unrecoverable.
#:
#: **Windows data is LOCAL, not roaming** (`roaming=False` is the default): a photo catalog has no
#: business syncing to a domain profile. The docstring above said ``%APPDATA%`` and was wrong.


def _override_dir(name: str) -> Path | None:
    """The directory ``name`` asks for, or ``None`` when it is unset **or blank**. `(adv)`.

    **Blank is unset, and that is `platformdirs`' own rule rather than ours.** It reads its
    overrides as ``os.environ.get("XDG_CONFIG_HOME", "").strip() or <default>`` - verified here
    rather than cited: with ``XDG_DATA_HOME`` set to ``""`` and to ``"   "`` it returns
    ``~/.local/share`` both times. An unset variable and an empty one must not mean different
    things, and without this ``TRUESTILL_DATA_DIR=`` resolves a catalog into a directory named by
    whitespace - measured, ``"   /catalog.sqlite"``.
    """
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else None


def _data_dir() -> Path:
    override = _override_dir(DATA_DIR_ENV)
    return override if override else Path(platformdirs.user_data_dir(APP_NAME, appauthor=False))


def _cache_dir() -> Path:
    override = _override_dir(CACHE_DIR_ENV)
    return override if override else Path(platformdirs.user_cache_dir(APP_NAME, appauthor=False))


def is_same_file(one: Path, other: Path) -> bool:
    """Whether two paths name the **same file**, not the same string. `(aeb)`.

    **The question actually being asked** whenever code compares one catalog path against another.
    A symlink anywhere in a data directory produces two spellings of one file - measured on the
    maintainer's machine, where `/home/dinesh/TruestillLibrary` links to `/data/TruestillLibrary`
    and `truestill catalog` duly reported a correctly-placed catalog as being *"in the old
    location"*, advising a `--move` that could not help.

    **`samefile` rather than resolving both sides.** Resolving would work today and break the
    first time a path cannot be resolved - a stale mount raises `ENOTCONN`, and `drive.py`'s
    containment check already records that a path which cannot be resolved must still get an
    answer. This compares device and inode, which is the property the question is about.

    **False rather than raising** when either path is missing or unreadable: `samefile` stats
    both, and *"one of them is not there"* is a perfectly good **no** rather than an error every
    caller has to handle.
    """
    try:
        return one.samefile(other)
    except OSError:
        return False


def default_catalog_path() -> Path:
    """The catalog to use when the caller did not name one. **Never creates anything.**

    Resolved on **every call**, never cached in a module constant: an override set after import
    must still be honoured, and a constant computed at import time is unpatchable by a test and
    therefore un-isolatable.

    ⚠ **The legacy `reports/catalog.sqlite` is no longer consulted** (`(adw)`, 2026-08-19).
    ~~An existing legacy catalog wins, and that ordering is the backwards-compatibility
    promise.~~ It did, as `(aae)`'s promise that an upgrade must not silently start writing to a
    different, empty catalog while the real one sits where the user left it - which was right.
    What was wrong is that the path is **relative**, so the promise was kept against *whichever
    directory the process happened to start in*, and the same install answered differently after
    a `cd`. `truestill catalog --move` migrates one; nothing adopts one.
    """
    return resolve_catalog_choice().path


CatalogChoiceReason = Literal["override", "legacy", "default"]


@dataclass(frozen=True, slots=True)
class CatalogChoice:
    """Which catalog path won, and why - so a surface can say so instead of only showing it."""

    path: Path
    reason: CatalogChoiceReason
    #: Always set. One sentence naming the winner's provenance.
    summary: str
    #: Set only when something surprising has to be disclosed - a second real catalog that was
    #: found and not used, or an override that was set and lost. Empty otherwise.
    note: str


def resolve_catalog_choice() -> CatalogChoice:
    """Where the catalog is, which of three rules decided it, and what the user should be told.

    **The precedence, and it was the other way round until `(adv)`.** An explicit
    ``TRUESTILL_DATA_DIR`` outranks the legacy path, because the legacy check is a *guess made
    from the working directory* and the variable is a *stated instruction*. `platformdirs`, XDG
    and Terraform's ``TF_DATA_DIR`` all consult the override first; nothing consults a
    compatibility fallback first. The old order meant a user who set the variable could organize
    and register drives against a catalog they never named.

    ⚠ **But the override does NOT get to strand an existing library, and that half is not
    negotiable.** "The fallback applies only when no override is set" would hand someone with a
    real `reports/catalog.sqlite` and the variable set in a shell profile a brand-new empty
    catalog and no sign of the old one - which is the data-loss shape `(aae)` exists to prevent,
    reintroduced by the fix for `(adv)`. So the legacy file is still used when **it exists and the
    override holds no catalog yet**.

    **Whenever the two disagree, the answer is disclosed rather than picked silently** - the
    banner was identical in all three cases, which is what made `(adv)` hard to notice: the
    resolved path was already on screen and nothing said a variable had been set and lost.
    """
    override_dir = _override_dir(DATA_DIR_ENV)
    if override_dir is not None:
        return CatalogChoice(
            path=(override_dir / CATALOG_FILENAME).resolve(),
            reason="override",
            summary=f"Catalog location from {DATA_DIR_ENV}.",
            note="",
        )

    return CatalogChoice(
        path=_data_dir() / CATALOG_FILENAME,
        reason="default",
        summary="Catalog location from the standard data directory.",
        note="",
    )


def lock_path_for(name: str) -> Path:
    """A lock file in the data dir, never on the drive. `(aaw)`

    **On this machine on purpose.** Advisory locking is least reliable on the FUSE and network
    mounts a library sits on; a stale file on the user's own drive is the thing they delete by
    hand; and the marker is stable identity rather than a high-churn runtime file. The cost is
    stated rather than hidden: two machines sharing one mount do not see each other's locks.
    """
    return _data_dir() / LOCKS_DIRNAME / f"{name}.lock"


def session_url_path() -> Path:
    """Where the running app leaves the URL a user needs to reach it.

    In the **data** directory rather than the cache: a cache may be cleared at any moment by the
    OS, and this file is the only way back into a running app whose browser did not open. It is
    short-lived but not disposable, which is a different thing.

    Not the OS *runtime* directory either, though that is the semantically closest fit
    (``XDG_RUNTIME_DIR`` exists for exactly this and is cleared on logout). It resolves
    inconsistently across the three platforms, and a file whose whole job is to be found by a
    confused user - or by whoever is helping them - must be in one predictable place per
    platform, not three differently-shaped ones.
    """
    return _data_dir() / SESSION_URL_FILENAME


def default_cache_path() -> Path:
    """The cache for the default catalog: the OS **cache** directory, never the data one."""
    return _cache_dir() / CACHE_FILENAME


def record_path_for(catalog: Path) -> Path:
    """Where the run record belonging to ``catalog`` goes: **beside it, always.**

    ⚠ **The sibling half of `cache_path_for`'s rule without the split, and the difference is the
    point.** A cache is redirected to the OS *cache* directory for the conventional catalog,
    because that is what a cache is for and losing one costs nothing. A record is **data**: it is
    the only place a finished run says what it did, so it belongs with the catalog wherever the
    catalog is, and travels with it. `(afl)`
    """
    return catalog.parent / RUN_RECORD_FILENAME


def cache_path_for(catalog: Path) -> Path:
    """The cache belonging to ``catalog`` - its cache counterpart, wherever that is.

    For the OS-conventional catalog the counterpart is the OS cache directory. For any other
    path - an explicit ``--db``, a test fixture, a catalog on an external drive - there is no
    counterpart, so the cache sits beside it and travels with it.
    """
    if catalog == _data_dir() / CATALOG_FILENAME:
        return default_cache_path()
    return catalog.with_suffix(".cache.sqlite")
