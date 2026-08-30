"""A rename may overwrite the drive's name; nothing else may. `(aix)` stage 2b

**The guard is `(ahz)` step 3 and it is not weakened here.** `would_lose` refuses to overwrite a
value a drive holds, because the catalog might be a REBUILD that never knew it - written after a
real name was destroyed. It cannot tell that from a user who just renamed something, and **only
the writer knows which**.

🔑 **THE FIX IS A LEASE, NOT A FORCE FLAG, and the `expected` value is the difference.** Git names
it exactly: `--force` "has really no checking", while `--force-with-lease` does "an atomic
compare-and-swap on the branch you are pushing to, based on the last information you fetched".
So a lease says *"overwrite this key IF the drive still holds `expected`"* - never *"overwrite
this key"*. The scoped, per-key form is the **field mask** pattern that Google's AIP-134/161
require rather than tolerate; the unscoped `force=true` boolean is the anti-pattern.

**A rebuilt catalog leases nothing**, so it is refused in full without anyone having to notice it
is a rebuild. That is the self-identifying half, and it is why this beats a caller-supplied flag.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
from truestill_core.catalog import Catalog
from truestill_core.decisions import (
    Decisions,
    document_key_text,
    gather_decisions,
    read_decisions,
    would_lose,
    write_decisions,
)
from truestill_core.destinations.local import LocalDestination
from truestill_core.hashing import sha256_file
from truestill_core.layout_settings import resolve_scheme
from truestill_core.migrate import ROUTE_TIMELINE, RenameKind, apply_rename, plan_rename

_DAYS = ["2014-08-15", "2014-08-16"]


@pytest.fixture
def drive(tmp_path: Path) -> tuple[Path, Path, int]:
    root, db = tmp_path / "drive", tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        for day in _DAYS:
            relative = f"Camera/2014/2014-08/{day} - Holiday/{day}.jpg"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(day.encode())
            catalog.record_uploaded(
                source_path=f"/src/{day}.jpg",
                original_name=PurePosixPath(relative).name,
                sha256=sha256_file(path),
                copy_sha256=sha256_file(path),
                perceptual=None,
                size=10,
                captured_at=f"{day}T10:00:00",
                category="Camera",
                relative=relative,
                drive_uuid="D1",
            )
        trip_id = catalog.create_trip(
            name="Holiday", slug="holiday", start_date=_DAYS[0], end_date=_DAYS[-1], days=_DAYS
        )
    return root, db, trip_id


def _rename(db: Path, root: Path, trip_id: int, name: str) -> None:
    with Catalog(db) as catalog:
        plan = plan_rename(
            catalog,
            "D1",
            resolve_scheme(catalog),
            kind=RenameKind.TRIP,
            row_id=trip_id,
            new_name=name,
            routes={"Camera": ROUTE_TIMELINE},
        )
        apply_rename(catalog, LocalDestination(root), "D1", plan)


def _on_drive(name: str) -> Decisions:
    """A document as a drive would hold it, naming this trip ``name``."""
    return Decisions(
        settings={},
        trips=({"name": name, "slug": name.lower(), "days": list(_DAYS)},),
        events=(),
        skipped_clusters=(),
        date_confirmations=(),
        albums=(),
        written="2020-01-01T00:00:00+00:00",
    )


def test_the_rename_leases_exactly_one_key_and_names_what_it_expects(
    drive: tuple[Path, Path, int],
) -> None:
    """THE MECHANISM. Scoped to one key, and carrying the value it expects to find."""
    root, db, trip_id = drive

    _rename(db, root, trip_id, "Corsica")

    with Catalog(db) as catalog:
        leases = catalog.authored_decisions()
    assert leases == {("trips", document_key_text(tuple(_DAYS))): "Holiday"}, (
        f"the lease is not scoped to the renamed key: {leases}"
    )


def test_the_drive_document_takes_the_new_name(drive: tuple[Path, Path, int]) -> None:
    """The half stage 2 could not do: `would_lose` now lets this key through."""
    root, db, trip_id = drive
    write_decisions(root, _on_drive("Holiday"))

    _rename(db, root, trip_id, "Corsica")

    with Catalog(db) as catalog:
        fresh, leases = gather_decisions(catalog, "D1"), catalog.authored_decisions()
    existing = read_decisions(root).decisions
    assert existing is not None
    assert would_lose(existing, fresh, authored=leases) == (), (
        "the rename is still refused by its own guard"
    )


def test_a_rebuilt_catalog_is_still_refused(drive: tuple[Path, Path, int]) -> None:
    """🔑 **Q1004's PROOF, and it must fail if the permission ever leaks.**

    A rebuilt catalog holding a placeholder against a drive holding the real name is exactly
    `(ahz)`'s measured data loss. It **authored nothing**, so it leases nothing, so the guard bites
    in full - and the lease table dying with the catalog is what makes that automatic rather than
    something a caller has to remember.
    """
    root, db, trip_id = drive
    _rename(db, root, trip_id, "Corsica")
    with Catalog(db) as catalog:
        leases = catalog.authored_decisions()
    assert leases, "the fixture did not lease anything, so this proves nothing"

    # The drive holds a real name this catalog has never seen, and the catalog holds a placeholder.
    rebuilt = _on_drive("placeholder B")
    theirs = _on_drive("Morning Market")

    assert would_lose(theirs, rebuilt) == ("trips",), "the guard stopped biting without a lease"
    # ⚠ **AND IT STILL BITES WITH THIS CATALOG'S LEASE IN HAND**, because the lease expects
    # `Holiday` and the drive says `Morning Market`. A force flag would have overwritten it.
    assert would_lose(theirs, rebuilt, authored=leases) == ("trips",), (
        "the lease leaked to a key it did not author - this is the data loss (ahz) measured"
    )


def test_a_drive_changed_elsewhere_is_refused_even_with_a_lease(
    drive: tuple[Path, Path, int],
) -> None:
    """⚠ **THE `--force-with-lease` PROPERTY, and what a plain force flag would get wrong.**

    Rename here, then someone renames the same trip on another machine and that drive carries
    their name. Our lease expects `Holiday`; the drive says `Diwali`. The compare-and-swap fails,
    so the write is refused and their name survives - which is the whole reason the lease stores
    a value rather than a permission.
    """
    root, db, trip_id = drive
    _rename(db, root, trip_id, "Corsica")
    with Catalog(db) as catalog:
        fresh, leases = gather_decisions(catalog, "D1"), catalog.authored_decisions()

    assert would_lose(_on_drive("Diwali"), fresh, authored=leases) == ("trips",), (
        "a name made on another machine was overwritten - the lease behaved as a force flag"
    )
    # The same catalog, against the drive it actually left behind, still passes.
    assert would_lose(_on_drive("Holiday"), fresh, authored=leases) == ()


def test_an_event_rename_leases_by_signature(tmp_path: Path) -> None:
    """⚠ **Both kinds, tested rather than inferred.** The document keys a trip by its DAY SET and
    an event by its SIGNATURE - `(ahz)` recorded that asymmetry - so the join from a row-keyed
    rename differs per kind and each needs its own proof.
    """
    root, db = tmp_path / "drive", tmp_path / "c.sqlite"
    signature = "e" * 64
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        shas = []
        for name in ("a", "b"):
            relative = f"Camera/2015/2015-10/2015-10-25 - Party/{name}.jpg"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode() * 8)
            shas.append(sha256_file(path))
            catalog.record_uploaded(
                source_path=f"/s/{name}.jpg",
                original_name=f"{name}.jpg",
                sha256=shas[-1],
                copy_sha256=shas[-1],
                perceptual=None,
                size=16,
                captured_at="2015-10-25T10:00:00",
                category="Camera",
                relative=relative,
                drive_uuid="D1",
            )
        event_id = catalog.record_event(
            name="Party", slug="party", start_date="2015-10-25", file_count=2, signature=signature
        )
        catalog.set_event_id(shas, event_id)
        plan = plan_rename(
            catalog,
            "D1",
            resolve_scheme(catalog),
            kind=RenameKind.EVENT,
            row_id=event_id,
            new_name="Diwali",
            routes={"Camera": ROUTE_TIMELINE},
        )
        apply_rename(catalog, LocalDestination(root), "D1", plan)
        leases = catalog.authored_decisions()

    assert leases == {("events", signature): "Party"}, (
        f"an event must lease by signature, not by row id or day set: {leases}"
    )


def test_a_process_killed_before_the_publish_still_publishes_next_time(
    drive: tuple[Path, Path, int],
) -> None:
    """⚠ **Q1007: WHERE THE PUBLISH SITS, AND WHAT DIES BETWEEN.** `(aix)` stage 2b

    The sequence is: move every file, then **flip the name and record the lease in ONE
    transaction**, then publish on the catalog's close. So the only gap a process can die in is
    between the flip and the publish - and the lease is on disk by then, because it was written in
    the same transaction as the flip.

    🔑 **That is why the lease is a TABLE and not an in-memory set.** Held in memory it would die
    with the process, the document would keep the old name forever, and the refusal note would
    return - which is exactly the state stage 2 shipped with. Durable, the next publish carries
    it, and no user action is needed.

    Simulated by renaming with no drive document present (so nothing publishes), then publishing
    afterwards from a fresh catalog open - which is what a later run does.
    """
    root, db, trip_id = drive
    _rename(db, root, trip_id, "Corsica")

    # The drive's document appears only AFTER the rename - the write the killed process never did.
    write_decisions(root, _on_drive("Holiday"))

    with Catalog(db) as catalog:  # a later, ordinary open
        fresh, leases = gather_decisions(catalog, "D1"), catalog.authored_decisions()
    existing = read_decisions(root).decisions
    assert existing is not None

    assert leases, "the lease did not survive the process that wrote it"
    assert would_lose(existing, fresh, authored=leases) == (), (
        "a rename interrupted before its publish can never publish again"
    )
