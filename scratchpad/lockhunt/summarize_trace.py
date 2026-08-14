"""Read a TRUESTILL_LOCKHUNT trace and answer one question: how long did the HOLDER hold?

Every figure in this investigation so far is a WAITER's 5 s timeout, which is the same number
whatever caused it. `schema.enter` -> `schema.exit` on the winning thread is the only measurement
that separates "the schema write is genuinely slow in the lane" from "the 5 s is something else".

Also answers, because the trace already carries it: whether all the requests in one window
resolved to the SAME catalog path, which decides whether the rig has been modelling the right
file at all.

    uv run python scratchpad/lockhunt/summarize_trace.py <trace.jsonl>
"""

from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: summarize_trace.py <trace.jsonl>", file=sys.stderr)
        return 2
    trace = Path(sys.argv[1])
    if not trace.is_file():
        print(f"no trace at {trace} - was TRUESTILL_LOCKHUNT set for the run?", file=sys.stderr)
        return 2

    records = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
    print(f"{len(records)} records from {trace}")
    if not records:
        return 1

    counts = collections.Counter(r["event"] for r in records)
    print("\nevents:")
    for event, n in counts.most_common():
        print(f"  {n:6}  {event}")

    _holds(records)
    _one_file_per_window(records)
    return 0


def _holds(records: list[dict]) -> None:
    """`schema.enter` -> `schema.exit`, matched per (pid, tid, db). THE number."""
    opened: dict[tuple, float] = {}
    holds: list[tuple[float, str]] = []
    for record in records:
        key = (record["pid"], record["tid"], record.get("db"))
        if record["event"] == "schema.enter":
            opened[key] = record["wall"]
        elif record["event"] == "schema.exit" and key in opened:
            holds.append(((record["wall"] - opened.pop(key)) * 1000, str(record.get("db"))))

    if not holds:
        print("\nNO COMPLETED SCHEMA WRITE IN THE TRACE.")
        print("  Either nothing hit the fresh-catalog path, or every holder DIED inside the")
        print("  write - which would itself be the finding, since the lock dies with it.")
        return

    times = sorted(ms for ms, _ in holds)
    print(f"\n=== THE HOLDER: time inside executescript(_SCHEMA), n={len(times)} ===")
    print(f"  min {times[0]:.2f}  median {statistics.median(times):.2f}  max {times[-1]:.2f} ms")
    print(f"  p90 {times[int(len(times) * 0.9)]:.2f} ms")
    over = [t for t in times if t >= 1000]
    print(
        f"  holds over 1000 ms: {len(over)}   over 5000 ms: {len([t for t in times if t >= 5000])}"
    )
    print("\n  slowest 10 holds (ms):")
    for ms, db in sorted(holds, reverse=True)[:10]:
        print(f"    {ms:10.2f}   {db}")
    if times[-1] < 1000:
        print(
            "\n  EVERY HOLD IS UNDER A SECOND. The 5 s waits are then NOT this write, and the\n"
            "  holder of the lock the waiters are queued behind is something else entirely."
        )


def _one_file_per_window(records: list[dict]) -> None:
    """Q20: within each 1 s window, how many distinct catalog paths were being opened?

    If six requests that should share one catalog resolve to two paths, the rig has been
    modelling the wrong file and every number taken against it is answering a different question.
    """
    windows: dict[int, set[str]] = collections.defaultdict(set)
    for record in records:
        if record["event"] == "migrate.enter":
            windows[int(record["wall"])].add(str(record.get("db")))
    if not windows:
        return
    sizes = collections.Counter(len(paths) for paths in windows.values())
    print("\n=== distinct catalog paths opened per 1 s window ===")
    for size, n in sorted(sizes.items()):
        print(f"  {size} path(s): {n} windows")
    busiest = max(windows.items(), key=lambda kv: len(kv[1]))
    if len(busiest[1]) > 1:
        print(f"  busiest window opened {len(busiest[1])} distinct catalogs:")
        for path in sorted(busiest[1])[:10]:
            print(f"    {path}")


if __name__ == "__main__":
    raise SystemExit(main())
