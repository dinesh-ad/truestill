"""The hash cache's own connection carries the same pragma the catalog's does.

**It is the only connection in the codebase that is not a `Catalog`**, checked by search rather
than remembered: `grep sqlite3.connect` over `packages/*/src`, `scripts/` and `packaging/` returns
three sites - two here and one in `Catalog.__init__`.

**Nothing is unenforced today**, which is exactly why it is worth setting. `hash_cache`'s schema
declares no foreign key, so the pragma changes no behaviour now. It is set so that the day
someone adds a `REFERENCES` clause here, it is enforced - SQLite silently ignores one otherwise,
and the failure mode is a database that accepts orphans while the schema says it cannot.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.hash_cache import HashCache


def test_the_writable_connection_enforces_foreign_keys(tmp_path: Path) -> None:
    with HashCache(tmp_path / "c.cache.sqlite") as cache:
        assert cache._conn is not None
        assert cache._conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_the_read_only_connection_enforces_them_too(tmp_path: Path) -> None:
    """A read-only connection cannot violate an FK, but it can READ through one in a future
    query plan, and a pragma set on one connection and not its twin is the drift this pins."""
    path = tmp_path / "c.cache.sqlite"
    with HashCache(path):
        pass

    with HashCache.beside_readonly(path.parent / "c.sqlite") as cache:
        assert cache._conn is not None
        assert cache._conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_a_catalog_and_its_cache_agree(tmp_path: Path) -> None:
    """The point of the whole file: two connections in one process must not be configured
    differently. Asserted against the catalog rather than against the literal 1, so the day the
    catalog's settings change this fails instead of drifting quietly."""
    with Catalog(tmp_path / "c.sqlite") as catalog, HashCache(tmp_path / "c.cache.sqlite") as cache:
        assert cache._conn is not None
        catalog_fk = catalog._conn.execute("PRAGMA foreign_keys").fetchone()[0]
        cache_fk = cache._conn.execute("PRAGMA foreign_keys").fetchone()[0]

    assert cache_fk == catalog_fk
