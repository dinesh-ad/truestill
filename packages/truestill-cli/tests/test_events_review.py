"""Event review stage: naming applies, catalog remembers names and skips (idempotent)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from truestill_cli.events_review import run_event_stage
from truestill_core.catalog import Catalog
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.events import EventCandidate
from truestill_core.models import DateSource, Decision, FileHashes, Resolution


def _camera(i: int, when: datetime) -> Resolution:
    category = CategoryMatch(
        label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device"
    )
    decision = Decision(
        source=Path(f"/src/img{i}.jpg"),
        category=category,
        captured_at=when,
        date_source=DateSource.EXIF,
        date_tag="DateTimeOriginal",
        relative=Path(f"Camera/{when:%Y}/{when:%m}/img{i}.jpg"),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=f"sha{i:04d}", perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def _one_cluster() -> list[Resolution]:
    base = datetime(2026, 6, 14, 9, 0)
    return [_camera(i, base + timedelta(minutes=20 * i)) for i in range(10)]  # 10 files, 3h


def _boom(_cluster: EventCandidate) -> str | None:
    pytest.fail("prompt should not be called")


def test_naming_applies_and_is_remembered(tmp_path: Path) -> None:
    resolutions = _one_cluster()
    db = tmp_path / "c.sqlite"

    with Catalog(db) as catalog:
        updated, events = run_event_stage(
            resolutions, {}, catalog, apply=True, prompt=lambda _c: "Goa Trip"
        )
        assert len(events) == 10
        assert all(
            r.decision.relative.as_posix().startswith("2026/2026-06/2026-06-14 - Goa Trip/")
            for r in updated
        )

    # second run: same cluster signature -> reuse name from catalog, never prompt again
    with Catalog(db) as catalog:
        updated2, events2 = run_event_stage(resolutions, {}, catalog, apply=True, prompt=_boom)
        assert len(events2) == 10
        assert all("2026-06-14 - Goa Trip" in r.decision.relative.as_posix() for r in updated2)


def test_skip_is_remembered_and_not_reasked(tmp_path: Path) -> None:
    resolutions = _one_cluster()
    db = tmp_path / "c.sqlite"

    with Catalog(db) as catalog:
        updated, events = run_event_stage(
            resolutions, {}, catalog, apply=True, prompt=lambda _c: None
        )
        assert events == {}
        # paths unchanged -- cluster left flat
        assert all("2026-06-14 - Goa Trip" not in r.decision.relative.as_posix() for r in updated)

    with Catalog(db) as catalog:
        _, events2 = run_event_stage(resolutions, {}, catalog, apply=True, prompt=_boom)
        assert events2 == {}  # skip remembered, prompt not called


def test_dry_run_does_not_prompt_or_mutate(tmp_path: Path) -> None:
    resolutions = _one_cluster()
    with Catalog(tmp_path / "c.sqlite") as catalog:
        updated, events = run_event_stage(resolutions, {}, catalog, apply=False, prompt=_boom)
    assert events == {}
    assert updated == resolutions  # untouched in dry run
