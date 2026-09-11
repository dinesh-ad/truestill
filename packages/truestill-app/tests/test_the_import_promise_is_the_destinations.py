"""Import promises what will land in THIS destination. `DECISIONS.md` D14 and D17.

⚠ **THE DEFECT, MEASURED BEFORE IT WAS FIXED.** `service/takeout.py:ingest_preview` accepted
`destination` and did not use it - the parameter carried `# noqa: ARG001 - kept for API symmetry`
- so it resolved catalog-globally and reported the **library's** answer under the promise's name.
On a two-drive fixture a fresh second drive was told `kept: 0, dup_collapsed: 6` while
`truestill ingest` copied all six into it. That is defect **D2** of `handoff-2026-09-05.md`,
*"no second copy"*, on a third surface.

⚠ **AND NOT THE ONE-ARGUMENT FIX.** That record measured scoping the single `resolve` and rejects
it by name: it makes the promise true and empties the naming, reddening four cases of
`test_the_preview_names_the_drive.py`. The pass stays catalog-global and `promise_view` re-judges
it - one pass, two answers - so `kept` is the destination's and `already_in_library` is the
library's, and both are true at once.

**The CLI is the reference, and it was run rather than read.** `_run_pipeline` has always passed
`on_destination`; six photographs ingested into Drive A and then the same source into a fresh
Drive B reported `skipped (exact dup): 0` and Drive B received all six.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PIL import Image
from truestill_app import service
from truestill_app.service.takeout import ingest_preview, ingest_preview_run
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker


def _photo(path: Path, seed: int) -> None:
    image = Image.new("RGB", (48, 48))
    pixels = image.load()
    assert pixels is not None
    for x in range(48):
        for y in range(48):
            pixels[x, y] = ((x * 7 + seed * 53) % 256, (y * 11 + seed) % 256, (x + y + seed) % 256)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def takeout_and_drives(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """A Takeout-shaped source, a drive that already holds it, and a fresh one that does not."""
    source = tmp_path / "Takeout" / "Photos from 2014"
    for index in range(4):
        _photo(source / f"img{index}.jpg", seed=index)
    db = tmp_path / "c.sqlite"
    held, fresh = tmp_path / "Held", tmp_path / "Fresh"
    held.mkdir()
    fresh.mkdir()
    marker = create_marker(held, label="Held")
    create_marker(fresh, label="Fresh")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
    return tmp_path / "Takeout", held, fresh, db


def _preview(takeout: Path, destination: Path, db: Path) -> dict[str, object]:
    return ingest_preview(  # type: ignore[return-value]
        takeout, destination, db, progress=lambda _p: None, cancel=threading.Event()
    )


def _organize_into(source: Path, destination: Path, db: Path) -> None:
    """Really organize, so the catalog holds them on that drive - never a hand-written row."""
    service.organize_run(source, destination, db)(lambda _p: None, threading.Event())


# ------------------------------------------------------------------ the promise, per destination


def test_a_fresh_destination_is_promised_the_files_it_will_receive(
    takeout_and_drives: tuple[Path, Path, Path, Path],
) -> None:
    """⚠ **THE DEFECT.** Told `kept: 0` for a drive that would receive every one of them."""
    takeout, held, fresh, db = takeout_and_drives
    _organize_into(takeout, held, db)

    answer = _preview(takeout, fresh, db)

    assert answer["kept"] == 4, "a fresh destination was promised files it will not receive"
    assert answer["dup_collapsed"] == 0


def test_a_destination_that_already_holds_them_collapses_them(
    takeout_and_drives: tuple[Path, Path, Path, Path],
) -> None:
    """⚠ **The half that makes the test above mean something.** A promise that said "everything
    will be written" everywhere would satisfy it and be just as wrong."""
    takeout, held, _fresh, db = takeout_and_drives
    _organize_into(takeout, held, db)

    answer = _preview(takeout, held, db)

    assert answer["kept"] == 0
    assert answer["dup_collapsed"] == 4


def test_the_library_s_answer_survives_the_scoping(
    takeout_and_drives: tuple[Path, Path, Path, Path],
) -> None:
    """⚠ **THE HALF THE ONE-ARGUMENT FIX DESTROYED**, and the reason the pass stays global.

    `handoff-2026-09-05.md:78` measured scoping the single `resolve` and rejects it: the promise
    becomes true and the naming empties. Here both are true of the same fresh drive - the library
    holds all four, and all four are still going to be written into it.
    """
    takeout, held, fresh, db = takeout_and_drives
    _organize_into(takeout, held, db)

    answer = _preview(takeout, fresh, db)

    assert answer["already_in_library"] == 4
    assert answer["kept"] == 4


def test_an_untouched_catalog_promises_everything_and_names_nothing(
    takeout_and_drives: tuple[Path, Path, Path, Path],
) -> None:
    """The cry-wolf half of the test above: `already_in_library` must not be a constant."""
    takeout, _held, fresh, db = takeout_and_drives

    answer = _preview(takeout, fresh, db)

    assert answer["kept"] == 4
    assert answer["already_in_library"] == 0


# ------------------------------------------------------------------------ both previews, not one


def test_scoping_reached_the_job_form_too(
    takeout_and_drives: tuple[Path, Path, Path, Path],
) -> None:
    """⚠ **`(akg)` names splitting them as the risk**: *"On Import the preview and the run agree
    with each other, so no promise is broken."* They must still agree after the fix, and they do
    because `ingest_preview_run` delegates rather than repeating the work - asserted here so a
    future edit that duplicates the body cannot silently scope only one.
    """
    takeout, held, fresh, db = takeout_and_drives
    _organize_into(takeout, held, db)

    direct = _preview(takeout, fresh, db)
    job = ingest_preview_run(takeout, fresh, db)(lambda _p: None, threading.Event())

    assert job["kept"] == direct["kept"] == 4  # type: ignore[index]
    assert job["already_in_library"] == direct["already_in_library"] == 4  # type: ignore[index]


def test_the_tally_still_adds_up(
    takeout_and_drives: tuple[Path, Path, Path, Path],
) -> None:
    """`files == kept + dup_collapsed + unreadable` is the disjointness the payload documents,
    and re-judging must not break it - the promise re-buckets every resolution, not some."""
    takeout, held, fresh, db = takeout_and_drives
    _organize_into(takeout, held, db)

    for destination in (fresh, held):
        answer = _preview(takeout, destination, db)
        total = answer["kept"] + answer["dup_collapsed"] + answer["unreadable"]  # type: ignore[operator]
        assert total == answer["files"], destination
