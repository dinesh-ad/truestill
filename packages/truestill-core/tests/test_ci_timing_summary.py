"""The CI timing instrument, and the one property that matters: it cannot fail a build.

`docs/PERFORMANCE.md` §5.1 records why this exists. The Windows lane swings 405-1308 s on an
unchanged suite, and telling a slow *runner* from a slow *suite* took a 20-minute dig through
`gh` history. The discriminator is the ratio of the pytest step to a **fixed-cost** step
(installing exiftool downloads the same archive every run), because that ratio is
runner-independent. This emits it into the run itself.

**It is an instrument, not a gate.** A threshold here would fire on runner variance - the thing
we measured and cannot control - and a check that fires on noise gets switched off, taking its
signal with it. So the script never exits non-zero and the workflow step is belt-and-braces
`continue-on-error`.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "ci_timing_summary.py"
_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("ci_timing_summary", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(env: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, str]:
    """Run main() with a controlled environment; return (exit code, rendered summary)."""
    summary = tmp_path / "summary.md"
    for key in list(os.environ):
        if key.startswith(("TS_", "GITHUB_")):
            monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    code = _load().main()
    return code, summary.read_text(encoding="utf-8") if summary.exists() else ""


_HEALTHY = {"TS_EXIFTOOL_START": "100", "TS_EXIFTOOL_END": "115", "TS_PYTEST_SECONDS": "450"}


# --- it can never fail a build ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "env"),
    [
        ("healthy", _HEALTHY),
        ("nothing set", {}),
        ("pytest missing", {"TS_EXIFTOOL_START": "100", "TS_EXIFTOOL_END": "115"}),
        ("exiftool missing", {"TS_PYTEST_SECONDS": "450"}),
        ("garbage", {"TS_EXIFTOOL_START": "x", "TS_EXIFTOOL_END": "y", "TS_PYTEST_SECONDS": "z"}),
        ("negative clock", {"TS_EXIFTOOL_START": "200", "TS_EXIFTOOL_END": "100"}),
        ("zero fixed cost", {**_HEALTHY, "TS_EXIFTOOL_END": "100"}),
    ],
)
def test_the_instrument_always_exits_zero(
    label: str, env: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every input shape, including ones that cannot happen, exits 0.

    A divide-by-zero or a missing variable turning a green suite red would make the instrument
    a worse problem than the variance it measures.
    """
    code, _summary = _run(env, tmp_path, monkeypatch)
    assert code == 0, label


def test_a_zero_fixed_cost_does_not_divide_by_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one arithmetic hazard, stated on its own so a failure names it."""
    _code, summary = _run({**_HEALTHY, "TS_EXIFTOOL_END": "100"}, tmp_path, monkeypatch)
    assert "450" in summary
    assert "nan" not in summary.lower()
    assert "inf" not in summary.lower()


# --- what it reports -------------------------------------------------------------------------


def test_the_raw_numbers_appear_beside_the_ratio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ratio with no inputs cannot be sanity-checked, so both must be present."""
    _code, summary = _run(_HEALTHY, tmp_path, monkeypatch)
    assert "450" in summary, "the pytest seconds must be shown"
    assert "15" in summary, "the fixed-cost seconds must be shown"


def test_the_ratio_is_pytest_over_the_fixed_cost_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """450 / 15 = 30. Asserted as a value, because the point is comparing it across runs."""
    _code, summary = _run(_HEALTHY, tmp_path, monkeypatch)
    assert "30" in summary


def test_a_slow_runner_and_a_slow_suite_render_differently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The discriminator, exercised on the two real shapes from 2026-08-03.

    `37ee466` was 1308 s of pytest with a 55 s exiftool install -- ratio 24, the same as a
    healthy run. A genuinely slower suite would raise the ratio instead.
    """
    _code, slow_runner = _run(
        {"TS_EXIFTOOL_START": "0", "TS_EXIFTOOL_END": "55", "TS_PYTEST_SECONDS": "1308"},
        tmp_path,
        monkeypatch,
    )
    _code, slow_suite = _run(
        {"TS_EXIFTOOL_START": "0", "TS_EXIFTOOL_END": "15", "TS_PYTEST_SECONDS": "1308"},
        tmp_path,
        monkeypatch,
    )
    assert "24" in slow_runner
    assert "87" in slow_suite


def test_it_falls_back_to_stdout_when_there_is_no_summary_file(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Runnable locally, so the format can be checked without pushing to CI."""
    for key in list(os.environ):
        if key.startswith(("TS_", "GITHUB_")):
            monkeypatch.delenv(key, raising=False)
    for key, value in _HEALTHY.items():
        monkeypatch.setenv(key, value)
    assert _load().main() == 0
    assert "450" in capsys.readouterr().out


# --- the workflow wiring ----------------------------------------------------------------------


def _summary_steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    return [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "ci_timing_summary" in str(step.get("run", ""))
    ]


def test_the_workflow_runs_the_instrument() -> None:
    """Anti-vacuity: the tests above prove a script nobody calls without this."""
    assert _summary_steps(), "no CI step runs scripts/ci_timing_summary.py"


def test_the_instrument_step_cannot_fail_the_build() -> None:
    """Belt and braces, because "the script always exits 0" is a property a refactor can lose.

    `continue-on-error` makes it structural: even a crashing script leaves the lane green.
    """
    for step in _summary_steps():
        assert step.get("continue-on-error") is True, step.get("name")
        assert step.get("if") == "always()", step.get("name")


def test_every_timed_step_records_both_ends() -> None:
    """A stopwatch with one hand tells nothing; both marks must exist on the same job."""
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    for name, job in workflow["jobs"].items():
        body = "\n".join(str(step.get("run", "")) for step in job["steps"])
        if "ci_timing_summary" not in body:
            continue
        for marker in ("TS_EXIFTOOL_START", "TS_EXIFTOOL_END", "TS_PYTEST_SECONDS"):
            assert marker in body, f"{name} runs the instrument without setting {marker}"
