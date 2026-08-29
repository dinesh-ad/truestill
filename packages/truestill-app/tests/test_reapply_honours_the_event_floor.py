"""`_reapply_named_events`, tested directly for the first time. `(ahv)` stage 1.

Until 2026-08-29 this function had no test of its own - only `organize_run`'s tests reached it,
and that coverage could never catch the defect fixed here: `propose` hard-defaulted
``min_files=8``, so a user who lowered ``events.min_files`` and named a six-file event had it
**silently skipped on every re-import** - `_reapply_named_events` returns its input unchanged
when nothing proposes, which at the call site is indistinguishable from "no events recur in
this source". A call-site test with default settings and default-sized fixtures passes forever
over that skip; only a catalog holding the lowered floor and an event *below the default* can
see it, and that is exactly what this file constructs.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from truestill_app.service.organize import _reapply_named_events
from truestill_core.catalog_session import open_catalog
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.events import EVENT_MIN_FILES_KEY
from truestill_core.layout import DEFAULT_SCHEME
from truestill_core.models import (
    DateSource,
    Decision,
    FileHashes,
    Resolution,
    RuleName,
)

_START = datetime(2019, 7, 12, 10, 30)


def _camera_resolutions(count: int) -> list[Resolution]:
    """Dated camera-rule files, hashes present so nothing touches the filesystem."""
    resolutions = []
    for i in range(count):
        when = _START + timedelta(minutes=i)
        decision = Decision(
            source=Path(f"/src/IMG_{i:04d}.jpg"),
            category=CategoryMatch(
                label="Camera", reason="t", confidence=Confidence.MEDIUM, rule=RuleName.DEVICE
            ),
            captured_at=when,
            date_source=DateSource.EXIF,
            date_tag=None,
            relative=Path(f"Camera/{when:%Y}/{when:%m}/IMG_{i:04d}.jpg"),
        )
        resolutions.append(
            Resolution(
                decision=decision,
                hashes=FileHashes(sha256=f"sha-{i:04d}", perceptual=None),
                exact_duplicate=None,
                near_duplicate=None,
            )
        )
    return resolutions


def _signature(resolutions: list[Resolution]) -> str:
    joined = "\n".join(sorted(r.hashes.sha256 for r in resolutions))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def test_a_named_event_below_the_default_floor_reapplies(tmp_path: Path) -> None:
    """The defect, directly: floor lowered to 5, a named 6-file event, a fresh import.

    Before the fix the propose ran at the hard default of 8, the 6-file cluster never
    existed, and the event silently failed to reapply. Mutation proof: hard-code 8 back
    into `_reapply_named_events`' propose call and this dies.
    """
    resolutions = _camera_resolutions(6)
    with open_catalog(tmp_path / "catalog.sqlite") as catalog:
        catalog.set_setting(EVENT_MIN_FILES_KEY, "5")
        catalog.record_event(
            name="Morning Market",
            slug="morning-market",
            start_date=_START.date().isoformat(),
            file_count=6,
            signature=_signature(resolutions),
        )

        result = _reapply_named_events(resolutions, {}, catalog, DEFAULT_SCHEME)

    placed = [r for r in result if "Morning Market" in str(r.decision.relative)]
    assert len(placed) == 6, [str(r.decision.relative) for r in result]


def test_an_unnamed_cluster_is_left_reviewable_not_skipped(tmp_path: Path) -> None:
    """The function's other promise, pinned while a direct test finally exists: a cluster
    the catalog has never named is returned untouched - reviewable later, never auto-skipped.
    """
    resolutions = _camera_resolutions(6)
    with open_catalog(tmp_path / "catalog.sqlite") as catalog:
        catalog.set_setting(EVENT_MIN_FILES_KEY, "5")

        result = _reapply_named_events(resolutions, {}, catalog, DEFAULT_SCHEME)

        assert [str(r.decision.relative) for r in result] == [
            str(r.decision.relative) for r in resolutions
        ]
        assert not catalog.skipped_signatures()
