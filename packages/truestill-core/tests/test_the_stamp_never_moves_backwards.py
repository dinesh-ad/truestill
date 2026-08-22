"""`(afv)`: `user_version` must never move backwards under concurrent migrating opens.

⚠ **WHY THIS EXISTS BESIDE `test_a_migration_step_is_all_or_nothing.py`, WHICH ALREADY COVERS
`(adl)`.** That file's `test_concurrent_openers_of_a_behind_catalog_all_succeed` asserts what each
opener *returns*, so it goes red only when a read happens to land inside the window where the
version is low. Measured: runs where **all six openers returned 20** still moved the file
`20 -> 5`, `20 -> 19`, `20 -> 4` on disk. **That test understated the defect by construction** - it
samples an outcome; this asserts the property.

⚠ **AND IT IS FORCED, NOT SAMPLED, WHICH IS THE SECOND CORRECTION.** The first version of this
file ran the natural race 25 times and asserted no dip. It passed, and it was weak twice over: it
cost 61 s, and its power depended on the *amplification* `(ady)` happened to supply - 28/40 rounds
against 7/40 before it. Fixing `(ady)` would have quietly taken it back to ~17% per round and left
a guard that needs 25 rounds to be worth anything. §4's twenty-fifth member: for a mechanism that
can lie, build a differential rather than counting green runs. So the interleave is **constructed**
- one opener is held at its first step until another has carried the chain to the end - and one
run is then decisive.
"""

from __future__ import annotations

import contextlib
import itertools
import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import truestill_core.catalog as catalog_module
from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog

#: The step the late opener is held at. Any early target works; 4 is the chain's first.
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


def _watch(db: Path, stop: threading.Event, out: list[int]) -> None:
    """Sample `user_version` from a connection taking no part in the race.

    Reading it from an opener would ask what that connection believes; the claim is about the
    **file**, so the observer has to be outside.
    """
    watcher = sqlite3.connect(db, timeout=30)
    try:
        while not stop.is_set():
            with contextlib.suppress(sqlite3.Error):
                version = int(watcher.execute("PRAGMA user_version").fetchone()[0])
                if not out or out[-1] != version:
                    out.append(version)
            time.sleep(0.0005)
    finally:
        watcher.close()


def _forced_race(db: Path) -> tuple[list[int], list[object]]:
    """Hold one opener at its first step until another has finished the whole chain.

    That is the interleave the defect needs and the one a `sleep` cannot produce: both openers
    read `version = 3`, one completes to 20, and only then does the other stamp its low target.
    """
    seen: list[int] = []
    outcomes: list[object] = []
    stop = threading.Event()
    late_is_waiting = threading.Event()
    chain_finished = threading.Event()
    late_thread: dict[str, int] = {}
    real_apply = catalog_module._apply_step

    def held(
        conn: sqlite3.Connection, target: int, migrate: Callable[[sqlite3.Connection], None]
    ) -> None:
        if threading.get_ident() == late_thread.get("id") and target == LATE_TARGET:
            # Held BEFORE the step, so no transaction is open and the other opener is free to
            # take the write lock. Holding it *inside* one would deadlock rather than race.
            late_is_waiting.set()
            chain_finished.wait(timeout=20)
        real_apply(conn, target, migrate)

    def opener() -> None:
        try:
            with Catalog(db) as catalog:
                outcomes.append(catalog.schema_version)
        except Exception as error:
            outcomes.append(f"{type(error).__name__}: {error}")

    def late() -> None:
        late_thread["id"] = threading.get_ident()
        opener()

    observer = threading.Thread(target=_watch, args=(db, stop, seen), daemon=True)
    observer.start()
    with patch.object(catalog_module, "_apply_step", held):
        slow = threading.Thread(target=late)
        slow.start()
        assert late_is_waiting.wait(timeout=20), "the late opener never reached its first step"
        fast = threading.Thread(target=opener)
        fast.start()
        fast.join(timeout=30)
        chain_finished.set()
        slow.join(timeout=30)
    stop.set()
    observer.join(timeout=5)
    return seen, outcomes


def test_user_version_never_moves_backwards_under_concurrent_opens(tmp_path: Path) -> None:
    """The property `(adl)` left open: a step must not stamp over a version already ahead.

    ⚠ **A backwards stamp is not cosmetic.** The file then claims a schema **older than it has**,
    so the next open re-runs migrations against columns that already exist - survivable only
    because every migration happens to be idempotent, which `catalog.py` already calls
    *"luck holding, not a design"*.
    """
    db = tmp_path / "catalog.sqlite"
    _behind(db)

    seen, outcomes = _forced_race(db)

    backwards = [(a, b) for a, b in itertools.pairwise(seen) if b < a]
    assert not backwards, (
        f"user_version moved BACKWARDS on disk: {backwards} (full series {seen}). `_apply_step` "
        "must re-read the version inside its own `BEGIN IMMEDIATE` and skip a step the file is "
        "already past - otherwise an opener that entered the chain late stamps its low target "
        "over a version another opener has already carried forward."
    )
    assert outcomes == [CURRENT_SCHEMA_VERSION, CURRENT_SCHEMA_VERSION], outcomes


def test_the_interleave_is_actually_forced(tmp_path: Path) -> None:
    """Non-emptiness, §4's fifty-second member - and here it is the whole of the test's power.

    Zero backward transitions over a race that never happened is the same green as zero over a
    correct one. This asserts the constructed order really occurred: the observer saw the chain
    reach the end **while** the late opener was still held, which is the only arrangement in which
    the assertion above can fail.
    """
    db = tmp_path / "catalog.sqlite"
    _behind(db)

    seen, _ = _forced_race(db)

    assert seen[0] == 3, seen
    assert CURRENT_SCHEMA_VERSION in seen, f"no opener ever finished the chain: {seen}"
    assert len(seen) > 2, f"the observer saw only endpoints, so it could not detect a dip: {seen}"
