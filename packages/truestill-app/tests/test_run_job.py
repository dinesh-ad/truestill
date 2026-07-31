"""(F38 commit 2) Every job site goes through runJob; cancel is dispatched once.

**The count is derived, not written down.** This file used to assert ``== 13``, which is a fact
about how many features existed the day it was written rather than the promise it stands for -
adding a fourteenth job made it fail while nothing was wrong. The promise is that *every* site
supplies ``onCancelled``, so that is what is compared, with a floor so the check cannot pass
vacuously if the calls are ever renamed away (`ENGINEERING_STANDARD.md` §4: assert the promise,
not what happens to have survived).
"""

from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static" / "app.js"


def test_await_job_is_only_called_from_run_job() -> None:
    """No site may keep a private copy of the awaitJob skeleton."""
    src = APP_JS.read_text(encoding="utf-8")
    # Strip the awaitJob definition itself; every remaining call must sit inside runJob.
    without_def = re.sub(
        r"function awaitJob\(jobId, onProgress\) \{.*?\n\}",
        "",
        src,
        count=1,
        flags=re.S,
    )
    calls = [m.start() for m in re.finditer(r"awaitJob\(", without_def)]
    assert len(calls) == 1, f"expected one awaitJob call (inside runJob), found {len(calls)}"
    run_job_at = without_def.index("async function runJob(")
    run_job_end = without_def.index("\nasync function withBusy(", run_job_at)
    assert run_job_at < calls[0] < run_job_end, "the sole awaitJob call must live inside runJob"


def test_run_job_dispatches_cancelled_before_success() -> None:
    """The payoff of extraction: one cancelled branch reaches every site."""
    src = APP_JS.read_text(encoding="utf-8")
    body = src.split("async function runJob(", 1)[1].split("\nasync function withBusy(", 1)[0]
    assert 'd.status === "cancelled"' in body
    assert "onCancelled" in body
    # Cancelled must not fall through to onSuccess.
    cancelled_at = body.index('d.status === "cancelled"')
    success_call = body.index("onSuccess(d)", cancelled_at)
    assert "else" in body[cancelled_at:success_call]


def test_every_site_calls_run_job_with_on_cancelled() -> None:
    src = APP_JS.read_text(encoding="utf-8")
    sites = src.count("await runJob({")
    handled = src.count("onCancelled:")
    assert sites >= 13, f"only {sites} runJob sites found; have the calls been renamed?"
    assert handled == sites, (
        f"{sites} job sites but {handled} onCancelled handlers - a job whose cancel falls "
        "through to onSuccess reports a stopped run as a finished one"
    )
