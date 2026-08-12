"""A staged copy that survived because its own cleanup failed is findable again. `(acz)`.

`(acj)` made a survivor safe - named `<target>.partial`, so `_free_relative` never suffixes beside
it and `scan_source` can never take it for a photo. **It also moved the discovery seam**: `(abu)`
was found because "rescan reports it as STRAY", which was true only while the leftover carried a
media extension. `rescan` is fed `scan_source(...).media`, so a `.partial` stopped reaching it.

This gives it back, as its **own outcome rather than as a stray**, because the two need opposite
words - `(ach)`'s lesson, applied at the point where it would otherwise be repeated.
"""

from __future__ import annotations

from truestill_core.rescan import reconcile
from truestill_core.safe_copy import STAGING_SUFFIX


def test_a_surviving_staged_copy_is_reported() -> None:
    """The whole point: a user who hit a full disk mid-copy has debris whose only record was a
    message that scrolled past."""
    report = reconcile(
        recorded={},
        on_disk=[],
        identified={},
        debris=[f"2014/2014-08/IMG_0001.jpg{STAGING_SUFFIX}"],
    )
    assert report.debris == (f"2014/2014-08/IMG_0001.jpg{STAGING_SUFFIX}",)


def test_debris_is_not_folded_into_stray() -> None:
    """**THE DESIGN.** A stray may be a photograph the user wants adopted; debris is truestill's
    own failed write and the only sane action is removing it. One count meaning both would be
    `ApplyReport.skipped_newer_locally` again - two meanings needing opposite words."""
    report = reconcile(recorded={}, on_disk=[], identified={}, debris=[f"a.jpg{STAGING_SUFFIX}"])
    assert report.stray == ()
    assert report.debris == (f"a.jpg{STAGING_SUFFIX}",)


def test_a_real_stray_is_still_a_stray() -> None:
    """**CRY-WOLF HALF.** Debris must not start swallowing files that are genuinely unaccounted
    for - that would hide a photograph behind a word meaning litter."""
    report = reconcile(
        recorded={}, on_disk=["holiday.jpg"], identified={"holiday.jpg": "s" * 64}, debris=[]
    )
    assert report.stray == ("holiday.jpg",)
    assert report.debris == ()


def test_debris_does_not_change_whether_the_drive_reconciled() -> None:
    """Deliberate, and stated rather than assumed. `reconciled` means every record and every file
    AGREED; debris is not a disagreement between record and disk, it is litter beside them. It
    drives the CLI's exit code, so making a leftover fail a run would turn a successful copy into
    a scripted failure. Reported, not failed on."""
    littered = reconcile(recorded={}, on_disk=[], identified={}, debris=[f"a.jpg{STAGING_SUFFIX}"])
    assert littered.debris
    assert littered.reconciled is True


def test_the_four_original_outcomes_are_untouched_by_the_fifth() -> None:
    """Anti-regression on the contract sentence: four outcomes, disjoint and exhaustive over
    records and media. Debris arrives from a different input and may not disturb them."""
    recorded = {"placed.jpg": "p" * 64, "gone.jpg": "g" * 64}
    report = reconcile(
        recorded=recorded,
        on_disk=["placed.jpg", "extra.jpg"],
        identified={"extra.jpg": "e" * 64},
        debris=[f"x.jpg{STAGING_SUFFIX}"],
    )
    assert report.placed == ("placed.jpg",)
    assert report.stray == ("extra.jpg",)
    assert report.unaccounted == ("gone.jpg",)
    assert report.moved == ()
