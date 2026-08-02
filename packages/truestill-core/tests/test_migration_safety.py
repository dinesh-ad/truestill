"""The migration path is not atomic, and these are the four conventions that make it safe.

**Measured 2026-08-02, not assumed.** Interrupting v17 after its third `ALTER TABLE` left three
of five columns committed - each DDL statement autocommits under Python's legacy transaction
control, so a migration is *not* one transaction. The catalog survives that anyway:

    before          user_version=16   new columns=0/5
    interrupted     user_version=16   new columns=3/5
    next open       user_version=17   new columns=5/5   self-healed

Nothing was lost because of two conventions, and **a transaction is not one of them**:

1. ``user_version`` is bumped **after** the migration function returns, so a partial migration
   leaves the *old* version and never claims a schema that does not exist.
2. Every migration is **idempotent**, so the next open completes the partial work.

Both were conventions with nothing enforcing them, and the failure they prevent only shows up
when a real person loses power mid-upgrade. A third assumption holds the argument together: no
migration performs a **backfill**. DDL autocommits while DML does not, so a crash between them
would commit the column and roll back the data - and idempotency would then *skip* the retry,
because the column guard sees the column already there. That is the case where non-atomicity
genuinely bites, and today it cannot happen because every migration is DDL-only.

These tests pin all three, plus the transaction-control setting they depend on. **They are not a
substitute for a transaction; they are the reason one is not needed.** If a future migration
needs a backfill, `test_no_migration_performs_a_backfill` fails and forces that conversation
rather than letting it land silently.
"""

from __future__ import annotations

import ast
import contextlib
import inspect
import re
import sqlite3
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest
from truestill_core import catalog as catalog_module
from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog

#: The `files` table as it stood at v1, before any migration. Written out rather than derived,
#: so the chain below starts from a genuine historical shape rather than from today's schema.
_V1_FILES = """
CREATE TABLE files (
    id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL, relative TEXT NOT NULL, upload_status TEXT NOT NULL,
    processed_at TEXT NOT NULL
);
"""


class _PowerLossError(Exception):
    """Stands in for a crash mid-migration. Injected, so all three CI lanes run it."""


#: The five columns v17 adds, used by the interruption fixture.
_V17_COLUMNS = (
    ("camera_make", "TEXT"),
    ("camera_model", "TEXT"),
    ("lens_model", "TEXT"),
    ("gps_latitude", "REAL"),
    ("gps_longitude", "REAL"),
)


def _schema_of(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Every object's DDL, order-independent - the thing a re-run must not change."""
    return sorted(
        (str(row[0]), str(row[1]))
        for row in conn.execute("SELECT type, sql FROM sqlite_master WHERE sql IS NOT NULL")
    )


@contextlib.contextmanager
def _migrated_from_v1() -> Iterator[sqlite3.Connection]:
    """A connection carrying every migration applied in order from the v1 shape.

    A context manager so the handle closes deterministically: returning a bare connection leaked
    one per parametrised case, and a `ResourceWarning` surfaces wherever the collector happens
    to run - which lands it on an unrelated test.
    """
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.executescript(_V1_FILES)
        for _version, migrate in catalog_module._MIGRATIONS:
            migrate(conn)
        yield conn
    finally:
        conn.close()


def _sql_literals(function: object) -> list[str]:
    """Every string literal handed to ``.execute`` / ``.executescript`` inside ``function``.

    **AST over the execute argument, not a text scan of the source.** These migrations carry
    long explanations, and a raw grep for `UPDATE` would fail one for describing what it
    deliberately does *not* do. Reading only the literals handed to an execute call means
    comments and docstrings cannot trip it - proved by
    `test_the_backfill_guard_does_not_fire_on_prose`.

    **Blind spots, stated rather than discovered later:** SQL built at runtime from a non-literal
    expression, and DML performed by a helper the migration calls rather than inline. Neither
    exists today; both would slip past. The guard is a tripwire on the ordinary shape, not a
    proof.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))  # type: ignore[arg-type]
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"execute", "executescript", "executemany"}:
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                found.append(argument.value)
            elif isinstance(argument, ast.JoinedStr):
                found.extend(
                    part.value
                    for part in argument.values
                    if isinstance(part, ast.Constant) and isinstance(part.value, str)
                )
    return found


# --- pin 1: every migration is re-runnable -------------------------------------------------


@pytest.mark.parametrize(
    ("version", "migrate"),
    catalog_module._MIGRATIONS,
    ids=[f"v{v}-{m.__name__}" for v, m in catalog_module._MIGRATIONS],
)
def test_every_migration_is_idempotent(version: int, migrate: object) -> None:
    """Applying a migration twice must not error and must not change the schema.

    This is the property that lets an interrupted upgrade finish on the next open, and §3 states
    it in prose ("ordered, idempotent functions"). Stated in prose is not enforced.
    """
    with _migrated_from_v1() as conn:
        before = _schema_of(conn)
        migrate(conn)  # type: ignore[operator]
        after = _schema_of(conn)

    assert after == before, (
        f"v{version} changed the schema when applied a second time. An interrupted upgrade "
        "re-runs every migration from the recorded version, so a non-idempotent one turns a "
        "recoverable partial upgrade into an error the user cannot get past."
    )


def test_the_whole_chain_is_idempotent_end_to_end() -> None:
    """Cry-wolf half, and a stronger statement than the per-migration one.

    Each migration passing alone would not prove the *sequence* is safe to replay, which is what
    actually happens: `_migrate` re-runs every entry above the recorded version.
    """
    with _migrated_from_v1() as conn:
        before = _schema_of(conn)
        for _version, migrate in catalog_module._MIGRATIONS:
            migrate(conn)
        after = _schema_of(conn)

    assert after == before


# --- pin 2: the version never claims a schema that is not there ----------------------------


def test_an_interrupted_migration_leaves_the_old_version_and_then_self_heals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The measured scenario, pinned.

    Patching the migration function rather than the connection: `sqlite3.Connection` is an
    immutable C type and its `execute` cannot be replaced, so the interruption is injected one
    level up. Injection rather than a real process kill, so this runs on all three CI lanes.
    """
    db = tmp_path / "c.sqlite"
    with contextlib.closing(sqlite3.connect(str(db))) as conn:
        conn.executescript(f"{_V1_FILES}\nPRAGMA user_version = 16;")
        conn.commit()

    def interrupted(connection: sqlite3.Connection) -> None:
        for index, (column, kind) in enumerate(_V17_COLUMNS):
            if index == 3:
                raise _PowerLossError
            connection.execute(f"ALTER TABLE files ADD COLUMN {column} {kind}")

    monkeypatch.setattr(
        catalog_module,
        "_MIGRATIONS",
        tuple(
            (version, interrupted if version == 17 else migrate)
            for version, migrate in catalog_module._MIGRATIONS
        ),
    )
    with pytest.raises(_PowerLossError):
        Catalog(db)

    with contextlib.closing(sqlite3.connect(str(db))) as probe:
        version = int(probe.execute("PRAGMA user_version").fetchone()[0])
        columns = {row[1] for row in probe.execute("PRAGMA table_info(files)")}

    partial = {name for name, _kind in _V17_COLUMNS} & columns
    assert partial, "fixture check: the interruption must leave some work committed"
    assert version < 17, (
        f"user_version is {version} while only {len(partial)} of 5 columns exist. The version "
        "must never be ahead of the schema: it is bumped after the migration returns precisely "
        "so a partial upgrade re-runs instead of being skipped as already done."
    )

    monkeypatch.undo()
    with Catalog(db) as healed:
        assert healed.schema_version == CURRENT_SCHEMA_VERSION
    with contextlib.closing(sqlite3.connect(str(db))) as probe:
        columns = {row[1] for row in probe.execute("PRAGMA table_info(files)")}
    assert {name for name, _kind in _V17_COLUMNS} <= columns, "the next open must finish the job"


def test_a_normal_migration_still_arrives_complete(tmp_path: Path) -> None:
    """Cry-wolf half: an uninterrupted upgrade reaches the current version with its rows."""
    db = tmp_path / "c.sqlite"
    with contextlib.closing(sqlite3.connect(str(db))) as conn:
        conn.executescript(
            f"{_V1_FILES}\n"
            "INSERT INTO files (source_path, sha256, category, relative, upload_status, "
            "processed_at) VALUES ('/a.jpg','sha-a','Camera','C/a.jpg','uploaded','2026-01-01');\n"
            "PRAGMA user_version = 1;"
        )
        conn.commit()

    with Catalog(db) as catalog:
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION
        assert catalog._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 1


# --- pin 3: migrations are DDL-only --------------------------------------------------------

_DML = re.compile(r"\b(INSERT|UPDATE|DELETE)\b", re.IGNORECASE)


@pytest.mark.parametrize(
    ("version", "migrate"),
    catalog_module._MIGRATIONS,
    ids=[f"v{v}-{m.__name__}" for v, m in catalog_module._MIGRATIONS],
)
def test_no_migration_performs_a_backfill(version: int, migrate: object) -> None:
    """DDL and DML do not fail together, and that is the case non-atomicity would bite.

    DDL autocommits; DML runs inside an implicit transaction. A crash between them commits the
    column and rolls back the data - and the retry then **skips** the backfill, because the
    column guard sees the column already present. The partial state becomes permanent and
    silent.

    **If you are reading this because the guard failed: it is not in your way, it is the
    conversation.** A migration that needs a backfill needs an explicit transaction around the
    pair, or a separately-versioned data step that can be re-run on its own. Adding one without
    that is how a schema upgrade quietly loses data.
    """
    offending = [sql for sql in _sql_literals(migrate) if _DML.search(sql)]

    assert not offending, (
        f"v{version} appears to perform a data backfill: {offending}. See this test's docstring "
        "- the safety of the whole migration path assumes DDL-only steps."
    )


def test_the_backfill_guard_can_actually_see_a_backfill() -> None:
    """Anti-vacuity. A guard that reads no SQL would pass every migration silently."""

    def with_backfill(conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE files ADD COLUMN nickname TEXT")
        conn.execute("UPDATE files SET nickname = original_name")

    assert [sql for sql in _sql_literals(with_backfill) if _DML.search(sql)]
    # ...and it reads real SQL from the real migrations, not an empty list.
    assert any(_sql_literals(migrate) for _version, migrate in catalog_module._MIGRATIONS)


def test_the_backfill_guard_does_not_fire_on_prose() -> None:
    """The reason this reads execute arguments rather than grepping the source.

    These migrations carry long explanations, and one describing what it deliberately does *not*
    update would fail a text scan while touching no data at all. No migration's prose happens to
    say `UPDATE` today - checked - so the demonstration is built rather than borrowed, which
    also keeps it true if that prose is later reworded.
    """

    def explains_but_does_not_update(conn: sqlite3.Connection) -> None:
        """Adds a column. Deliberately does NOT UPDATE the existing rows or DELETE anything."""
        # An INSERT here would be a backfill; there is none.
        conn.execute("ALTER TABLE files ADD COLUMN nickname TEXT")

    assert _DML.search(textwrap.dedent(inspect.getsource(explains_but_does_not_update)))
    assert not [sql for sql in _sql_literals(explains_but_does_not_update) if _DML.search(sql)]


# --- pin 4: transaction control is chosen, not inherited -----------------------------------


def test_the_connection_pins_its_transaction_control_explicitly() -> None:
    """Python's docs say `autocommit`'s default will change to `False` in a future release.

    Inheriting it means a Python upgrade silently changes when our writes commit. The value is
    therefore passed at the connect call, and this reads the call site rather than the runtime
    value - `conn.autocommit` is already the legacy constant today, so a runtime check cannot
    tell "pinned" from "inherited" and would pass against the very code this guards.
    """
    # dedent: `__init__` is a method, so its source arrives indented and `ast.parse`
    # refuses it. The same trap `_sql_literals` hit.
    tree = ast.parse(textwrap.dedent(inspect.getsource(Catalog.__init__)))
    connects = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "connect"
    ]

    assert len(connects) == 1, f"expected exactly one sqlite3.connect call, found {len(connects)}"
    keywords = {keyword.arg for keyword in connects[0].keywords}
    assert "autocommit" in keywords, (
        "sqlite3.connect() inherits its transaction control. Python's documentation states the "
        "default changes to False in a future release, which would alter when every catalog "
        "write commits, without a line of our code changing. Pass it explicitly."
    )


def test_the_pinned_value_is_todays_behaviour_and_not_a_silent_change(tmp_path: Path) -> None:
    """Pinned, not adopted. Adopting the new semantics is a separate, deliberate decision."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert catalog._conn.autocommit == sqlite3.LEGACY_TRANSACTION_CONTROL


def test_pinning_changed_no_observable_behaviour(tmp_path: Path) -> None:
    """A pin that altered behaviour would be an adoption wearing a pin's name.

    Compared against a bare `sqlite3.connect`, which is what the code did before: same implicit
    transaction handling, so a rollback still discards an uncommitted write.
    """
    reference = sqlite3.connect(str(tmp_path / "reference.sqlite"))
    try:
        pinned = Catalog(tmp_path / "c.sqlite")
        try:
            assert pinned._conn.autocommit == reference.autocommit
            assert pinned._conn.isolation_level == reference.isolation_level
            pinned._conn.execute("INSERT INTO settings (key, value) VALUES ('k', 'v')")
            pinned._conn.rollback()
            assert pinned.get_setting("k") is None, "an uncommitted write must still roll back"
        finally:
            pinned.close()
    finally:
        reference.close()


def test_a_fresh_catalog_is_created_and_readable(tmp_path: Path) -> None:
    """Cry-wolf half for pin 4: the ordinary path still works with the value pinned."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.set_setting("hello", "world")
    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert catalog.get_setting("hello") == "world"
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION
