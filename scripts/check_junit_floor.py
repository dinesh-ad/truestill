#!/usr/bin/env python3
"""Refuse a junit report that says the suite did not run.

A green step is not a proof that tests ran: pytest exits 0 for a file that collected nothing, a
junit upload set to ``if-no-files-found: warn`` is *"a warning in a log nobody opens"*
(`ENGINEERING_STANDARD.md` §4, forty-third member), and nothing in CI read ``test-results.xml``
for a count. This reads it. Missing file, unparseable file, or fewer tests than the floor is a
refusal; the floor is a fraction of the real count so a lane that silently collected half the
suite fails too. Standard library only - no dependency was added for this (P189, Q1213).
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def count_tests(report: Path) -> int:
    """Tests the report records: the ``tests`` attribute summed over ``testsuite`` elements, or
    the ``testcase`` elements counted when no suite carries the attribute."""
    root = ET.parse(report).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    declared = sum(int(suite.get("tests") or 0) for suite in suites)
    return declared if declared else sum(1 for _ in root.iter("testcase"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--at-least", type=int, default=1, help="fewest tests that count as a run")
    args = parser.parse_args(argv)
    if not args.report.is_file():
        print(
            f"junit floor: {args.report} does not exist, so nothing proves the suite ran",
            file=sys.stderr,
        )
        return 1
    try:
        total = count_tests(args.report)
    except ET.ParseError as exc:
        print(f"junit floor: {args.report} is not a junit report ({exc})", file=sys.stderr)
        return 1
    if total < args.at_least:
        print(
            f"junit floor: {args.report} records {total} test(s), under the floor of "
            f"{args.at_least} - the suite did not run, or ran a fraction of itself",
            file=sys.stderr,
        )
        return 1
    print(f"junit floor: {total} tests recorded (floor {args.at_least})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
