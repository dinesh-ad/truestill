"""Re-naming a trip the screen offered again must change the name, or say why not.

**The defect, and why it is worse than a wrong answer.** The review screen re-offers a trip whose
days are already claimed - `assemble_trip_review` never consults `trip_for_day`, so an
already-named trip comes back with an empty name box like any other card. Typing a new name into
it did nothing at all: `commit_trips` took the already-claimed branch, called
:meth:`Catalog.update_trip_days`, and **never read** ``decision.name``. No error, no note, no
change. A question asked and the reply discarded while reporting success (§9 never-silent).

Downstream it also made the app state something untrue: ``apply_event_review_names`` reports
``"name": name.strip()`` - the name the user typed - so the "reveal in file manager" row named a
trip the catalog had not renamed.

**Renaming is safe, and this is not a new decision.** `record_event` already renames on
re-commit (``ON CONFLICT(signature) DO UPDATE SET name = excluded.name``), which likewise leaves
a placed library's folders spelling the old name until the next migration. Trips were simply the
one shape without a rename path. Catalog-then-reconcile is the same forward/reconcile split a
layout-template change already uses; `copies_for_migration` selects ``t.name AS trip_name``, so
the next migration renders the new name and offers the moves.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.trip_review import TripDecision, commit_trips
from truestill_core.trips import TripProposal

_DAYS = (date(2014, 8, 14), date(2014, 8, 15), date(2014, 8, 16), date(2014, 8, 17))


def _proposal() -> TripProposal:
    return TripProposal(
        start_date=_DAYS[0], end_date=_DAYS[-1], days=dict.fromkeys(_DAYS, 10)
    )


def _named(catalog: Catalog) -> tuple[str, str]:
    row = catalog._conn.execute("SELECT name, slug FROM trips").fetchone()  # noqa: SLF001
    return str(row["name"]), str(row["slug"])


def _claim(catalog: Catalog, name: str) -> int:
    return commit_trips(catalog, [TripDecision(_proposal(), name)])


def test_renaming_an_already_claimed_trip_changes_its_name(tmp_path: Path) -> None:
    """THE DEFECT. Before the fix the second name was read, discarded, and reported as success."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _claim(catalog, "Wayanad")
        _claim(catalog, "Kerala 2014")
        name, slug = _named(catalog)

    assert name == "Kerala 2014", f"the new name was discarded; the trip is still {name!r}"
    assert slug == "kerala-2014", "the slug still spells the old name"


def test_a_rename_is_reported_rather_than_done_silently(tmp_path: Path) -> None:
    """Never-silent. The count is what lets the screen say the rename happened."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _claim(catalog, "Wayanad")
        renamed = _claim(catalog, "Kerala 2014")

    assert renamed == 1, "a rename was applied but reported as nothing done"


def test_declining_a_re_offered_trip_never_erases_the_name_it_has(tmp_path: Path) -> None:
    """The cry-wolf half, and the one that matters most.

    A re-offered card arrives with an EMPTY box, and leaving it empty is how a user says "skip".
    If a blank reply overwrote the stored name, simply opening the screen and pressing Save would
    strip every trip in the library of its name - a far worse defect than the one being fixed.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _claim(catalog, "Wayanad")
        assert commit_trips(catalog, [TripDecision(_proposal(), None)]) == 0
        assert commit_trips(catalog, [TripDecision(_proposal(), "   ")]) == 0
        name, slug = _named(catalog)

    assert (name, slug) == ("Wayanad", "wayanad")


def test_the_same_name_again_is_not_reported_as_a_rename(tmp_path: Path) -> None:
    """A re-run over unchanged cards is a pure re-ask; it changed nothing and must not claim to."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _claim(catalog, "Wayanad")
        again = _claim(catalog, "Wayanad")
        name, _ = _named(catalog)

    assert again == 0, "an unchanged name was reported as a rename"
    assert name == "Wayanad"


def test_membership_still_refreshes_when_the_days_change(tmp_path: Path) -> None:
    """The behaviour that already existed on this branch must survive the repair (§6 edge trim)."""
    trimmed = _DAYS[:3]
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _claim(catalog, "Wayanad")
        commit_trips(catalog, [TripDecision(_proposal(), "Wayanad", confirmed_days=list(trimmed))])
        row = catalog._conn.execute("SELECT start_date, end_date FROM trips").fetchone()  # noqa: SLF001
        days = [r["day"] for r in catalog._conn.execute("SELECT day FROM trip_days ORDER BY day")]  # noqa: SLF001

    assert str(row["end_date"]) == trimmed[-1].isoformat()
    assert days == [d.isoformat() for d in trimmed]
