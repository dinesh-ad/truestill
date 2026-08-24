"""The app's undo job honours the cancel it is handed, rather than discarding it. `(agl)`

⚠ **THIS IS THE WIRING HALF, AND IT IS WHERE THE DEFECT LIVED.** `truestill_core.undo.run_undo`
could not be cancelled at all - it was the only long-running core entry point without a `cancel`
parameter, while `execute`, `extract_archive_set`, `run_migration`, `undo_migration`,
`verify_copies` and `compute_hashes` all had one. The app's target took the event and named it
``_cancel``: the leading underscore says *deliberately discarded*, and it was hiding a live
capability rather than an unused argument.

⚠ **What made it worse than a missing feature.** `jobs.py` sets ``status = "cancelled"`` from the
event alone, whatever the target did with it, so the user pressed Cancel, the job reported
**cancelled**, and `app.js`'s undo `onCancelled` rendered *"Restored N file(s) before you stopped
it."* - while the run put every remaining file back. The screen made a specific factual claim
about a run that had not stopped. `IMPLEMENTATION_STANDARDS.md` §9's *"a cancelled run says
cancelled"* held in form and was inverted in substance.

The engine property - stop between files, never mid-file - is pinned next door in
`test_undo_honours_a_cancel_between_files.py`. This file pins only that the app hands the event
over and reports what came back.
"""

from __future__ import annotations

import inspect
import random
import threading
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service.organize_undo import organize_undo
from truestill_cli.cli import main
from truestill_core.progress import Progress

FILES = 4


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def organized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    lib, db = tmp_path / "lib", tmp_path / "c.sqlite"
    for i in range(FILES):
        _jpeg(lib / "Old Folder" / f"p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(lib), "--label", "L", "--db", str(db)]) == 0
    monkeypatch.setattr("builtins.input", lambda _="": "move")
    assert main(["organize", str(lib), str(lib), "--in-place", "--apply", "--db", str(db)]) == 0
    return lib, db


def _noop(_progress: Progress) -> None:
    return None


def test_a_cancel_set_before_the_job_starts_restores_nothing(
    organized: tuple[Path, Path],
) -> None:
    """⚠ **FAILS BEFORE THE FIX** - the job accepted the event and restored all four anyway.

    An event already set is the honest worst case: there is no race to lose and no timing to
    tune, so a run that still restores files is doing so with the cancel in hand.
    """
    _lib, db = organized
    cancel = threading.Event()
    cancel.set()

    summary = organize_undo(db=db, apply=True)(_noop, cancel)

    assert summary["restored"] == 0, (
        f"the job was handed a set cancel and restored {summary['restored']} file(s) anyway"
    )
    assert summary["stopped"] is not None, "the summary must say the run stopped"
    assert summary["stopped"]["kind"] == "cancelled"
    assert summary["stopped"]["never_attempted"] == FILES


def test_a_cancelled_undo_stays_armed_so_the_card_offers_it_again(
    organized: tuple[Path, Path],
) -> None:
    """`(agk)`'s recovery property, read through the payload the screen actually gets.

    `still_armed` is what `refreshOrganizeUndoAffordance` re-renders the armed card from, so this
    is the assertion that the user is told a second undo will finish the job.
    """
    _lib, db = organized
    cancel = threading.Event()
    cancel.set()

    summary = organize_undo(db=db, apply=True)(_noop, cancel)

    assert summary["still_armed"] is True
    assert summary["restorable"] == FILES


def test_the_target_names_its_cancel_rather_than_discarding_it(tmp_path: Path) -> None:
    """The convention itself: a discarded parameter wears an underscore, a used one does not.

    ⚠ **Read from the SIGNATURE, never by grepping the source** - `inspect.signature`, the same
    way `test_every_job_declares_whether_it_mutates` reads `mutating`. The first draft of this
    test matched the text `_cancel` and went red on **its own comment explaining the defect**,
    which is §4's member about a comment that quotes the artefact name becoming noise in every
    text search. A signature cannot be fooled by prose, and it is the thing that actually misled
    a reader here.

    Every other `JobTarget` in this package already names it `cancel`; this one was the outlier.
    """
    target = organize_undo(db=tmp_path / "unused.sqlite", apply=False)
    names = list(inspect.signature(target).parameters)

    assert names[1] == "cancel", (
        f"the undo target calls its cancel {names[1]!r}. A leading underscore declares a "
        "parameter deliberately unused, and this one is wired - the name would be a false "
        "statement about live code."
    )


# --- cry-wolf -----------------------------------------------------------------------------


def test_an_untripped_cancel_restores_everything(organized: tuple[Path, Path]) -> None:
    """The half that goes red if the check fires on an event nobody set."""
    _lib, db = organized

    summary = organize_undo(db=db, apply=True)(_noop, threading.Event())

    assert summary["restored"] == FILES
    assert summary["stopped"] is None
    assert summary["still_armed"] is False


def test_a_preview_is_unaffected_by_a_set_cancel(organized: tuple[Path, Path]) -> None:
    """A preview writes nothing either way, so a cancel cannot change what it reports.

    Guards the direction nobody would look at: wiring a cancel into the apply path must not make
    the dry run answer differently, because `run_undo` returns before the loop when `apply` is
    false and the count on that card is what the user types `undo` against.
    """
    _lib, db = organized
    cancel = threading.Event()
    cancel.set()

    summary = organize_undo(db=db, apply=False)(_noop, cancel)

    assert summary["applied"] is False
    assert summary["restorable"] == FILES
    assert summary["restored"] == 0
    assert summary["stopped"] is None, "a preview never started, so it never stopped"
