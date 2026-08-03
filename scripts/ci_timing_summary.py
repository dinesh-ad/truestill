"""Emit the CI timing ratio into the run's own summary, so variance is answerable at a glance.

The Windows lane swings 405-1308 s on a suite that did not change. Telling a slow **runner**
from a slow **suite** took a 20-minute dig through `gh` history; the discriminator turned out to
be the ratio of the pytest step to a **fixed-cost** step. Installing exiftool downloads and
unpacks the same archive every run, so its duration is a property of the machine and nothing
else -- when it triples, the machine is slow. `docs/PERFORMANCE.md` §5.1 records the measurement.

**This is an instrument, not a gate, and the distinction is load-bearing.** Any threshold here
would fire on runner variance, which is exactly what we proved we cannot control; a check that
fires on noise gets switched off and takes its real signal with it. So every path returns 0 --
missing variables, unparseable values, a backwards clock, a zero-length fixed step. The workflow
also marks the step `continue-on-error`, so a crash cannot redden a lane either.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _seconds(name: str) -> int | None:
    """A non-negative integer from the environment, or ``None`` for anything else.

    Deliberately total: this runs after the suite has already passed or failed, and its own
    opinion of the environment must never change that outcome.
    """
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def _elapsed(start_name: str, end_name: str) -> int | None:
    start, end = _seconds(start_name), _seconds(end_name)
    if start is None or end is None or end < start:
        return None
    return end - start


def render(pytest_seconds: int | None, fixed_seconds: int | None, lane: str) -> str:
    """The summary block. Raw numbers beside the ratio, because a ratio alone cannot be checked.

    An unknown or zero fixed cost prints the seconds and withholds the ratio rather than
    inventing one -- the same accurate-or-absent rule the analyze report uses for throughput.
    """
    unknown = "not recorded"
    pytest_text = f"{pytest_seconds} s" if pytest_seconds is not None else unknown
    fixed_text = f"{fixed_seconds} s" if fixed_seconds is not None else unknown
    if pytest_seconds is not None and fixed_seconds:
        ratio = f"{round(pytest_seconds / fixed_seconds)}x"
    else:
        ratio = unknown
    return "\n".join(
        [
            f"### Timing - {lane}",
            "",
            "| measure | value |",
            "|---|---|",
            f"| pytest | {pytest_text} |",
            f"| install exiftool (fixed cost) | {fixed_text} |",
            f"| **pytest / fixed cost** | **{ratio}** |",
            "",
            (
                "The ratio is runner-independent: installing exiftool is the same work every "
                "run, so when both numbers rise together the machine was slow, and when only "
                "the ratio rises the suite got slower. Recorded, never enforced - see "
                "PERFORMANCE.md 5.1."
            ),
            "",
        ]
    )


def main() -> int:
    lane = os.environ.get("TS_LANE") or os.environ.get("RUNNER_OS") or "this lane"
    block = render(
        _seconds("TS_PYTEST_SECONDS"), _elapsed("TS_EXIFTOOL_START", "TS_EXIFTOOL_END"), lane
    )
    destination = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if destination:
        try:
            with Path(destination).open("a", encoding="utf-8") as handle:
                handle.write(block)
        except OSError as exc:  # a summary that cannot be written is not worth a red lane
            print(f"could not write the timing summary: {exc}", file=sys.stderr)
            print(block)
    else:
        print(block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
