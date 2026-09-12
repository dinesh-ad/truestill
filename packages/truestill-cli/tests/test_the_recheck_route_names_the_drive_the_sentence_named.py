"""The re-check route must point at the drive the sentence above it just named.

⚠ **TWO CONSECUTIVE LINES NAMING DIFFERENT DRIVES**, on a real two-drive run, 2026-09-12:

    Never checked: 'Library'. Truestill has not looked since the copy was written.
      Re-check: truestill verify <the path of the OTHER drive>

`drive.custody_freshness` excludes a drive that `was_ever_checked` even when `last_verified` is
NULL - the stamp is NULL both when nobody looked and when a verify looked and found gaps, `(aes)`.
`_recheck_route` tested `not last_verified` alone, so its candidate set was wider than the
sentence's and it offered the first CONNECTED member of the difference. Core's own comment reads
*"One predicate, four surfaces"*; this route was a fifth that never got it.

Same class as `(aiy)` - a second implementation of one predicate, disagreeing in the case nobody
had two real drives to produce.
"""

from __future__ import annotations

from truestill_cli import cli
from truestill_cli.cli import _recheck_route


class _Catalog:
    """Just enough catalog: every drive is connected, so reach never decides the outcome."""

    def __init__(self, hints: dict[str, str]) -> None:
        self._hints = hints

    def get_setting(self, key: str) -> str | None:
        return self._hints.get(key)


def _drive(uuid: str, label: str, *, last_verified: str | None, checked: int) -> dict[str, object]:
    """One `Catalog.list_drives` row.

    ⚠ **`confirmed_count` / `missing_count` are the keys `was_ever_checked` reads**, and using any
    other name gives a fixture that proves nothing - `drive.was_ever_checked`'s own docstring warns
    that a dict-based test can pass against an implementation that never runs. The first draft of
    this file used `checked_at` and went green against the defect.
    """
    return {
        "uuid": uuid,
        "label": label,
        "last_verified": last_verified,
        "confirmed_count": checked,
        "missing_count": 0,
    }


def test_a_drive_that_was_checked_with_gaps_is_not_offered_as_never_checked(
    monkeypatch, tmp_path
) -> None:
    """⚠ **THE DEFECT.** `Library` has never been looked at; `AD_2TB` was looked at and had gaps,
    so its `last_verified` is NULL too. The sentence names only `Library`, so the route must."""
    library, external = tmp_path / "Library", tmp_path / "AD_2TB"
    library.mkdir()
    external.mkdir()
    monkeypatch.setattr(cli, "drive_reach", lambda _hint, _uuid: cli.DriveReach.CONNECTED)

    holding = [
        _drive("u-ext", "AD_2TB", last_verified=None, checked=1),
        _drive("u-lib", "Library", last_verified=None, checked=0),
    ]
    catalog = _Catalog({"drive_path::u-ext": str(external), "drive_path::u-lib": str(library)})
    monkeypatch.setattr(cli, "drive_path_hint", lambda uuid: f"drive_path::{uuid}")

    route = _recheck_route(catalog, holding)

    assert route is not None
    assert str(library) in route, f"the route names a drive the sentence excluded: {route}"
    assert str(external) not in route


def test_a_genuinely_unchecked_drive_is_still_offered(monkeypatch, tmp_path) -> None:
    """The anti-vacuity anchor: the fix must not make the route silent. A drive nobody has looked
    at is exactly what this line is for."""
    library = tmp_path / "Library"
    library.mkdir()
    monkeypatch.setattr(cli, "drive_reach", lambda _hint, _uuid: cli.DriveReach.CONNECTED)
    monkeypatch.setattr(cli, "drive_path_hint", lambda uuid: f"drive_path::{uuid}")

    holding = [_drive("u-lib", "Library", last_verified=None, checked=0)]
    route = _recheck_route(_Catalog({"drive_path::u-lib": str(library)}), holding)

    assert route is not None
    assert str(library) in route


def test_with_nothing_unchecked_the_route_falls_to_the_oldest(monkeypatch, tmp_path) -> None:
    """When every place carries a date the route is about the stalest one, unchanged by the fix."""
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    monkeypatch.setattr(cli, "drive_reach", lambda _hint, _uuid: cli.DriveReach.CONNECTED)
    monkeypatch.setattr(cli, "drive_path_hint", lambda uuid: f"drive_path::{uuid}")

    holding = [
        _drive("u-new", "New", last_verified="2026-09-01T00:00:00+00:00", checked=1),
        _drive("u-old", "Old", last_verified="2026-01-01T00:00:00+00:00", checked=1),
    ]
    route = _recheck_route(
        _Catalog({"drive_path::u-old": str(old), "drive_path::u-new": str(new)}), holding
    )

    assert route is not None
    assert str(old) in route
