"""`compare_selfcheck.py`'s version half - the guard that would have caught `(ajw)` twice.

**Why this is a file of its own.** The defect it closes is not that the version was wrong; it is
that **nothing compared it to anything**. v0.1.0 and v0.1.1 both published a settings screen
reading *"truestill unknown (not installed)"* and both passed every release gate, because the
self-check reported `install: packaged` and said nothing about a version. So the tests here are
shaped the way `test_selfcheck.py` says they must be: every refusal is produced deliberately, and
the agreeing case is kept beside them, because a comparison that has only been seen to pass is not
known to be able to refuse.

**Two questions, and they fail for different reasons on purpose.** The artifact is compared
against the checkout's own `pyproject.toml` on **every** path - which is what makes a
`workflow_dispatch` dry run exercise this - and against the **tag** only when there is one. If the
tag comparison were the only one, `(ajw)` would survive the rehearsal a third time, since a
rehearsal has no tag.

`compare_selfcheck.py` is not importable as a package (it is a script `release.yml` runs), so it
is loaded by path here exactly as `test_selfcheck_app.py` already loads it.
"""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from typing import Any

import pytest
from truestill_core.version import UNKNOWN_VERSION

_ROOT = Path(__file__).resolve().parents[3]


def _compare_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "compare_selfcheck", _ROOT / "packaging/compare_selfcheck.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _declared(distribution: str) -> str:
    data = tomllib.loads(
        (_ROOT / "packages" / distribution / "pyproject.toml").read_text(encoding="utf-8")
    )
    return str(data["project"]["version"])


def _finding(distribution: str, version: str) -> dict[str, object]:
    """The shape `truestill_core.selfcheck.version_finding` actually writes."""
    return {
        "name": f"version {distribution}",
        "status": "ok",
        "detail": version,
        "evidence": {"distribution": distribution, "version": version},
    }


def _agreeing() -> list[dict[str, object]]:
    return [_finding(d, _declared(d)) for d in ("truestill-app", "truestill-core")]


@pytest.fixture
def compare() -> Any:
    return _compare_module()


def test_an_artifact_that_agrees_with_the_checkout_is_not_refused(compare: Any) -> None:
    """The cry-wolf half. Without it every refusal below would still pass against a comparison
    hard-wired to complain."""
    assert compare._version_problems(Path("f.json"), _agreeing(), None) == []


def test_a_version_that_disagrees_with_the_checkout_is_refused(compare: Any) -> None:
    """These bytes were not built from this checkout - the only thing a released artifact's
    version can honestly mean."""
    findings = [
        _finding("truestill-app", "9.9.9"),
        _finding("truestill-core", _declared("truestill-core")),
    ]
    problems = compare._version_problems(Path("f.json"), findings, None)
    assert len(problems) == 1
    assert "truestill-app is not the version this repository declares" in problems[0]
    assert "9.9.9" in problems[0]


def test_an_artifact_that_reports_no_version_at_all_is_refused(compare: Any) -> None:
    """**The exact state that shipped twice.** The published builds reported `install: packaged`
    and nothing else about themselves; a comparison that only checked findings it happened to
    find would have passed on both, which is the whole failure."""
    problems = compare._version_problems(Path("f.json"), [], None)
    assert len(problems) == 2
    assert all("THE ARTIFACT NEVER REPORTED ITS VERSION" in p for p in problems)


def test_the_unknown_value_is_refused_rather_than_accepted_as_a_version(compare: Any) -> None:
    """`(ajw)`'s own string. It is caught upstream by the artifact's `DEGRADED` finding too;
    two independent refusals for the defect that got through twice."""
    findings = [
        _finding("truestill-app", UNKNOWN_VERSION),
        _finding("truestill-core", _declared("truestill-core")),
    ]
    problems = compare._version_problems(Path("f.json"), findings, None)
    assert len(problems) == 1
    assert UNKNOWN_VERSION in problems[0]


def test_an_artifact_that_disagrees_with_the_tag_is_refused(compare: Any) -> None:
    """A build stamped from the wrong checkout, or a tag pushed without bumping `pyproject.toml`.
    The artifact agrees with the checkout it was built from and still must not publish under a
    tag that names a different version."""
    problems = compare._version_problems(Path("f.json"), _agreeing(), "9.9.9")
    assert len(problems) == 1
    assert "THE ARTIFACT DISAGREES WITH THE TAG" in problems[0]


def test_the_tag_comparison_passes_when_the_tag_is_the_declared_version(compare: Any) -> None:
    """The release path as it will actually run: tag `v0.1.2` against a checkout declaring
    `0.1.2`. Its absence would let the refusal above be unconditional."""
    assert compare._version_problems(Path("f.json"), _agreeing(), _declared("truestill-app")) == []


def test_the_checkout_comparison_runs_without_a_tag_so_a_dry_run_exercises_it(
    compare: Any,
) -> None:
    """`(ajw)` reached publication through a lane that had already been rehearsed. The rehearsal
    has no tag, so a guard that only fired on one would have missed it a third time."""
    findings = [_finding("truestill-app", UNKNOWN_VERSION)]
    assert compare._version_problems(Path("f.json"), findings, None) != []
