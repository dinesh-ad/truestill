"""The flake instrument: it must read failures correctly, and it must never name a test flaky.

Sibling of `test_ci_timing_summary.py`, and it guards the same property - an instrument cannot
fail a build - plus one this repo cares about more.

**The no-flaky-column rule is enforced here, not merely written down.** Naming a test flaky is a
conclusion someone reaches after proving a failure unrelated to the change under test; it is not
a field a script can fill in. A tool that prints "flaky: yes" automates the exact reflex §4's
twenty-sixth member warns about - ~84% of pass-to-fail transitions are flakes, and a team that
internalises that base rate learns to shrug at a red lane until the one real regression walks
through. Adding the column is the first thing anyone will want to do, which is precisely why a
comment asking them not to is not enough. `test_the_report_never_reaches_a_verdict` fails if the
word ever appears in what the script prints.
"""

from __future__ import annotations

import collections
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "flake_report.py"
_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"

_JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4">
  <testcase classname="tests.e2e.test_a" name="test_passes"/>
  <testcase classname="tests.e2e.test_a" name="test_fails"><failure>boom</failure></testcase>
  <testcase classname="tests.e2e.test_b" name="test_errors"><error>bang</error></testcase>
  <testcase classname="tests.e2e.test_b" name="test_skipped"><skipped/></testcase>
</testsuite></testsuites>
"""

_CLEAN = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="1">
  <testcase classname="tests.e2e.test_a" name="test_passes"/>
</testsuite></testsuites>
"""


_TIMED = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4">
  <testcase classname="tests.e2e.test_a" name="test_quick" time="0.10"/>
  <testcase classname="tests.e2e.test_a" name="test_slow" time="9.30"/>
  <testcase classname="tests.e2e.test_b" name="test_skipped" time="0.00"><skipped/></testcase>
  <testcase classname="tests.e2e.test_b" name="test_unparseable" time="not-a-number"/>
</testsuite></testsuites>
"""


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("flake_report", _SCRIPT)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_it_reads_failures_and_errors_but_not_skips(tmp_path: Path) -> None:
    """The matcher, on input built to exercise each outcome. A skip is not a failure - counting
    one would inflate every report on a suite that legitimately skips on Windows."""
    xml = tmp_path / "test-results.xml"
    xml.write_text(_JUNIT, encoding="utf-8")

    assert _load()._failures_in(xml) == {
        "tests/e2e/test_a::test_fails",
        "tests/e2e/test_b::test_errors",
    }


@pytest.mark.parametrize("body", ["", "not xml at all", "<testsuites>"])
def test_an_unreadable_file_is_empty_not_an_exception(tmp_path: Path, body: str) -> None:
    """An instrument that raises on a truncated artifact is one nobody runs twice."""
    xml = tmp_path / "broken.xml"
    xml.write_text(body, encoding="utf-8")
    assert _load()._failures_in(xml) == set()


def test_a_missing_file_is_empty_not_an_exception(tmp_path: Path) -> None:
    assert _load()._failures_in(tmp_path / "absent.xml") == set()


def test_it_cannot_fail_a_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every path returns 0, including the one where `gh` is not installed at all."""
    module = _load()
    monkeypatch.setattr(module.sys, "argv", ["flake_report.py"])
    monkeypatch.setattr(module, "_gh", lambda *_: None)
    assert module.main() == 0


def _driven(module: object, monkeypatch: pytest.MonkeyPatch, junit: str | None) -> None:
    """Run `main()` against two fabricated runs, so the REPORT path actually executes.

    The first version of this test stubbed `_gh` to return ``None``, which makes `main()` return
    at "no runs to read" - so it asserted on output the script had never produced, and a mutation
    that printed a verdict sailed through it. Driving both `run list` and `run download` is what
    makes the assertions below reach the lines they are about.
    """

    def fake_gh(*args: str) -> str | None:
        if args[:2] == ("run", "list"):
            return json.dumps(
                [
                    {
                        "databaseId": 1,
                        "headSha": "aaaaaaaa11",
                        "conclusion": "failure",
                        "createdAt": "2026-08-10T00:00:00Z",
                        "displayTitle": "one",
                    },
                    {
                        "databaseId": 2,
                        "headSha": "bbbbbbbb22",
                        "conclusion": "success",
                        "createdAt": "2026-08-10T01:00:00Z",
                        "displayTitle": "two",
                    },
                ]
            )
        if args[:2] == ("run", "download") and junit is not None:
            target = Path(args[args.index("--dir") + 1])
            target.mkdir(parents=True, exist_ok=True)
            (target / "test-results.xml").write_text(junit, encoding="utf-8")
            return ""
        return None

    monkeypatch.setattr(module.sys, "argv", ["flake_report.py"])
    monkeypatch.setattr(module, "_gh", fake_gh)
    assert module.main() == 0


def test_the_report_never_reaches_a_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The rule this file exists for**, asserted over every path that prints.

    The script may print counts and run ids. It may not print a judgement about any test, because
    that judgement is a human step and skipping it is how a real regression is waved through as
    "just a flake".

    Asserted on the OUTPUT, not the source, so the docstrings explaining the rule - which
    necessarily use the word - cannot satisfy it, and a future `flaky: yes` column cannot hide
    behind them.
    """
    module = _load()
    for junit in (_JUNIT, _CLEAN, None):
        _driven(module, monkeypatch, junit)
        printed = capsys.readouterr().out.lower()
        assert "flaky: " not in printed
        assert "verdict:" not in printed
        assert "likely" not in printed
        assert "probably" not in printed


def test_it_counts_the_same_failure_across_runs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The one thing the report is for: a test that failed in both runs is reported as 2x, with
    the runs named so somebody can go and read them."""
    module = _load()
    _driven(module, monkeypatch, _JUNIT)

    printed = capsys.readouterr().out
    assert "read 2 of 2 recent runs" in printed
    assert "2x  tests/e2e/test_a::test_fails" in printed
    assert "aaaaaaaa" in printed
    assert "bbbbbbbb" in printed


def test_both_lanes_upload_what_this_reads() -> None:
    """The instrument is useless if the artifacts stop being produced, and that failure would be
    silent - the report would simply say "no failures recorded" forever."""
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    module = _load()

    uploads = [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if str(step.get("with", {}).get("name", "")).startswith(module._ARTIFACT_PREFIX)
    ]
    assert len(uploads) == 2, "both the check matrix and the e2e lane must upload results"
    for step in uploads:
        assert step["if"] == "always()", "a red run is exactly when the file is worth having"
        assert step["with"]["path"] == "test-results.xml"

    junit = [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "--junitxml=test-results.xml" in str(step.get("run", ""))
    ]
    assert len(junit) == 2, "both lanes must actually write the file they upload"


def test_it_reads_the_time_every_junit_already_records(tmp_path: Path) -> None:
    """The timings were always in the artifact; this reads them.

    A **skip** is dropped rather than recorded as 0.00 s - a skipped test did not take no time,
    it did not run, and a zero in the table would read as the first. An unparseable `time` is
    dropped for the same reason it is not defaulted to zero: an instrument that invents a number
    is worse than one that omits a row.
    """
    xml = tmp_path / "test-results.xml"
    xml.write_text(_TIMED, encoding="utf-8")

    assert _load()._durations_in(xml) == {
        "tests/e2e/test_a::test_quick": 0.10,
        "tests/e2e/test_a::test_slow": 9.30,
    }


def test_a_missing_or_broken_file_yields_no_timings(tmp_path: Path) -> None:
    """Same rule as the failure reader: this is an instrument and must not raise."""
    module = _load()
    assert module._durations_in(tmp_path / "absent.xml") == {}
    broken = tmp_path / "broken.xml"
    broken.write_text("<testsuites>", encoding="utf-8")
    assert module._durations_in(broken) == {}


def test_the_slow_list_is_ordered_by_the_worst_run_not_the_average(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """⚠ THE ORDERING IS THE WHOLE VALUE, so it is pinned.

    A test at a steady 5 s and one that is usually 0.4 s but occasionally 9 s have similar
    averages and are completely different problems. Sorting by the worst run puts the second
    first, which is the one worth opening - and it is how `PERFORMANCE.md` §5.4 found its answer,
    with the body of the distribution unmoved and the tail exploded.
    """
    module = _load()
    module._print_slowest(
        collections.defaultdict(list, {"steady": [5.0, 5.0, 5.0], "spiky": [0.4, 9.0, 0.4]}), 5
    )

    out = capsys.readouterr().out
    assert out.index("spiky") < out.index("steady"), "the spiky test must be listed first"
    assert "0.40" in out, "the best run must be shown"
    assert "9.00" in out, "the worst run must be shown"


def test_nothing_to_time_prints_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    """A run with no timings must not print an empty heading - a section with no rows reads as a
    tool that failed rather than as a run that recorded nothing."""
    _load()._print_slowest(collections.defaultdict(list), 5)
    assert capsys.readouterr().out == ""
