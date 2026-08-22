"""Where the catalog and the cache live, and why they are not the same place ((aae)).

**The finding.** `DEFAULT_CATALOG_PATH` was ``Path("reports/catalog.sqlite")`` - CWD-relative -
and `HashCache.beside(db)` put the cache next to it. Two consequences, both bad and both
recorded in `(aae)`: a double-clicked app has no meaningful working directory, so the catalog
path is *undefined* the day an installer ships; and user data and a disposable cache share one
directory, so anything true of one (OS cache clearing, backup exclusion) is true of the other.

**Backwards-compatible by default.** A new install writes to the OS-conventional locations. An
existing ``reports/catalog.sqlite`` **keeps being used where it is** - nobody's setup changes on
upgrade, and moving it is an explicit act the user chooses, never something startup does.

**Does the cache follow the catalog, or the OS convention? Both, and the rule is one sentence:
the cache lives in the cache counterpart of wherever the catalog lives.**

* Catalog at its default (``user_data_dir``) - the counterpart is ``user_cache_dir``. This is the
  whole point of `(aae)`: a cache in the *data* directory would inherit the catalog's backup and
  retention treatment, which is wrong for something rebuilt in seconds.
* Catalog at an explicit ``--db`` path - there is no counterpart, so the cache sits beside it. A
  ``--db`` invocation stays self-contained, which is also what keeps **tests hermetic**: a
  machine-wide cache would have every test that organizes or attaches write into the developer's
  real cache directory.

**Sharing a cache between catalogs would be safe, and that is not what decided this.** Proven
from the code rather than assumed: rows are keyed by absolute path, the stored values are a pure
function of the file and the requested tag set, ``size`` + ``mtime_ns`` guard staleness, and
`_prune` deletes only rows whose file is genuinely gone - never one another run is using. So two
catalogs could share safely; the decision is about *lifetime* and *isolation*, not correctness.

The "a user who moves their catalog takes its cache with it" argument is also **illusory**, and
the cache module says so itself: rows are keyed by **absolute path, which is machine-specific**.
A cache carried to another machine is a hundred percent misses.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.app_paths import (
    RUN_RECORD_FILENAME,
    cache_path_for,
    default_cache_path,
    default_catalog_path,
    record_path_for,
)


def test_a_new_install_puts_the_catalog_in_the_os_data_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No legacy file: the catalog goes where the platform says user data goes."""
    monkeypatch.chdir(tmp_path)

    resolved = default_catalog_path()

    assert resolved.is_absolute(), "a CWD-relative default is undefined for an installed app"
    assert resolved.name == "catalog.sqlite"


def test_resolution_never_creates_anything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asking where the catalog *would* live must not make a directory or a file.

    Startup asks this before it knows whether the user is going to do anything at all.
    """
    monkeypatch.chdir(tmp_path)

    resolved = default_catalog_path()
    default_cache_path()

    assert not resolved.exists()
    assert list(tmp_path.iterdir()) == []


def test_the_cache_is_not_in_the_data_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The core of (aae): a disposable cache must not share the catalog's fate.

    An OS may clear the cache location or a backup tool may skip it - correct for a cache,
    catastrophic for the record of which drive holds the only copy of someone's photos.
    """
    monkeypatch.chdir(tmp_path)

    assert default_cache_path().parent != default_catalog_path().parent


def test_the_default_catalog_uses_the_os_cache_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache counterpart of the default catalog is the OS cache directory."""
    monkeypatch.chdir(tmp_path)

    assert cache_path_for(default_catalog_path()) == default_cache_path()


def test_an_explicit_db_keeps_its_cache_beside_it(tmp_path: Path) -> None:
    """A --db invocation stays self-contained - and this is what keeps tests hermetic."""
    db = tmp_path / "scratch.sqlite"

    assert cache_path_for(db).parent == tmp_path
    assert cache_path_for(db) != default_cache_path()


def test_two_explicit_catalogs_do_not_share_a_cache(tmp_path: Path) -> None:
    """Isolation for the case that matters most in practice: two test runs, or two libraries."""
    first = cache_path_for(tmp_path / "a" / "c.sqlite")
    second = cache_path_for(tmp_path / "b" / "c.sqlite")

    assert first != second


def test_the_run_record_sits_beside_the_catalog_wherever_it_is(tmp_path: Path) -> None:
    """⚠ The sibling half of `cache_path_for`'s rule WITHOUT the split, and that is the point.

    A cache is redirected to the OS cache directory for the conventional catalog, because losing
    one costs nothing. A record is data: it is the only place a finished run says what it did, so
    it belongs with the catalog wherever the catalog is. `(afl)`
    """
    db = tmp_path / "library" / "c.sqlite"

    assert record_path_for(db).parent == db.parent
    assert record_path_for(db).name == RUN_RECORD_FILENAME


def test_the_default_catalogs_record_is_not_sent_to_the_cache_directory() -> None:
    """The difference from `cache_path_for`, asserted rather than described."""
    catalog = default_catalog_path()

    assert record_path_for(catalog).parent == catalog.parent
    assert record_path_for(catalog).parent != default_cache_path().parent


def test_two_catalogs_do_not_share_a_record(tmp_path: Path) -> None:
    """A rolling file is overwritten each run - so two libraries must not overwrite each other's."""
    one = record_path_for(tmp_path / "a" / "c.sqlite")
    other = record_path_for(tmp_path / "b" / "c.sqlite")

    assert one != other


def test_resolving_a_record_path_creates_nothing(tmp_path: Path) -> None:
    """The same promise the other accessors make: asking where is not making."""
    resolved = record_path_for(tmp_path / "c.sqlite")

    assert not resolved.exists()
    assert list(tmp_path.iterdir()) == []
