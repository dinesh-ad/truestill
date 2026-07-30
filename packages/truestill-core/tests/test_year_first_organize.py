"""The scheme, reached by a real run - not only by a preview.

The design audit found that `LayoutScheme` was unreachable from any production path: `plan` and
`apply_events` took an *optional* scheme, no caller passed one, and every file therefore rendered
through a bare template. Routing-on-rule and readable event folders existed, were tested, and
never executed. These tests assert the on-disk tree a run actually produces, which is the thing
a preview cannot prove.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_core.catalog import Catalog
from truestill_core.categorize import build_rules
from truestill_core.destinations import LocalDestination
from truestill_core.exif import read_metadata
from truestill_core.layout import (
    DEFAULT_SCHEME,
    PRESETS,
    LayoutScheme,
    Placement,
    preview_scheme,
)
from truestill_core.migrate import label_routes, plan_migration
from truestill_core.models import Event, FileHashes, Resolution
from truestill_core.organizer import apply_events, execute, plan

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")

YEAR_FIRST = PRESETS["year-month-event"].scheme()


def _camera_photo(path: Path, when: str = "2014:08:20 14:30:00") -> Path:
    """A JPEG that really carries camera EXIF, so the `device` rule fires for it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 32), (10, 120, 200)).save(path, "JPEG")
    subprocess.run(
        [
            "exiftool",
            "-q",
            "-m",
            "-overwrite_original",
            f"-DateTimeOriginal={when}",
            "-Make=Samsung",
            "-Model=SM-A546B",
            str(path),
        ],
        check=False,
    )
    return path


def _screenshot(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 40), (5, 5, 5)).save(path, "JPEG")
    return path


def _organize(tmp_path: Path, scheme: LayoutScheme, files: list[Path]) -> list[str]:
    """Run the real pipeline and return the relative paths that actually landed on disk."""
    destination = tmp_path / "out"
    metadata = read_metadata(files)
    decisions = plan(files, metadata, build_rules(), scheme=scheme)
    resolutions = [
        Resolution(
            decision=d,
            hashes=FileHashes(sha256=f"sha-{i}", perceptual=None),
            exact_duplicate=None,
            near_duplicate=None,
        )
        for i, d in enumerate(decisions)
    ]
    execute(resolutions, LocalDestination(destination), apply=True, catalog=None)
    return sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*.jpg"))


def test_a_real_run_routes_camera_to_the_timeline_and_the_rest_to_side_bins(
    tmp_path: Path,
) -> None:
    """The capability the audit found switched off, asserted against the filesystem."""
    source = tmp_path / "src"
    photo = _camera_photo(source / "IMG_0001.jpg")
    shot = _screenshot(source / "Screenshot_20240115_101500.jpg")

    placed = _organize(tmp_path, YEAR_FIRST, [photo, shot])

    assert placed == [
        # camera -> timeline, no category folder, ordinary photos in the Everyday bucket
        "2014/2014-08/2014-08 - Everyday/20140820_143000_IMG_0001.jpg",
        "Screenshots/2024/2024-01/Screenshot_20240115_101500.jpg",  # -> side bin, not double-dated
    ]


def test_a_real_run_writes_readable_event_folders(tmp_path: Path) -> None:
    """`2014-08-20 - Goa Trip`, on disk. Previously this rendered only in the preview."""
    source = tmp_path / "src"
    photos = [_camera_photo(source / f"IMG_{i:04d}.jpg") for i in range(2)]
    metadata = read_metadata(photos)
    decisions = plan(photos, metadata, build_rules(), scheme=YEAR_FIRST)
    resolutions = [
        Resolution(
            decision=d,
            hashes=FileHashes(sha256=f"sha-{i}", perceptual=None),
            exact_duplicate=None,
            near_duplicate=None,
        )
        for i, d in enumerate(decisions)
    ]

    start = datetime(2014, 8, 20)
    events = {str(p): Event(start=start, slug="goa-trip", name="Goa Trip", id=1) for p in photos}
    routed = apply_events(resolutions, events, scheme=YEAR_FIRST)

    destination = tmp_path / "out"
    execute(routed, LocalDestination(destination), apply=True, catalog=None)

    landed = sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*.jpg"))
    assert all(p.startswith("2014/2014-08/2014-08-20 - Goa Trip/") for p in landed), landed


@pytest.mark.parametrize("preset_key", list(PRESETS))
def test_a_run_and_a_preview_of_the_same_layout_agree(tmp_path: Path, preset_key: str) -> None:
    """One resolution path, one render path -- so a plan a user approved is the plan that runs.

    The audit's F1 was exactly this divergence: the preview rendered through a scheme while runs
    rendered through a bare template, and the two agreed only by accident.
    Parametrized across every shipped preset.
    """
    scheme = PRESETS[preset_key].scheme()
    source = tmp_path / "src"
    photo = _camera_photo(source / "IMG_0001.jpg")

    previewed = {
        row.description: rendered.path.parent.as_posix() for row, rendered in preview_scheme(scheme)
    }
    placed = _organize(tmp_path, scheme, [photo])

    assert Path(placed[0]).parent.as_posix() == previewed["Camera"]


def test_the_default_is_the_year_first_preset() -> None:
    """The default is a year-first scheme.

    Its two timeline shapes differ (events keep the month as their parent, ordinary photos go
    to `Everyday`), which is why the default cannot be rebuilt from a single stored string.
    """
    assert PRESETS["year-month-event"].scheme() == DEFAULT_SCHEME
    assert (
        DEFAULT_SCHEME.template_for(Placement.SIDE_BIN).template == "{category}/{yyyy}/{yyyy}-{mm}"
    )
    assert (
        DEFAULT_SCHEME.template_for(Placement.EVERYDAY).template
        != DEFAULT_SCHEME.template_for(Placement.EVENT_DAY).template
    )


def test_a_migration_and_an_organize_run_agree_under_the_same_layout(tmp_path: Path) -> None:
    """Closes the audit's F2: migrate rendered through a bare template and could not route.

    A library that was migrated and a library that was organized fresh must be the same tree,
    or "adopt the new layout" would mean something different depending on which door you came
    through.
    """
    source = tmp_path / "src"
    photo = _camera_photo(source / "IMG_0001.jpg")
    organized = _organize(tmp_path, YEAR_FIRST, [photo])

    # The same file, recorded as a legacy-layout copy on a drive, then re-planned.
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive")
        catalog.record_uploaded(
            source_path=str(photo),
            original_name="IMG_0001.jpg",
            sha256="sha-1",
            copy_sha256="sha-1",
            perceptual=None,
            size=10,
            captured_at="2014-08-20T14:30:00",
            category="Camera",
            relative="Camera/2014/08/20140820_143000_IMG_0001.jpg",
            event_id=None,
            albums=[],
            drive_uuid="D1",
        )
        routes = {r.label: "timeline" for r in label_routes(catalog, "D1")}
        plan = plan_migration(catalog, "D1", YEAR_FIRST, routes=routes)

    assert [m.new_relative for m in plan.moves] == organized
