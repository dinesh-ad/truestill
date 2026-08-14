"""THROWAWAY MEASUREMENT. Does opening a fresh catalog concurrently take seconds on a runner?

Delete this directory once the question is answered. It is not a test, it is not in `make check`,
and nothing imports it.

**The question.** CI run `31801778372` failed 29 e2e tests. All 84 `database is locked` errors
raise inside `Catalog._migrate` (`catalog.py:760/769/774`), 76 of them on its FIRST statement,
`PRAGMA user_version` - a pure read. A read waits only behind an EXCLUSIVE lock. The only writer
in view is `executescript(_SCHEMA)`, 24 statements in rollback-journal mode at `synchronous=FULL`,
run by whichever of six concurrent page-load requests wins the check-then-act at `catalog.py:769`.
So the hypothesis is: **one thread inside the schema write, five blocked behind it, all expiring
together at `sqlite3.connect`'s 5 s default.** That explains the observed shape - 84 waits at
5009-5597 ms with NOTHING between 148 ms and 5009 ms.

**Why it has to run here rather than locally.** The same six-way contention measures **36.85 ms**
on the author's NVMe. If that number held on a runner the hypothesis would be dead. It is not
trusted, because fsync is exactly where a GitHub virtual disk diverges from consumer NVMe, and
every statement here is a durable transaction.

**What makes this falsifiable rather than a number that agrees with me.** Four things, and the
run is worthless without all four:

1. **The pragmas are read off a live `Catalog` connection**, not assumed and not read off a
   fresh `sqlite3.connect` - those are different questions, and only the first one is the app's.
2. **fsync is measured against its own control**, timed loops with and without. A fast fsync is
   not evidence of a fast disk; it is evidence of write-back caching, in which case THIS RUN DOES
   NOT TEST THE HYPOTHESIS and says so in capitals. A small number with no durability check is
   the same non-measurement as the 36.85 ms it exists to replace.
3. **Per-thread times, not a total.** The prediction has a shape: one fast, five near-identical
   slow. Six uniformly slow threads would mean something else is the mechanism, and a total
   hides the difference.
4. **A single-thread control on the same machine**, so the contended figure is compared against
   this disk rather than against the Dell.

The six openers are released by a `threading.Barrier`, so the race is real rather than hoped for:
without it the scheduler decides whether they overlap, and a run where thread 1 finished migrating
before thread 2 started would report 6 ms and prove nothing. In production the six requests arrive
within 3 ms of each other, which is what the barrier models.
"""

from __future__ import annotations

import contextlib
import os
import platform
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from subprocess import DEVNULL

import anyio
import anyio.to_thread
from starlette.concurrency import run_in_threadpool
from truestill_core.catalog import _SCHEMA, Catalog

#: Six, because that is how many catalog-touching requests the page fires on load.
OPENERS = 6

#: The sweep. One fresh file per level, so each level pays the full migration.
#:
#: ⚠ **48 is beyond anything the product can do.** Starlette's threadpool limiter is 40, so the
#: server can never have more than 40 opens in flight whatever arrives. The high levels are an
#: upper bound on the mechanism, not a model of it - the limiter is raised to match, and that
#: raising is itself printed so nobody reads 48 as a thing that happens.
LEVELS = (1, 6, 12, 24, 48)

#: The solo baseline is repeated because ONE sample was not one. The first run reported a control
#: of 31.60 ms against a contended winner of 28.23 ms - contention apparently making the winner
#: faster, which is scheduling noise on a small runner and not a queue. A single measurement
#: could not tell those apart, so it did not measure contention at all.
CONTROL_REPEATS = 7

#: `sqlite3.connect`'s default `timeout=5.0`, in ms. The number every observed wait lands on.
TIMEOUT_MS = 5000.0

#: Below this, an fsync did not reach stable storage and the disk is answering from cache.
WRITE_BACK_MS = 0.05

#: Local baseline, dell-g5505, 2026-08-14. ⚠ ON tmpfs, NOT on the NVMe it was first attributed
#: to: `tempfile.mkdtemp()` follows TMPDIR to /tmp, which is tmpfs here, and the `df -T` that
#: named the NVMe was run against the checkout instead. The local numbers are RAM speed with no
#: durable write in them at all - which is why `_identity` now prints `df -T` for the directory
#: actually used, and why nothing local can falsify the hypothesis.
LOCAL = "fsync 0.002 ms | executescript(_SCHEMA) 1.64-2.05 ms | 6 contended opens 36.85 ms total"


def main() -> None:
    workdir = Path(tempfile.mkdtemp(prefix="lockhunt-"))
    _identity(workdir)
    _pragmas_in_force(workdir / "pragmas.sqlite")
    _fsync(workdir)
    _schema_write(workdir)

    solo = _solo_baseline(workdir)
    idle = _sweep(workdir, "IDLE")
    with _background_load(workdir):
        loaded = _sweep(workdir, "UNDER LOAD")

    print(f"\n=== CURVE (solo median {solo:.2f} ms, measured idle) ===")
    print(f"  {'openers':>8}  {'idle ms':>10}  {'loaded ms':>10}  {'load x':>7}")
    for (level, quiet), (_, busy) in zip(idle, loaded, strict=True):
        print(f"  {level:>8}  {quiet:>10.2f}  {busy:>10.2f}  {busy / quiet:>6.1f}x")
    reached = [level for level, worst in loaded if worst >= TIMEOUT_MS]
    if reached:
        print(
            f"\n  *** REACHES THE {TIMEOUT_MS:.0f} ms TIMEOUT UNDER LOAD AT: {reached} ***\n"
            "  *** A descheduled holder keeps EXCLUSIVE while it is off-cpu, so the wait is\n"
            "  *** starvation rather than slow work - which is the observed shape. ***"
        )
    else:
        print(
            f"\n  NO LEVEL REACHES {TIMEOUT_MS:.0f} ms, LOADED OR IDLE. Contention on one file does\n"
            "  not produce the observed wait even with the cpus oversubscribed, and the holder\n"
            "  is something this rig still does not model."
        )
    print(f"\nlocal baseline for comparison: {LOCAL}")


def _sweep(workdir: Path, label: str) -> list[tuple[int, float]]:
    print(f"\n=== SWEEP {label}: {LEVELS} openers, one fresh file each, released together ===")
    worst: list[tuple[int, float]] = []
    for level in LEVELS:
        print(f"\n--- {label}, {level} opener{'s' if level > 1 else ''} ---")
        results = _race(workdir / f"{label.split(maxsplit=1)[0].lower()}{level}.sqlite", level)
        _report(results)
        worst.append((level, max(ms for ms, _ in results)))
    return worst


@contextlib.contextmanager
def _background_load(workdir: Path) -> Iterator[None]:
    """Oversubscribe the cpus and keep the disk busy, for the duration of the block.

    **The hypothesis this exists to test.** SQLite's EXCLUSIVE lock is held by a *thread*, not by
    the kernel's scheduler - a thread descheduled midway through `executescript` keeps the lock
    for as long as it is off-cpu. On a 4-core runner also running a browser, a video recorder,
    tracing and up to nine uvicorn servers, the holder is not slow, it is **starved**. An idle
    rig cannot see that, which is why the numbers so far may be measuring the wrong machine.

    **Subprocesses, not threads.** A Python busy-loop in a thread holds the GIL and burns ONE
    core no matter how many of them there are, so a threaded version of this would have looked
    like load and produced none. Separate interpreters genuinely occupy the cpus.
    """
    burners = max(2, (os.cpu_count() or 2) * 2)
    spin = "while True: pass"
    writer = (
        "import os,tempfile\n"
        f"f=open({str(workdir / 'load.probe')!r},'wb')\n"
        "while True:\n f.write(b'x'*4096); f.flush(); os.fsync(f.fileno())\n"
    )
    procs = [
        subprocess.Popen([sys.executable, "-c", spin], stdout=DEVNULL, stderr=DEVNULL)
        for _ in range(burners)
    ]
    procs.append(subprocess.Popen([sys.executable, "-c", writer], stdout=DEVNULL, stderr=DEVNULL))
    print(
        f"\n*** BACKGROUND LOAD ON: {burners} cpu burners + 1 fsync writer on {os.cpu_count()} cpus ***"
    )
    try:
        time.sleep(1.0)  # let them actually get scheduled before anything is timed
        yield
    finally:
        for proc in procs:
            proc.kill()
        for proc in procs:
            proc.wait()
        print("\n*** BACKGROUND LOAD OFF ***")


def _solo_baseline(workdir: Path) -> float:
    """One opener, repeated, because a single sample cannot be told apart from noise."""
    times = [_race(workdir / f"solo{i}.sqlite", 1)[0][0] for i in range(CONTROL_REPEATS)]
    print(f"\nSOLO baseline, {CONTROL_REPEATS} fresh files, one opener each:")
    print(f"  ms: {', '.join(f'{t:.2f}' for t in sorted(times))}")
    print(f"  median {statistics.median(times):.2f}  min {min(times):.2f}  max {max(times):.2f}")
    return statistics.median(times)


def _identity(workdir: Path) -> None:
    print(f"runner:  {platform.node()}  {platform.system()} {platform.release()}")
    print(f"cpus:    {os.cpu_count()}")
    print(f"python:  {platform.python_version()}  sqlite {sqlite3.sqlite_version}")
    print(f"workdir: {workdir}")
    # The filesystem of the directory actually used, not of the checkout - pytest's `tmp_path`
    # and this script both follow TMPDIR, and on a runner that is not where the repo lives.
    for label, path in (("workdir", workdir), ("TMPDIR", os.environ.get("TMPDIR", "/tmp"))):
        out = subprocess.run(
            ["df", "-T", str(path)], capture_output=True, text=True, check=False
        ).stdout
        print(f"df -T {label}: {out.strip().splitlines()[-1] if out.strip() else '(none)'}")
    anyio.run(_print_limiter)  # only readable from inside a loop


async def _print_limiter() -> None:
    """How many of the openers can actually be in a thread at once. Six blocked on a limiter of
    four would look exactly like six blocked on a lock, and only one of those is this bug."""
    print(f"anyio thread limiter: {anyio.to_thread.current_default_thread_limiter().total_tokens}")


def _pragmas_in_force(db: Path) -> None:
    """Read from a live `Catalog`, because that is the connection the app actually serves on.

    A fresh `sqlite3.connect` would answer "what are the defaults", which is a different question
    and the one that lets an assumption survive a measurement.
    """
    with Catalog(db) as catalog:
        conn = catalog._conn  # the app's own connection is the whole point of this read
        values = {
            name: conn.execute(f"PRAGMA {name}").fetchone()[0]
            for name in ("journal_mode", "synchronous", "busy_timeout")
        }
    print("\npragmas IN FORCE on a live Catalog connection:")
    for name, value in values.items():
        print(f"  {name:14} {value}")


def _fsync(workdir: Path) -> None:
    """Time fsync against its own control. The ratio is the finding, not the absolute."""
    with_sync = _write_loop(workdir / "sync.probe", sync=True)
    without = _write_loop(workdir / "nosync.probe", sync=False)
    print(f"\nfsync:        {with_sync:.4f} ms/write (n=200)")
    print(f"no fsync:     {without:.4f} ms/write (n=200)")
    print(f"ratio:        {with_sync / without if without else float('inf'):.1f}x")
    if with_sync < WRITE_BACK_MS:
        print(
            f"\n  *** WARNING: fsync costs {with_sync:.4f} ms, under the {WRITE_BACK_MS} ms floor "
            "for a real durable write. ***\n"
            "  *** This disk is answering from write-back cache, so a fast contended figure "
            "below is NOT evidence against the hypothesis - the run does not test it. ***"
        )


def _write_loop(path: Path, *, sync: bool) -> float:
    handle = open(path, "wb")
    try:
        start = time.perf_counter()
        for _ in range(200):
            handle.write(b"x")
            handle.flush()
            if sync:
                os.fsync(handle.fileno())
        return (time.perf_counter() - start) / 200 * 1000
    finally:
        handle.close()


def _schema_write(workdir: Path) -> None:
    times = []
    for i in range(5):
        conn = sqlite3.connect(str(workdir / f"schema{i}.sqlite"))
        start = time.perf_counter()
        conn.executescript(_SCHEMA)
        conn.commit()
        times.append((time.perf_counter() - start) * 1000)
        conn.close()
    statements = len([s for s in _SCHEMA.split(";") if s.strip()])
    print(f"\nexecutescript(_SCHEMA), {statements} statements, fresh file:")
    print(f"  {min(times):.2f}-{max(times):.2f} ms  (n=5)")


def _race(db: Path, openers: int) -> list[tuple[float, str]]:
    """Open ``db`` from ``openers`` threads released simultaneously. Returns (ms, outcome)."""
    # Generous: at 48 openers every one of them may sit out a full 5 s busy timeout before the
    # barrier's peers are all through, and a barrier that expires reports "measured nothing"
    # rather than a small number, which is the failure mode worth avoiding.
    barrier = threading.Barrier(openers, timeout=180)
    results: list[tuple[float, str]] = []

    def opener() -> tuple[float, str]:
        # Wait BEFORE the clock starts: what is being timed is the open, not the scheduling.
        try:
            barrier.wait()
        except threading.BrokenBarrierError:  # pragma: no cover - only if a thread never arrives
            return (0.0, "barrier broke: the threads never overlapped, this run measured nothing")
        start = time.perf_counter()
        try:
            with Catalog(db) as catalog:
                catalog.schema_version
            outcome = "ok"
        except Exception as error:  # a failure IS the measurement here
            outcome = f"{type(error).__name__}: {error}"
        return ((time.perf_counter() - start) * 1000, outcome)

    async def run() -> None:
        # Starlette's default is 40. Above it the barrier would DEADLOCK rather than measure,
        # because the 41st opener never gets a thread to arrive at the barrier with - so the
        # limiter is raised to the level and the raise is announced. Reading a 48-opener figure
        # as something the server could produce is exactly the misreading this guards against.
        limiter = anyio.to_thread.current_default_thread_limiter()
        if openers > limiter.total_tokens:
            print(f"  (thread limiter raised {limiter.total_tokens} -> {openers} to seat them all)")
            limiter.total_tokens = openers

        async def one() -> None:
            results.append(await run_in_threadpool(opener))

        async with anyio.create_task_group() as group:
            for _ in range(openers):
                group.start_soon(one)

    anyio.run(run)
    return results


def _report(results: list[tuple[float, str]]) -> None:
    times = sorted(ms for ms, _ in results)
    print(f"  per-thread ms: {', '.join(f'{t:.2f}' for t in times)}")
    print(f"  slowest:       {max(times):.2f} ms")
    for ms, outcome in sorted(results):
        if outcome != "ok":
            print(f"  FAILED at {ms:.2f} ms: {outcome}")
    if len(times) < 2:
        return

    # The discriminator, stated before the label so the label can be argued with.
    # Predicted shape: one winner inside executescript, the rest blocked behind it and released
    # together - so a large gap at the front and a tight tail. Six uniformly slow threads would
    # mean the cost is per-thread work, not a lock, and the hypothesis would be wrong.
    gap = times[1] / times[0] if times[0] else float("inf")
    tail = times[1:]
    spread = (max(tail) - min(tail)) / statistics.median(tail) if statistics.median(tail) else 0.0
    print(f"  gap (2nd/1st): {gap:.1f}x   tail spread: {spread:.2f}")
    print("  criterion: gap >= 3x AND tail spread <= 0.5  =>  one writer, the rest blocked")
    if gap >= 3 and spread <= 0.5:
        print("  shape: ONE FAST, REST BLOCKED - consistent with the lock hypothesis")
    else:
        print("  shape: NOT one-fast-rest-blocked - the mechanism is something else")


if __name__ == "__main__":
    main()
