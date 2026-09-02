"""CI reads the junit file for a count, and a missing or empty one is a refusal, not a warning.

Both junit uploads were ``if-no-files-found: warn`` and nothing read ``test-results.xml`` at
all, so "the suite ran" was inferred from a green step - and pytest exits 0 for a file that
collected nothing (P188's Q1209; built as P189's Q1213). Two halves: the script that counts,
and the workflow that wires it with ``if: always()`` and sets the uploads to ``error``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = ROOT / "scripts" / "check_junit_floor.py"
_CI = ROOT / ".github" / "workflows" / "ci.yml"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_junit_floor", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_junit_floor"] = module
    spec.loader.exec_module(module)
    return module


_floor = _load()


def _report(tmp_path: Path, tests: int, *, cases: int | None = None) -> Path:
    body = "".join(
        f'<testcase classname="t" name="c{i}" time="0.01"/>'
        for i in range(cases if cases is not None else tests)
    )
    path = tmp_path / "test-results.xml"
    path.write_text(
        f'<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="{tests}" errors="0" '
        f'failures="0" skipped="0">{body}</testsuite></testsuites>',
        encoding="utf-8",
    )
    return path


def test_zero_tests_is_a_refusal(tmp_path: Path, capsys: Any) -> None:
    assert _floor.main([str(_report(tmp_path, 0))]) == 1
    assert "did not run" in capsys.readouterr().err


def test_a_missing_report_is_a_refusal(tmp_path: Path, capsys: Any) -> None:
    assert _floor.main([str(tmp_path / "absent.xml")]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_a_count_under_the_floor_is_a_refusal(tmp_path: Path) -> None:
    assert _floor.main(["--at-least", "1000", str(_report(tmp_path, 400))]) == 1


def test_a_count_at_the_floor_passes(tmp_path: Path, capsys: Any) -> None:
    assert _floor.main(["--at-least", "1000", str(_report(tmp_path, 1000, cases=3))]) == 0
    assert "1000 tests recorded" in capsys.readouterr().out


def test_a_report_without_the_attribute_counts_its_cases(tmp_path: Path) -> None:
    path = tmp_path / "r.xml"
    path.write_text(
        '<testsuite name="x"><testcase name="a"/><testcase name="b"/></testsuite>', encoding="utf-8"
    )
    assert _floor.count_tests(path) == 2


def test_garbage_is_a_refusal(tmp_path: Path) -> None:
    path = tmp_path / "r.xml"
    path.write_text("not xml", encoding="utf-8")
    assert _floor.main([str(path)]) == 1


def _jobs() -> dict[str, Any]:
    doc = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    jobs: dict[str, Any] = doc["jobs"]
    return jobs


def test_every_junit_upload_errors_on_absence_and_has_a_floor_step() -> None:
    uploads = 0
    for name, job in _jobs().items():
        steps = job.get("steps", [])
        junit = [
            s
            for s in steps
            if "upload-artifact" in str(s.get("uses", ""))
            and "test-results.xml" in str((s.get("with") or {}).get("path", ""))
        ]
        for step in junit:
            uploads += 1
            assert step["with"].get("if-no-files-found") == "error", (
                f"{name}: the junit upload only warns"
            )
            floors = [s for s in steps if "check_junit_floor.py" in str(s.get("run", ""))]
            assert floors, f"{name}: uploads test-results.xml and never reads it for a count"
            assert all(str(s.get("if", "")).strip() == "always()" for s in floors), (
                f"{name}: the floor step must run after a red suite too"
            )
    assert uploads == 2, f"{uploads} junit uploads seen; both lanes write the file they upload"
