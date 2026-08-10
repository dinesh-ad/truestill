"""Which tests failed, in which CI runs, how often. Read on demand; nothing runs this in CI.

    uv run python scripts/flake_report.py            # last 20 runs
    uv run python scripts/flake_report.py --runs 50

**Why this exists.** Green runs were being counted by hand in a backlog entry to decide whether
a flake had settled. That is the manual version of the one intervention every large team reports
working first: visibility. Spotify cut their flake rate by a third in two months from a view of
the data alone, *before* any enforcement. This is the cheapest honest form of that view - JUnit
XML the test runner already knows how to emit, uploaded as an artifact, read when someone asks.

**THERE IS NO "FLAKY" COLUMN, AND THERE MUST NEVER BE ONE.** This is the first thing anyone will
want to add, so here is the argument against it. Naming a test flaky is a *conclusion somebody
reaches* after proving the failure unrelated to the change under test - it is not a field a
script can fill in. A tool that prints "flaky: yes" automates precisely the reflex
`ENGINEERING_STANDARD.md` §4's twenty-sixth member warns about: roughly 84% of pass-to-fail
transitions across the industry are flakes rather than regressions, and a team that internalises
that base rate learns to shrug at a red lane until the one real regression in six walks through.
The counter is *prove unrelated, never assert it*. A column that asserts it on your behalf
removes the step that catches the regression. So this prints counts and run ids, and stops.

**What it cannot tell you, which is the point rather than a shortfall.** These are failure
counts, not flake rates. A test appearing three times may be flaky, or may be one a real
regression broke three times, or may be a test somebody left broken - and **this cannot tell
those apart, deliberately.** Nothing here reads the diff, and nothing here decides. Reaching a
verdict means opening the runs, and the trace is already attached to each red e2e lane for
exactly that. The instrument narrows where to look; it does not look for you.

**An instrument, not a gate** - the same rule `ci_timing_summary.py` states for the same reason.
Every failure path here exits 0 with a message: a missing `gh`, no artifacts, an unparseable
file. Nothing in CI calls this, so it cannot redden a lane, and there is no threshold to trip on
a slow week.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

#: Artifacts this reads. Set by the two `Upload test results` steps in `ci.yml`.
_ARTIFACT_PREFIX = "test-results"


#: A run with no results artifact is ORDINARY, not an error: every run older than the workflow
#: step that uploads it, and any lane that died before pytest ran. Printing a scary line for each
#: would bury the one message that matters under noise the reader can do nothing about.
_EXPECTED_ABSENCE = "no valid artifacts found to download"


def _gh(*args: str) -> str | None:
    """Run `gh`, or return ``None``. Never raises: this is an instrument."""
    try:
        done = subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=False, timeout=120
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"could not run gh: {exc}")
        return None
    if done.returncode != 0:
        if _EXPECTED_ABSENCE not in done.stderr:
            print(f"gh {' '.join(args)} failed: {done.stderr.strip()[:200]}")
        return None
    return done.stdout


def _failures_in(xml: Path) -> set[str]:
    """`file::test` for every case that failed or errored. A skip is not a failure."""
    try:
        root = ET.parse(xml).getroot()
    except (ET.ParseError, OSError):
        return set()
    named: set[str] = set()
    for case in root.iter("testcase"):
        if case.find("failure") is None and case.find("error") is None:
            continue
        where = case.get("classname", "").replace(".", "/")
        named.add(f"{where}::{case.get('name', '?')}")
    return named


def _runs(limit: int) -> list[dict[str, Any]]:
    out = _gh(
        "run",
        "list",
        "--limit",
        str(limit),
        "--json",
        "databaseId,headSha,conclusion,createdAt,displayTitle",
    )
    if out is None:
        return []
    try:
        parsed: list[dict[str, Any]] = json.loads(out)
    except json.JSONDecodeError:
        print("gh returned something that is not JSON")
        return []
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=20, help="how many recent runs to read")
    args = parser.parse_args()

    runs = _runs(args.runs)
    if not runs:
        print("no runs to read")
        return 0

    counts: Counter[str] = Counter()
    where: defaultdict[str, list[str]] = defaultdict(list)
    read = 0

    with tempfile.TemporaryDirectory() as tmp:
        for run in runs:
            run_id = str(run["databaseId"])
            target = Path(tmp) / run_id
            if (
                _gh(
                    "run",
                    "download",
                    run_id,
                    "--pattern",
                    f"{_ARTIFACT_PREFIX}*",
                    "--dir",
                    str(target),
                )
                is None
            ):
                continue
            found = sorted(target.rglob("*.xml"))
            if not found:
                continue
            read += 1
            for xml in found:
                for test in _failures_in(xml):
                    counts[test] += 1
                    where[test].append(f"{run_id} ({run['headSha'][:8]})")

    print(f"read {read} of {len(runs)} recent runs\n")
    if not counts:
        print("no failures recorded. That is a fact about these runs, not a verdict on any test.")
        return 0

    width = max(len(t) for t in counts)
    for test, n in counts.most_common():
        print(f"{n:>3}x  {test:<{width}}  {', '.join(where[test][:4])}")
    print(
        "\nCounts only. Whether any of these is flaky is a conclusion to reach by opening the "
        "runs and proving the failure unrelated - never one to read off this table."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - a command, exercised by its tests
    sys.exit(main())
