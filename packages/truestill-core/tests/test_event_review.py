"""Core event-review orchestration: naming, catalog reuse, skip memory, preview no-op."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.event_review import (
    EventDecision,
    EventStageOutcome,
    commit,
    propose,
    run_event_stage,
)
from truestill_core.events import EventCandidate, merge_candidates
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
    return Resolution(decision, FileHashes(f"sha{i:04d}", None), None, None)


def _one_cluster() -> list[Resolution]:
    base = datetime(2026, 6, 14, 9, 0)
    return [_camera(i, base + timedelta(minutes=20 * i)) for i in range(10)]


def _boom(_cluster: EventCandidate) -> str | None:
    pytest.fail("prompt should not be called")


def test_preview_returns_clusters_without_naming(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        out = run_event_stage(_one_cluster(), {}, catalog, apply=False, prompt=_boom)
    assert isinstance(out, EventStageOutcome)
    assert len(out.clusters) == 1  # proposed
    assert out.events == {}  # but nothing named
    assert all("goa" not in r.decision.relative.as_posix() for r in out.resolutions)


def test_apply_names_and_places(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        out = run_event_stage(_one_cluster(), {}, catalog, apply=True, prompt=lambda _c: "Goa Trip")
    assert len(out.events) == 10
    assert all(
        r.decision.relative.as_posix().startswith("2026/2026-06/2026-06-14 - Goa Trip/")
        for r in out.resolutions
    )


def test_merge_then_commit_places_all_under_one_event(tmp_path: Path) -> None:
    """The UI path: propose -> merge two clusters -> commit with one name."""
    base = datetime(2026, 6, 14, 9, 0)
    week2 = datetime(2026, 6, 21, 9, 0)  # 7 days later -> a second cluster
    resolutions = [_camera(i, base + timedelta(minutes=20 * i)) for i in range(10)]
    resolutions += [_camera(20 + i, week2 + timedelta(minutes=20 * i)) for i in range(10)]

    with Catalog(tmp_path / "c.sqlite") as catalog:
        clusters = propose(resolutions, {}, min_files=8)
        assert len(clusters) == 2  # two separate proposals
        merged = merge_candidates(clusters)
        out = commit(resolutions, [EventDecision(merged, "Summer")], catalog)

    assert len(out.events) == 20  # all files belong to the one merged event
    assert all(
        r.decision.relative.as_posix().startswith("2026/2026-06/2026-06-14 - Summer/")
        for r in out.resolutions
    )


def test_catalog_reuse_and_skip_memory(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        run_event_stage(_one_cluster(), {}, catalog, apply=True, prompt=lambda _c: "Goa Trip")
    with Catalog(db) as catalog:  # same signature -> reused, prompt never called
        out = run_event_stage(_one_cluster(), {}, catalog, apply=True, prompt=_boom)
    assert len(out.events) == 10
