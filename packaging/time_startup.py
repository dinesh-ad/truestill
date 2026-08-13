"""How long a frozen truestill takes to become reachable. `(aad)`'s last ungrounded column.

**What is timed, and why this definition.** From process start to `session-url.txt` existing -
the file the app writes once the server is bound and about to be reached. That is the closest
machine-observable event to *"I double-clicked and the app came up"*, and it is the same file the
serving assertions already wait on. It is **not** time-to-first-byte and it is not time-to-window;
truestill has no window of its own.

**Cold and warm are the first run and the rest.** The first launch after a build pays for the OS
reading the bundle off disk; later launches read it from cache. For a one-folder build the gap is
the interesting number, because the published ~50 s figure people quote is for **one-file**, which
extracts to a temp directory on *every* launch and therefore never gets a warm run at all. This
builds one-folder, so that figure should not apply - measuring is how we stop guessing which way.

**Each run gets a fresh data directory.** A stale `session-url.txt` from the previous run would be
found instantly and the measurement would be zero.

⚠ **"Cold" here means FIRST RUN AFTER THE BUILD, not a cold page cache.** The build just wrote
those files, so the OS still has them; dropping caches needs privileges a runner does not give.
So the cold figure is a **lower bound** on a real first launch from a user's disk, and the honest
claim from this script is the warm number plus "the first run was not materially slower". Do not
report it as a first-launch-on-a-fresh-machine measurement.

Usage: ``python packaging/time_startup.py <exe> <label> [runs]``  (default 3)
Writes ``findings/startup-<label>.json`` and prints a line per run. Never fails the job: a startup
number is evidence, not a gate, and a step that dies takes the other artifact's number with it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

#: Poll interval. Fine enough that the number is not quantised by the loop - a 500 ms poll would
#: report every startup under half a second as half a second.
_POLL_SECONDS = 0.02

#: How long to wait before calling a launch failed rather than slow.
_TIMEOUT_SECONDS = 120.0


def _one_run(exe: Path, root: Path, index: int) -> dict[str, object]:
    data = root / f"run-{index}"
    shutil.rmtree(data, ignore_errors=True)
    data.mkdir(parents=True)
    url_file = data / "session-url.txt"

    env = {
        **os.environ,
        "TRUESTILL_DATA_DIR": str(data),
        "TRUESTILL_CACHE_DIR": str(root / f"cache-{index}"),
    }
    started = time.perf_counter()
    child = subprocess.Popen(
        [str(exe), "--port", "0", "--no-browser"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = started + _TIMEOUT_SECONDS
        while time.perf_counter() < deadline:
            if url_file.exists():
                return {"run": index, "seconds": round(time.perf_counter() - started, 3)}
            if child.poll() is not None:
                return {"run": index, "seconds": None, "error": f"exited {child.returncode}"}
            time.sleep(_POLL_SECONDS)
        return {"run": index, "seconds": None, "error": "timed out"}
    finally:
        child.kill()
        child.wait(timeout=30)


#: `<exe> <label>`; a third argument is the run count.
_REQUIRED_ARGS = 2


def main(argv: list[str]) -> int:
    if len(argv) < _REQUIRED_ARGS:
        print("usage: time_startup.py <exe> <label> [runs]", file=sys.stderr)
        return 2
    exe, label = Path(argv[0]), argv[1]
    runs = int(argv[2]) if len(argv) > _REQUIRED_ARGS else 3

    if not exe.is_file():
        print(f"::warning::no artifact at {exe} - not timed")
        return 0

    root = Path("startup-work") / label
    results = [_one_run(exe, root, i) for i in range(runs)]
    timed: list[float] = [s for r in results if isinstance(s := r.get("seconds"), float)]
    payload: dict[str, object] = {
        # The discriminator `compare_selfcheck.py` skips on. Without it a startup report
        # is a findings file with no findings, which that script correctly refuses - so a
        # measurement would fail the gate it has nothing to do with.
        "kind": "startup",
        "label": label,
        "exe": str(exe),
        "runs": results,
        "cold_seconds": results[0].get("seconds") if results else None,
        # The warm figure is the MEDIAN of the later runs, not their mean: one scheduling hiccup
        # on a shared runner moves a mean and does not move a median.
        "warm_seconds": (sorted(timed[1:])[len(timed[1:]) // 2] if len(timed) > 1 else None),
    }
    Path("findings").mkdir(exist_ok=True)
    Path(f"findings/startup-{label}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    for r in results:
        print(f"  startup {label} run {r['run']}: {r.get('seconds') or r.get('error')}")
    print(f"  startup {label}: cold {payload['cold_seconds']}s, warm {payload['warm_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
