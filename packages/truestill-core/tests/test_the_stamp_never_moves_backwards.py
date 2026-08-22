"""`(afv)`: a migration step must never stamp a version the file is already past.

⚠ **WHY THIS EXISTS BESIDE `test_a_migration_step_is_all_or_nothing.py`, WHICH ALREADY COVERS
`(adl)`.** That file's `test_concurrent_openers_of_a_behind_catalog_all_succeed` asserts what each
opener *returns*, so it goes red only when a read happens to land inside the window where the
version is low. Measured: runs where **all six openers returned 20** still moved the file
`20 -> 5`, `20 -> 19`, `20 -> 4` on disk. **That test samples an outcome; this asserts the
property.**

⚠ **AND THE FIRST TWO VERSIONS OF *THIS* FILE WERE BOTH WRONG, WHICH IS WORTH MORE THAN THE
GUARD.** Recorded because each failed in a way §4 already names:

1. **It sampled the natural race 25 times** and asserted no dip. 61 s, and its power came from the
   *amplification* `(ady)` happened to supply - 28/40 rounds against 7/40 before it. Fixing
   `(ady)` would have silently returned it to ~17% a round.
2. **It watched the file from a polling thread.** That is an instrument that can be *starved*: on
   CI under `pytest-xdist` the observer saw `[3, 20]` - **endpoints only** - and its non-emptiness
   guard went red. ⚠ **The guard firing was the lucky half.** Written any looser, the *primary*
   assertion would have passed **vacuously**, because an observer that never sees an intermediate
   value cannot see a dip either. A sampler cannot guarantee it observes the window it exists for.

**So there is no observer.** The interleave is constructed, and the version is read at the two
instants that decide the property - immediately before and immediately after the late step - from
a connection taking no part in the race. Deterministic, and it cannot pass vacuously: the
"before" read **is** the proof that the interleave happened.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import truestill_core.catalog as catalog_module
from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog

#: The step the late opener is held at - the chain's first, so the gap to `CURRENT` is widest.
LATE_TARGET = 4


def _behind(db: Path) -> None:
    """A catalog at v3 with the `files` table, so an opener has a real chain to run."""
    con = sqlite3.connect(db)
    con.executescript(
        "CREATE TABLE files (id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE,"
        " source_path TEXT, relative TEXT, copied_at TEXT);"
        "PRAGMA user_version = 3;"
    )
    con.commit()
    con.close()


def _version_of(db: Path) -> int:
    """The file's version, read by a connection taking no part in the race."""
    con = sqlite3.connect(db, timeout=30)
    try:
        return int(con.execute("PRAGMA user_version").fetchone()[0])
    finally:
        con.close()


def _forced_race(db: Path) -> tuple[int, int, list[object]]:
    """Hold one opener at its first step until another has finished the whole chain.

    Returns the file's version immediately **before** and **after** the late step runs, plus what
    each opener returned. That pair is the whole measurement: it needs no sampling, and the
    "before" value proves the interleave was really constructed.
    """
    outcomes: list[object] = []
    late_is_waiting = threading.Event()
    chain_finished = threading.Event()
    late_thread: dict[str, int] = {}
    around: dict[str, int] = {}
    real_apply = catalog_module._apply_step

    def held(
        conn: sqlite3.Connection, target: int, migrate: Callable[[sqlite3.Connection], None]
    ) -> None:
        late = threading.get_ident() == late_thread.get("id") and target == LATE_TARGET
        if late:
            # Held BEFORE the step, so no transaction is open and the other opener is free to
            # take the write lock. Holding it *inside* one would deadlock rather than race.
            late_is_waiting.set()
            chain_finished.wait(timeout=20)
            around["before"] = _version_of(db)
        real_apply(conn, target, migrate)
        if late:
            around["after"] = _version_of(db)

    def opener() -> None:
        try:
            with Catalog(db) as catalog:
                outcomes.append(catalog.schema_version)
        except Exception as error:
            outcomes.append(f"{type(error).__name__}: {error}")

    def late() -> None:
        late_thread["id"] = threading.get_ident()
        opener()

    with patch.object(catalog_module, "_apply_step", held):
        slow = threading.Thread(target=late)
        slow.start()
        assert late_is_waiting.wait(timeout=20), "the late opener never reached its first step"
        fast = threading.Thread(target=opener)
        fast.start()
        fast.join(timeout=30)
        chain_finished.set()
        slow.join(timeout=30)

    return around.get("before", -1), around.get("after", -1), outcomes


def test_a_late_step_does_not_stamp_over_a_finished_chain(tmp_path: Path) -> None:
    """The property `(adl)` left open, asserted at the instant it can be violated.

    ⚠ **A backwards stamp is not cosmetic.** The file then claims a schema **older than it has**,
    so the next open re-runs migrations against columns that already exist - survivable only
    because every migration happens to be idempotent, which `catalog.py` already calls
    *"luck holding, not a design"*.
    """
    db = tmp_path / "catalog.sqlite"
    _behind(db)

    before, after, outcomes = _forced_race(db)

    # The interleave, proven rather than assumed: the chain really did finish while the late
    # opener was held. Without this the assertion below could pass on a race that never happened.
    assert before == CURRENT_SCHEMA_VERSION, (
        f"the interleave was not forced - the file was at {before} when the late step was "
        f"released, so there was nothing for it to stamp over"
    )
    assert after == CURRENT_SCHEMA_VERSION, (
        f"user_version moved BACKWARDS: {before} -> {after}. `_apply_step` must re-read the "
        "version inside its own `BEGIN IMMEDIATE` and skip a step the file is already past - "
        "otherwise an opener that entered the chain late stamps its low target over a version "
        "another opener has already carried forward."
    )
    assert outcomes == [CURRENT_SCHEMA_VERSION, CURRENT_SCHEMA_VERSION], outcomes


def test_the_file_ends_at_the_current_version(tmp_path: Path) -> None:
    """The weaker, outcome-shaped claim, kept so the pair reads together.

    This is what the existing `(adl)` test asserts. It passes on runs where the file dipped and
    recovered before anyone looked, which is exactly why the test above is the one that bites.
    """
    db = tmp_path / "catalog.sqlite"
    _behind(db)

    _forced_race(db)

    assert _version_of(db) == CURRENT_SCHEMA_VERSION
