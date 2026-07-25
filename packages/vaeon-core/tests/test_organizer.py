"""End-to-end: plan -> resolve -> execute against a local destination, with dedup."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from vaeon_core.catalog import Catalog
from vaeon_core.categorize import CategoryMatch, Confidence
from vaeon_core.dedup import DedupIndex
from vaeon_core.destinations import LocalDestination
from vaeon_core.exif import read_metadata
from vaeon_core.hashing import sha256_file
from vaeon_core.models import (
    ActionStatus,
    DateSource,
    Decision,
    DuplicateKind,
    FileHashes,
    Resolution,
)
from vaeon_core.organizer import apply_events, discover, execute, plan, resolve, scan_source


def test_scan_source_partitions_media_documents_and_unrecognized(tmp_path: Path) -> None:
    for name in ("a.jpg", "b.MP4", "notes.pdf", "clip.vob", "movie.ogv", "weird.xyz"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / ".hidden.jpg").write_bytes(b"x")  # hidden -> skipped entirely

    scan = scan_source(tmp_path)
    assert sorted(p.name for p in scan.media) == [
        "a.jpg",
        "b.MP4",
    ]  # recognized media (case-insensitive)
    assert sorted(p.name for p in scan.documents) == ["notes.pdf"]
    assert sorted(p.name for p in scan.unrecognized) == ["clip.vob", "movie.ogv", "weird.xyz"]


def test_scan_source_all_files_treats_everything_as_media(tmp_path: Path) -> None:
    (tmp_path / "notes.pdf").write_bytes(b"x")
    (tmp_path / "clip.vob").write_bytes(b"x")
    scan = scan_source(tmp_path, all_files=True)
    assert len(scan.media) == 2
    assert scan.documents == []
    assert scan.unrecognized == []


def _camera_resolution(source: str, when: datetime, sha: str) -> Resolution:
    category = CategoryMatch(
        label="Camera", reason="test", confidence=Confidence.MEDIUM, rule="device"
    )
    decision = Decision(
        source=Path(source),
        category=category,
        captured_at=when,
        date_source=DateSource.EXIF,
        date_tag="DateTimeOriginal",
        relative=Path(f"Camera/{when:%Y}/{when:%m}/{Path(source).name}"),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=sha, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def _resolution(source: Path, when: datetime | None, sha: str) -> Resolution:
    category = CategoryMatch(
        label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device"
    )
    rel = (
        Path(f"Camera/Undated/{source.name}")
        if when is None
        else Path(f"Camera/{when:%Y}/{when:%m}/{source.name}")
    )
    decision = Decision(
        source=source,
        category=category,
        captured_at=when,
        date_source=DateSource.NONE if when is None else DateSource.EXIF,
        date_tag=None,
        relative=rel,
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=sha, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def test_skip_undated_skips_only_undated_files(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "dated.jpg").write_bytes(b"dated-bytes")
    (src / "undated.jpg").write_bytes(b"undated-bytes")
    dated = _resolution(src / "dated.jpg", datetime(2023, 1, 1), "sha-dated")
    undated = _resolution(src / "undated.jpg", None, "sha-undated")
    out = tmp_path / "out"

    results = execute([dated, undated], LocalDestination(out), apply=True, skip_undated=True)
    by = {r.resolution.decision.source.name: r for r in results}
    assert by["undated.jpg"].status is ActionStatus.SKIPPED_UNDATED
    assert by["dated.jpg"].status is ActionStatus.UPLOADED

    written = LocalDestination(out).list()
    assert any("dated.jpg" in w for w in written)  # the dated file was copied
    assert not any("undated" in w for w in written)  # the undated file was NOT written

    # Default (flag off): the undated file goes to Undated/ as before.
    out2 = tmp_path / "out2"
    execute([undated], LocalDestination(out2), apply=True)
    assert any("Undated" in w for w in LocalDestination(out2).list())


class _BadVerifyDestination(LocalDestination):
    """Uploads normally but reports a wrong checksum, to force a move re-verify failure."""

    def checksum(self, relative_path: str) -> str:  # noqa: ARG002
        return "0" * 64


def test_move_deletes_source_after_verified_copy(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    photo = src / "a.jpg"
    photo.write_bytes(b"real-content")
    res = _resolution(photo, datetime(2023, 1, 1), sha256_file(photo))
    out = tmp_path / "out"

    results = execute([res], LocalDestination(out), apply=True, move=True)
    assert results[0].status is ActionStatus.MOVED
    assert not photo.exists()  # source deleted only after the copy verified
    assert LocalDestination(out).list()  # copy is at the destination


def test_move_keeps_source_when_verify_fails(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    photo = src / "a.jpg"
    photo.write_bytes(b"real-content")
    res = _resolution(photo, datetime(2023, 1, 1), sha256_file(photo))
    out = tmp_path / "out"

    results = execute([res], _BadVerifyDestination(out), apply=True, move=True)
    assert results[0].status is ActionStatus.MOVE_KEPT
    assert photo.exists()  # verify failed -> source is NEVER deleted (still in both places)


def test_apply_events_consolidates_cross_month_under_start_month() -> None:
    """An event spanning June 30 -> July 2 lands wholly under the start month (June)."""
    r_jun = _camera_resolution("/src/a.jpg", datetime(2026, 6, 30, 23, 0), "sha-a")
    r_jul = _camera_resolution("/src/b.jpg", datetime(2026, 7, 2, 10, 0), "sha-b")
    start = datetime(2026, 6, 30, 23, 0)
    # Key by str(source) exactly as apply_events looks them up, so the test is not sensitive
    # to how Path stringifies the source on the host OS.
    assignments = {
        str(r_jun.decision.source): (start, "goa-trip"),
        str(r_jul.decision.source): (start, "goa-trip"),
    }

    updated = apply_events([r_jun, r_jul], assignments)
    relatives = {r.decision.relative.as_posix() for r in updated}
    assert relatives == {
        "Camera/2026/06/20260630_goa-trip/a.jpg",
        "Camera/2026/06/20260630_goa-trip/b.jpg",  # July file consolidated under June
    }


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
