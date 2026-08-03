"""Watch the ground a long write is standing on, without crying wolf about it.

Two hazards, both observed on a real 192 GB migration, both invisible to the run itself:

* **The drive drops.** A cloud FUSE mount that dies under sustained load leaves its mountpoint
  as an ordinary empty directory. The mount table is not a reliable witness either - the same
  migration found a dead mount lingering there with no process behind it, listing nothing.
* **The local disk fills.** The cloud client caches everything written to it.
  `preflight_destination` measures the *destination*, which on a mounted drive is the remote
  free space, while the disk that actually fills is the local one. Nothing points at the cloud
  client, which is why this costs people hours.

**Crying wolf is the failure mode to fear, more than either hazard.** A check that stops a
healthy thirty-minute run gets switched off and takes its real coverage with it. So a
slow-but-successful answer is not a bad answer, and a bad answer has to repeat.

**Why this is not `DestinationDevice`, and why the two must not be unified.** That guard sits
in front of a `mkdir` and **fails closed**: a refused write costs a re-run, while a rebuilt
folder tree costs the local disk, so one bad reading is enough there. This one is periodic and
advisory, so it **fails open until proven**: stopping a healthy run on one transient would be
the cry-wolf above. Different jobs, different costs of being wrong, deliberately different
postures.

**Cost, measured, so nobody re-derives whether it is affordable** (`docs/PERFORMANCE.md`):
``shutil.disk_usage`` 1.96 us, ``read_marker`` 21.18 us, a FUSE ``stat`` ~600 us. At the tick
below that is **~0.2 s over a thirty-minute run**; per file it would be ~20 s on a 32,628-file
FUSE library, which is the entire tier-0 budget spent again.

**The honest limit:** this detects the ground *moving*. It does not detect a mount that is
silently returning *wrong data* rather than disappearing. There is no evidence that happens and
nothing here should be read as covering it.
"""

from __future__ import annotations

import errno
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

#: Seconds between checks. **A judgement, not a measurement** - no dropping mount was available
#: to time this against, and one cannot be staged. Small enough that a run notices within a few
#: files, large enough that the cost is noise. Recorded the same way
#: `insights.SLOW_PERCEPTUAL_WARN_SHARE` is: whoever revisits should know there is no data here.
TICK_SECONDS = 5.0

#: Consecutive bad readings before the drive is declared gone. **Judgement, not measurement.**
STRIKES_TO_STOP = 3

#: ...and they must also span this long, so three checks inside one hiccup are not three
#: opinions. **Judgement, not measurement.** With the tick above this needs four checks.
STRIKE_SPAN_SECONDS = 15.0

#: The local disk must keep at least this much free whatever else is true. A full root breaks
#: far more than Truestill; two gigabytes keeps a desktop usable.
ABSOLUTE_FLOOR_BYTES = 2 * 1024**3

#: ``errno`` values meaning the path is genuinely not there, as opposed to momentarily
#: unhappy. Split by ``errno`` rather than message text, for the reason `scan._reason_for`
#: gives: a message is free to be reworded and an ``errno`` is not.
_GONE_ERRNOS = frozenset({errno.ENOENT, errno.ENOTCONN, errno.ENODEV, errno.ESTALE})


@dataclass(frozen=True, slots=True)
class DeviceReading:
    """What a device read actually established.

    ``definite`` is the whole point: a transient ``EIO`` and a vanished mount both fail to
    produce a device id, and treating them alike is what makes a check cry wolf.
    """

    device: int | None
    definite: bool


@dataclass(frozen=True, slots=True)
class HealthVerdict:
    """Carry on, or stop and say this."""

    ok: bool
    detail: str = ""


def read_device(path: Path) -> DeviceReading:
    """The filesystem device for ``path``, and whether the answer can be trusted."""
    try:
        return DeviceReading(path.stat().st_dev, definite=True)
    except OSError as exc:
        return DeviceReading(None, definite=exc.errno in _GONE_ERRNOS)


def free_bytes(path: Path) -> int:
    """Free bytes on the filesystem holding ``path``; ``0`` when it cannot be read."""
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0


def _gb(value: int) -> str:
    return f"{value / 1e9:.2f} GB"


class RunHealth:
    """Periodic liveness for one long write. Construct per run; ask on every file.

    ``local_probe`` must be a path on the **local** disk - the catalog's directory, which
    `app_paths` guarantees is local. Probing the destination would measure the remote free
    space, which is the mistake `preflight_destination` already makes and the reason a cache
    can fill a disk while a run reports plenty of room.
    """

    def __init__(
        self,
        *,
        root: Path,
        local_probe: Path,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._root = root
        self._probe = local_probe
        self._clock = clock
        #: ``None`` until a real device is seen - see :meth:`_check_device`, which is where
        #: that matters. (`read_device` never reports a device *and* uncertainty, so a
        #: non-``None`` reading is always one worth keeping.)
        self._baseline_device = read_device(root).device
        self._baseline_free = free_bytes(local_probe)
        self._due = clock() + TICK_SECONDS
        self._strikes = 0
        self._first_strike_at = 0.0

    def check(self, *, largest_remaining: int, written_bytes: int) -> HealthVerdict:
        """Carry on, or stop. Returns immediately unless the tick has elapsed."""
        now = self._clock()
        if now < self._due:
            return HealthVerdict(ok=True)
        self._due = now + TICK_SECONDS

        space = self._check_space(largest_remaining, written_bytes)
        if not space.ok:
            return space
        return self._check_device(now)

    def _check_space(self, largest_remaining: int, written_bytes: int) -> HealthVerdict:
        """One reading is enough: a local read does not fail transiently, and waiting for three
        would mean watching the disk fill while declining to say so."""
        free = free_bytes(self._probe)
        floor = max(ABSOLUTE_FLOOR_BYTES, largest_remaining * 2)
        if free >= floor:  # compared in BYTES; truncating to GB is what let 15.9 read as 15
            return HealthVerdict(ok=True)
        fell = max(0, self._baseline_free - free)
        return HealthVerdict(
            ok=False,
            detail=(
                f"Stopped: this computer's disk is nearly full ({_gb(free)} free). "
                f"Local free space fell by {_gb(fell)} while this run wrote {_gb(written_bytes)} "
                f"to the drive. Cloud sync clients keep a local cache of what you write; check "
                f"your client's cache or minimum-free-space setting, or free space on this "
                f"disk, then run again to continue."
            ),
        )

    def _check_device(self, now: float) -> HealthVerdict:
        """Three consecutive bad readings, spanning the window, before declaring anything."""
        reading = read_device(self._root)
        if self._baseline_device is None:
            # **Never let an absence serve as the baseline.** A `None` there would mean two
            # things at once - "not yet established" and "the device id is None" - and every
            # later `None` reading would compare equal to it, so a watcher built during one bad
            # moment would stay silently switched off for the whole run. `DestinationDevice`
            # latches on the first real sighting for the same reason; the two differ in what
            # they do afterwards, not in what counts as a baseline.
            #
            # Until one is latched this stands down rather than striking: the guard detects the
            # ground *moving*, and with nothing ever seen there is no movement to detect. A run
            # whose destination was never readable fails at the write, per file, with the real
            # ``OSError`` - which names the file, where a stop here would not.
            self._baseline_device = reading.device
            return HealthVerdict(ok=True)
        healthy = reading.definite and reading.device == self._baseline_device
        if healthy:
            self._strikes = 0
            return HealthVerdict(ok=True)

        if self._strikes == 0:
            self._first_strike_at = now
        self._strikes += 1
        spanned = now - self._first_strike_at
        if self._strikes < STRIKES_TO_STOP or spanned < STRIKE_SPAN_SECONDS:
            return HealthVerdict(ok=True)
        return HealthVerdict(
            ok=False,
            detail=(
                f"Stopped: the drive at {self._root} stopped answering, and has not come back "
                f"after {self._strikes} checks over {spanned:.0f} seconds. It looks like it was "
                f"disconnected or unmounted. Nothing was left half-written; reconnect it and "
                f"run again to continue from here."
            ),
        )
