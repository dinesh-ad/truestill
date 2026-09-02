"""A mutant that stops pytest from running is not a mutant that killed nothing.

`mutation_matrix.py` ran every mutant, threw the exit code into ``_`` and read the junit report
alone: a mutant that broke collection made pytest exit 4 or 5, left an empty report, and was filed
under *"MUTATIONS THAT KILLED NOTHING - missing guard, or dead code"*. The sibling tool,
`mutate_once.py`, refuses exactly that inference and says why (`_PYTEST_NOT_A_RESULT_EXITS`).
Found 2026-09-02 (P188) as one instance of a guard reporting a verdict while not having checked.

The decision is one function, and this pins it - and pins that the two tools rule by one set.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: the script's dataclasses resolve their own module by name.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_matrix = _load("mutation_matrix")


@pytest.mark.parametrize("code", sorted(_matrix._NOT_A_RESULT))
def test_a_run_pytest_refused_is_not_a_survivor(code: int) -> None:
    assert _matrix._outcome(set(), code) == "broke the run"


def test_a_partial_report_from_a_broken_run_is_not_a_kill() -> None:
    """A run can record failures and then die on a usage error; that run did not finish."""
    assert _matrix._outcome({"test_x.py::t"}, 4) == "broke the run"


def test_the_two_real_outcomes_are_unchanged() -> None:
    assert _matrix._outcome(set(), 0) == "inert"
    assert _matrix._outcome({"test_x.py::t"}, 1) == "killed"


def test_the_two_tools_rule_by_one_set() -> None:
    """If `mutate_once` learns a new not-a-result code, the matrix must learn it in the same commit."""
    once = _load("mutate_once")
    assert _matrix._NOT_A_RESULT == once._PYTEST_NOT_A_RESULT_EXITS
