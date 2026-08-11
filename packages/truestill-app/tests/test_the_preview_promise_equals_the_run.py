"""What the preview promises must equal what the run organizes - `(abl)` and `(acx)`.

**This assertion existed nowhere before 2026-08-11**, which is why both defects survived. The
suite had conservation (`new_unique + near_dup + exact_dup + unreadable == files`) and
disjointness, and those hold happily while the number a person reads is the wrong one: they check
that the parts sum, never that the promised part is the part the run takes.

The nearest existing pair is `test_overlapping_organize_runs.py`, where one test asserts the run
organized 3 and another asserts the preview said `new_unique == 3`. They agree only because that
fixture has `near_dup == 0`, and its own docstring says so. Nothing linked them.

**Two defects, opposite directions, one invariant:**

* `(abl)` - the tally row said *"will be organized"* over `new_unique`, while the run also
  organizes near-duplicates. It **understated**.
* `(acx)` - the preview endpoint never accepted `skip_undated`, which its own run endpoint did, so
  with that box ticked the confirm control **overstated** by the undated count. A preview that
  promises more than the run delivers is the worse of the two, and it was the unfiled one.

Pinning the invariant rather than either symptom is the point: a fix that traded one direction for
the other would satisfy two separate tests and fail this one.

**The comparison is not circular.** `will_organize` comes from `ReportBuckets.will_organize`, and
the run's count comes from `_completion`, which tallies `ActionStatus` values after the copies
happened. Different code paths, one of which touches the filesystem.
"""

from __future__ import annotations

import random
import threading
from pathlib import Path
from typing import Any

from PIL import Image
from truestill_app.service import organize_preview, organize_run


def _photo(path: Path, seed: int, *, quality: int = 95) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=quality)


def _library_with_a_look_alike(root: Path) -> Path:
    """Two distinct photos plus a recompressed copy of one of them.

    The recompressed file is a PERCEPTUAL near-duplicate: different bytes, same image, so the run
    keeps it (`should_upload` is True, `ActionStatus.UPLOADED`) and flags it. That is the file
    `(abl)`'s row excluded from its own promise, so the fixture must contain one or the test
    cannot see the defect.
    """
    source = root / "source"
    _photo(source / "one.jpg", 1)
    _photo(source / "two.jpg", 2)
    _photo(source / "one_again.jpg", 1, quality=40)
    return source


def _preview(source: Path, destination: Path, db: Path, *, skip_undated: bool = False) -> Any:
    return organize_preview(source, destination, db, skip_undated=skip_undated)


def _run(source: Path, destination: Path, db: Path, *, skip_undated: bool = False) -> Any:
    target = organize_run(source, destination, db, skip_undated=skip_undated)
    return target(lambda _p: None, threading.Event())


def test_the_preview_promises_exactly_what_the_run_organizes(tmp_path: Path) -> None:
    """`(abl)`: the understating direction, on a folder with a look-alike in it.

    Before the fix the preview's promise was `new_unique`, which is 2 here while the run organizes
    3 - the shape the entry measured on eight real photos from one event.
    """
    source = _library_with_a_look_alike(tmp_path)
    preview = _preview(source, tmp_path / "out", tmp_path / "c.sqlite")

    # The fixture must actually contain the thing under test, or this passes for the wrong reason.
    assert preview["near_dup"] >= 1, f"no look-alike in the fixture: {preview['near_dup']}"

    done = _run(source, tmp_path / "out", tmp_path / "c.sqlite")
    assert preview["will_organize"] == done["organized"], (
        f"the preview promised {preview['will_organize']} and the run organized "
        f"{done['organized']} - a preview is a promise about what is about to happen"
    )


def test_the_promise_falls_when_undated_files_are_skipped(tmp_path: Path) -> None:
    """`(acx)`: the OVERSTATING direction, which is the worse one.

    The preview endpoint did not accept `skip_undated` at all while the run did, so the confirm
    control promised files the run then skipped. A preview that promises more than the run
    delivers is worse than one that promises less: the user consents to an operation larger than
    the one they were shown.
    """
    source = tmp_path / "source"
    _photo(source / "dated.jpg", 3)
    _photo(source / "undated.jpg", 4)
    db = tmp_path / "c.sqlite"

    # Both files carry no EXIF date - PIL writes none - so skipping must drop the whole set.
    plain = _preview(source, tmp_path / "out", db)
    assert plain["undated"] >= 1, f"the fixture has no undated file: {plain['undated']}"

    skipping = _preview(source, tmp_path / "out2", db, skip_undated=True)
    assert skipping["will_organize"] == plain["will_organize"] - plain["undated"], (
        "skipping undated files must lower the promise by exactly the undated count"
    )

    done = _run(source, tmp_path / "out2", db, skip_undated=True)
    assert skipping["will_organize"] == done["organized"], (
        f"with skip-undated the preview promised {skipping['will_organize']} and the run "
        f"organized {done['organized']}"
    )


def test_the_promise_is_one_number_not_two(tmp_path: Path) -> None:
    """The card and the confirm control must render the SAME field.

    They disagreed by `near_dup` for weeks because each computed its own answer - the card
    `new_unique`, the control `new_unique + near_dup`. This asserts the payload carries one
    number rather than leaving both surfaces to derive one, which is what makes the browser-side
    assertion trivial instead of arithmetic.
    """
    source = _library_with_a_look_alike(tmp_path)
    preview = _preview(source, tmp_path / "out", tmp_path / "c.sqlite")

    assert "will_organize" in preview, "the payload must state the promise rather than imply it"
    assert preview["will_organize"] == preview["new_unique"] + preview["near_dup"], (
        "with nothing skipped the promise is the organized set; if this ever needs a second "
        "expression to compute, the two surfaces have started deriving it again"
    )
