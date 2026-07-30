"""(F38 commit 2) All thirteen job sites go through runJob; cancel is dispatched once."""

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
    """The payoff of extraction: one cancelled branch reaches all thirteen sites."""
    src = APP_JS.read_text(encoding="utf-8")
    body = src.split("async function runJob(", 1)[1].split("\nasync function withBusy(", 1)[0]
    assert 'd.status === "cancelled"' in body
    assert "onCancelled" in body
    # Cancelled must not fall through to onSuccess.
    cancelled_at = body.index('d.status === "cancelled"')
    success_call = body.index("onSuccess(d)", cancelled_at)
    assert "else" in body[cancelled_at:success_call]


def test_thirteen_sites_call_run_job_with_on_cancelled() -> None:
    src = APP_JS.read_text(encoding="utf-8")
    # 13 call sites (definition excluded).
    assert src.count("await runJob({") == 13
    assert src.count("onCancelled:") == 13
