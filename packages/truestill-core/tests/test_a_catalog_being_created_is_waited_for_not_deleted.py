"""A catalog another process is creating is waited for, and never called debris. `(afp)`

**Measured.** Two `organize --apply` runs start against a catalog path that does not exist yet.
One creates the file and begins writing; the other lands in the window where it exists, is 0
bytes, and has a rollback journal beside it - and refused the whole run with *"Rename or delete
this file and run again"*, about a **live catalog the winner was writing**. 2 of 6 concurrent cold
starts, then again on demand.

⚠ **`(adr)`'s refusal is correct and stays.** A `copy2` killed by `ENOSPC` really does leave a
0-byte file, and opening it would build a schema into it and report a healthy empty library. What
is new is that a healthy concurrent start produces **the same evidence**, and the journal is the
discriminator `(adr)` already found and did not use.

**The rule, and it is a rule rather than a special case:** *wait when the contended state is
bounded and short; refuse when it is not.* Creating a catalog is milliseconds, so waiting here is
indistinguishable from the command working. A held drive lock is seconds to hours, so `drive_lock`
refuses instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.catalog_startup import (
    _CREATION_WAIT_SECONDS,
    CatalogPresence,
    inspect_catalog,
)


def _empty_with_journal(tmp_path: Path) -> Path:
    db = tmp_path / "catalog.sqlite"
    db.write_bytes(b"")
    db.with_name(db.name + "-journal").write_bytes(b"")
    return db


def test_a_catalog_that_fills_while_we_watch_is_opened_not_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **The fix.** The winner finishes; the loser must simply proceed.

    The other process is simulated at the one place its effect is visible - the file growing
    between two stats - because a real second process would make this a timing test rather than a
    behaviour one, and the behaviour is what is claimed.
    """
    db = _empty_with_journal(tmp_path)

    def winner_commits(_seconds: float) -> None:
        """The other process finishes while we are between two stats.

        A REAL catalog, not padding: the point of falling through is that the file is then
        opened, so a fake would fail for a reason that has nothing to do with the wait.
        """
        db.with_name(db.name + "-journal").unlink(missing_ok=True)
        with Catalog(db):
            pass

    monkeypatch.setattr("truestill_core.catalog_startup._sleep", winner_commits)

    info = inspect_catalog(db, explicit_db=True)

    assert info.presence is not CatalogPresence.ZERO_BYTES, (
        "a catalog that filled while we watched was still refused as debris"
    )


def test_the_bound_fires_and_the_refusal_stops_saying_delete_this_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **The holder deliberately never finishes, and the WORDING is what is asserted.**

    A bound that fires with `(adr)`'s *"rename or delete this file"* has fixed nothing: that is
    the sentence the whole entry is about, and it would still be given to whoever lost the race.
    """
    db = _empty_with_journal(tmp_path)
    slept: list[float] = []
    clock = iter([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])

    monkeypatch.setattr("truestill_core.catalog_startup._now", lambda: next(clock, 99.0))
    monkeypatch.setattr("truestill_core.catalog_startup._sleep", slept.append)

    info = inspect_catalog(db, explicit_db=True)
    detail = info.detail

    assert info.presence is CatalogPresence.ZERO_BYTES, "a file that never filled must be refused"
    assert slept, "the bound cannot have fired, because nothing ever waited"
    assert "delete this file" not in detail, (
        f"the refusal still tells the user to delete what may be a live catalog:\n{detail}"
    )
    assert "still empty after" in detail, (
        f"the refusal must say what was observed rather than diagnose an interruption:\n{detail}"
    )
    assert "let it finish" in detail, (
        f"the refusal must name the possibility it just waited on:\n{detail}"
    )
    assert f"{_CREATION_WAIT_SECONDS:.0f} seconds" in detail, (
        f"the refusal must say how long it waited, so the number is not folklore:\n{detail}"
    )


def test_a_zero_byte_catalog_with_no_journal_is_refused_immediately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **`(adr)`'s own case, and it must not have been slowed down or softened.**

    A failed `copy2` leaves a 0-byte file and **no** journal. That is not contention, so there is
    nothing to wait for - waiting would only delay a refusal that is already right.
    """
    db = tmp_path / "catalog.sqlite"
    db.write_bytes(b"")
    slept: list[float] = []
    monkeypatch.setattr("truestill_core.catalog_startup._sleep", slept.append)

    info = inspect_catalog(db, explicit_db=True)

    assert info.presence is CatalogPresence.ZERO_BYTES
    assert not slept, "with no journal there is no write in flight, so nothing may be waited for"
    assert "delete this file" in info.detail, "`(adr)`'s advice is right for `(adr)`'s case"
