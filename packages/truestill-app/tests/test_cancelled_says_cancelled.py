"""(F38 latent B) Cancel arrives as ok:true - runJob must dispatch cancelled, not success.

Site-level copy lives in onCancelled callbacks; the branch that chooses them is in runJob.
"""

from __future__ import annotations

from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static" / "app.js"


def test_run_job_branches_on_cancelled_before_success() -> None:
    src = APP_JS.read_text(encoding="utf-8")
    body = src.split("async function runJob(", 1)[1].split("\nasync function withBusy(", 1)[0]
    assert 'else if (d.status === "cancelled") await onCancelled(d);' in body
    assert "else await onSuccess(d);" in body


def test_reference_cancelled_copy_still_present() -> None:
    """Previews 5/8/9/13 and organize run already said cancelled; extraction keeps that copy.

    The handler *count* is not asserted here - `test_run_job.py` owns that, and derives it from
    the number of job sites rather than pinning the number of features that existed when this
    was written. Two files hard-coding the same 13 is the duplication the companion rule warns
    about; this one keeps only what it is really about, which is the wording.
    """
    src = APP_JS.read_text(encoding="utf-8")
    assert "Check cancelled" in src
    assert "Preview cancelled" in src
    assert "before you stopped it" in src
