"""A failed run names the files, at the same cap the CLI uses. `(ajl)`

**Measured before it was fixed.** Soak twelve's app half drove `organize` onto a drive that
vanished: **1,130 of 1,324 files failed** and the whole message on the screen was

    1,130 files could not be organized.

**No filename, no reason.** `cli._print_capped` has named up to `_STATUS_PREVIEW` of them and
counted the rest since `(afd)`, which was itself filed because an uncapped list printed **2,096
`FAILED` lines from ONE reason**. So the CLI already solved this and the app had the wrong half of
it: `(aiq)` calls that *"the inverse of `(aim)`'s framing"*, because a reader of `(aim)` would
copy the app.

🔑 **ONE CAP, BOTH SURFACES.** `models.FAILURE_PREVIEW_LIMIT` is read by `cli._STATUS_PREVIEW`
and by this payload, so the two surfaces cannot name a different number of files for one run.
It lives in core because `truestill-app` imports core and never the CLI.

⚠ **What this deliberately does NOT do**: group by reason. `(aiv)` measured that
`cli._reason_key` collapses neither failure message, so a grouped payload would ship that defect
to a second surface. And it does not link to the full list, because nothing serves the run record
- checked: `/api/runs` and `run_record` have zero occurrences in `server.py`.
"""

from __future__ import annotations

from pathlib import Path

from truestill_app.service.organize import _failed_report, _metadata_report
from truestill_cli.cli import _STATUS_PREVIEW
from truestill_core.models import (
    FAILURE_PREVIEW_LIMIT,
    ActionResult,
    ActionStatus,
)

APP_JS = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static" / "app.js"


class _Src:
    def __init__(self, name: str) -> None:
        self.name = name


class _Decision:
    def __init__(self, name: str) -> None:
        self.source = _Src(name)


class _Resolution:
    def __init__(self, name: str) -> None:
        self.decision = _Decision(name)


def _failure(name: str, detail: str) -> ActionResult:
    return ActionResult(
        resolution=_Resolution(name),  # type: ignore[arg-type]
        status=ActionStatus.FAILED,
        final_relative=None,
        detail=detail,
    )


def test_a_failed_run_names_the_files() -> None:
    """⚠ THE DETECTOR. Before `(ajl)` the payload carried a scalar and nothing else."""
    report = _failed_report([_failure("a.jpg", "the drive is not there any more")])
    assert report["total"] == 1
    assert report["shown"] == [{"name": "a.jpg", "detail": "the drive is not there any more"}]


def test_the_cap_is_cores_and_the_total_is_not_capped() -> None:
    """The soak's shape: far more failures than the cap. The count must survive the truncation."""
    results = [_failure(f"{n}.jpg", "the drive is not there any more") for n in range(1130)]
    report = _failed_report(results)
    assert report["total"] == 1130, "the count was capped along with the list"
    assert len(report["shown"]) == FAILURE_PREVIEW_LIMIT


def test_the_cli_reads_the_same_cap() -> None:
    """One home. A surface that redefines the number is what this refuses."""
    assert _STATUS_PREVIEW is FAILURE_PREVIEW_LIMIT


def test_only_failures_are_named() -> None:
    """A run's other outcomes are not failures and must not appear in this list."""
    results = [
        _failure("bad.jpg", "no space"),
        ActionResult(
            resolution=_Resolution("good.jpg"),  # type: ignore[arg-type]
            status=ActionStatus.UPLOADED,
            final_relative=None,
            detail="",
        ),
    ]
    report = _failed_report(results)
    assert report["total"] == 1
    assert [x["name"] for x in report["shown"]] == ["bad.jpg"]


def test_the_screen_renders_the_names_and_states_the_truncation() -> None:
    """⚠ The payload is not the screen. A field no renderer reads is `(ahl)`'s defect."""
    js = APP_JS.read_text(encoding="utf-8")
    assert "r.failed_files" in js, "the renderer does not read the field the service ships"
    assert "Show which" in js, "the names are not reachable from the card"
    assert "Showing ${nfmt(f.shown.length)} of" in js, (
        "truncation is implied rather than stated - the rule the grid and duplicate lists obey"
    )


# ------------------------------------------------ `(ajn)`: copied, safe, and without its timestamps


def _refused_metadata(name: str) -> ActionResult:
    return ActionResult(
        resolution=_Resolution(name),  # type: ignore[arg-type]
        status=ActionStatus.UPLOADED,
        final_relative=None,
        detail=f"{name!r} was copied to 'x/{name}' and is safe, but this drive does not let "
        "Truestill set timestamps or permissions",
        metadata_ok=False,
    )


def test_a_copy_that_lost_its_metadata_is_named_and_is_not_a_failure() -> None:
    results = [_refused_metadata("a.jpg"), _failure("b.jpg", "the drive is not there any more")]
    report = _metadata_report(results)
    assert report["total"] == 1
    assert report["shown"][0]["name"] == "a.jpg"
    assert "timestamps" in report["shown"][0]["detail"]
    assert _failed_report(results)["shown"][0]["name"] == "b.jpg", (
        "a caveated success is not a failure"
    )
    assert _failed_report(results)["total"] == 1


def test_the_metadata_list_shares_the_cap() -> None:
    results = [_refused_metadata(f"{i}.jpg") for i in range(FAILURE_PREVIEW_LIMIT + 5)]
    report = _metadata_report(results)
    assert report["total"] == FAILURE_PREVIEW_LIMIT + 5
    assert len(report["shown"]) == FAILURE_PREVIEW_LIMIT


def test_the_renderer_reads_the_field() -> None:
    """The payload key is only a fact if a pixel reads it; the string is the join."""
    source = APP_JS.read_text(encoding="utf-8")
    assert "r.metadata_files" in source
    assert 'data-testid="org-metadata-not-set"' in source
