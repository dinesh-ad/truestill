"""End-to-end: plan -> resolve -> execute against a local destination, with dedup."""

from __future__ import annotations

import shutil
from pathlib import Path

from vaeon_core.catalog import Catalog
from vaeon_core.dedup import DedupIndex
from vaeon_core.destinations import LocalDestination
from vaeon_core.exif import read_metadata
from vaeon_core.models import ActionStatus, DuplicateKind
from vaeon_core.organizer import discover, execute, plan, resolve


def _run(source: Path, out: Path, db: Path, *, apply: bool) -> list:
    files = discover(source)
    metadata = read_metadata(files)
    decisions = plan(files, metadata)
    with Catalog(db) as catalog:
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), threshold=10)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
        results = execute(resolutions, LocalDestination(out), catalog, apply=apply)
    return list(zip(resolutions, results, strict=True))


def test_exact_skipped_but_near_dup_kept_and_flagged(
    tmp_path: Path,
    gradient_png: Path,
    gradient_jpeg_recompressed: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    # a unique image, an exact copy of it, and a recompressed (perceptual) copy
    shutil.copy(gradient_png, source / "original.png")
    shutil.copy(gradient_png, source / "exact_copy.png")
    shutil.copy(gradient_jpeg_recompressed, source / "recompressed.jpg")

    paired = _run(source, tmp_path / "out", tmp_path / "c.sqlite", apply=True)
    by_name = {res.decision.source.name: (res, act) for res, act in paired}

    # original.png and exact_copy.png are byte-identical: exactly one is kept, the other is
    # an EXACT duplicate and skipped. Which one is discovery-order dependent, so don't pin it.
    png_pair = [by_name["original.png"], by_name["exact_copy.png"]]
    kept = [(res, act) for res, act in png_pair if res.should_upload]
    skipped = [(res, act) for res, act in png_pair if not res.should_upload]
    assert len(kept) == 1
    assert len(skipped) == 1
    assert kept[0][1].status is ActionStatus.UPLOADED
    assert skipped[0][0].exact_duplicate is not None
    assert skipped[0][0].exact_duplicate.kind is DuplicateKind.EXACT
    assert skipped[0][1].status is ActionStatus.DUPLICATE

    # recompressed.jpg is a PERCEPTUAL near-dup -> uploaded anyway (keep-both), only flagged
    perc_res, perc_act = by_name["recompressed.jpg"]
    assert perc_res.should_upload is True
    assert perc_res.near_duplicate is not None
    assert perc_res.near_duplicate.kind is DuplicateKind.PERCEPTUAL
    assert perc_act.status is ActionStatus.UPLOADED

    # both the kept PNG and the near-dup JPEG reached the destination; only the exact dup didn't
    assert len(LocalDestination(tmp_path / "out").list()) == 2


def test_rerun_recognises_catalog_and_skips(tmp_path: Path, gradient_png: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(gradient_png, source / "photo.png")
    out = tmp_path / "out"
    db = tmp_path / "c.sqlite"

    first = _run(source, out, db, apply=True)
    assert first[0][1].status is ActionStatus.UPLOADED

    # second run: the catalog now knows this file (identical bytes), so it is an EXACT
    # duplicate from a prior run and is not re-uploaded
    second = _run(source, out, db, apply=True)
    res, act = second[0]
    assert res.exact_duplicate is not None
    assert res.exact_duplicate.origin == "catalog"
    assert act.status is ActionStatus.DUPLICATE


def test_dry_run_writes_nothing(tmp_path: Path, gradient_png: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(gradient_png, source / "photo.png")
    out = tmp_path / "out"

    paired = _run(source, out, tmp_path / "c.sqlite", apply=False)
    assert paired[0][1].status is ActionStatus.PLANNED
    assert not out.exists()
