"""Drive identity via a marker file.

A destination drive is identified by a marker file at its root -- ``.truestill-drive.json`` --
carrying a truestill-minted ``uuid4``, a human label, and a creation timestamp. Identity is the
marker, **never** the mount path: drive letters and mount points change per session and OS,
and filesystem UUIDs are inconsistent across filesystems (NTFS/FAT serials) and copied by
cloning. A marker's uuid is OS/filesystem-independent, collision-free, and travels with the
data. See ``docs/drive-identity-research.md``.

Cloning a drive copies the marker too, so a clone shares identity until it is deliberately
re-labelled (a fresh uuid) -- correct, since clones are identical at clone time.

Legacy marker compatibility (vaeon -> truestill rename)
-------------------------------------------------------
Drives initialised before the rename carry ``.vaeon-drive.json``. Those drives must keep
working, so:

* **Read falls back.** :func:`read_marker` prefers the canonical name and falls back to any
  name in :data:`LEGACY_MARKER_NAMES`. If both exist, the **canonical file wins** -- a single,
  documented precedence, never a merge.
* **A read never writes.** :func:`read_marker` runs on every filesystem browse in the app and
  on preview/dry-run paths, where writing would break the "planning writes nothing" invariant
  and touch drives that may be mounted read-only. Upgrading is always an explicit act:
  :func:`write_marker` / :func:`create_marker`, or :func:`upgrade_marker`.
* **Identity is preserved verbatim.** An upgrade copies ``uuid``, ``label`` and ``created``
  unchanged. The uuid is the foreign key behind the catalog's ``drives`` / ``file_copies``
  tables; re-minting one would orphan every recorded copy and silently under-report how many
  places a file is safe in -- the exact failure this product exists to prevent.
* **The legacy file is kept, not deleted.** Deleting a file on a user's drive is what the
  copy-only invariant forbids, and retaining it (~100 bytes) means an older build reading the
  legacy name and a current build reading the canonical one agree on identity.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, NamedTuple, Protocol
from uuid import uuid4

from truestill_core.drive_unwritable import explain_unwritable_drive

#: Marker filename written at a drive's root. The only name this code ever writes.
MARKER_NAME = ".truestill-drive.json"

#: Marker filenames still honoured on read, newest first. Never written.
LEGACY_MARKER_NAMES: tuple[str, ...] = (".vaeon-drive.json",)


@dataclass(frozen=True, slots=True)
class DriveMarker:
    """The identity of a destination drive, as stored in its marker file."""

    uuid: str
    label: str
    created: str  # ISO-8601, UTC

    def to_json(self) -> str:
        return json.dumps(
            {"uuid": self.uuid, "label": self.label, "created": self.created}, indent=2
        )


@dataclass(frozen=True, slots=True)
class MarkerWrite:
    """What a marker write did. **Never an exception.** `(aek)`

    Shaped like `decisions.WriteOutcome` on purpose: the two drive writes this product performs
    answer the same question and should not need two shapes to answer it in.
    """

    written: bool
    path: Path | None = None
    #: Plain words for a person, when the drive would not take it. `None` on success.
    error: str | None = None


def marker_path(root: Path) -> Path:
    """The canonical marker path for ``root`` -- where a write would go."""
    return root / MARKER_NAME


def existing_marker_path(root: Path) -> Path | None:
    """The marker file actually present at ``root``: canonical first, then legacy names.

    Returns ``None`` when the drive carries no marker at all. Purely a lookup -- it never
    creates, moves or removes anything.
    """
    canonical = marker_path(root)
    try:
        if canonical.is_file():
            return canonical
        for name in LEGACY_MARKER_NAMES:
            legacy = root / name
            if legacy.is_file():
                return legacy
    except OSError:  # unreadable/disconnected mount -- treat as "no marker"
        return None
    return None


@dataclass(frozen=True, slots=True)
class DriveLocation:
    """What a path turned out to be, when a command wanted a drive root.

    Three outcomes, and telling them apart is the whole point: the path **is** a drive root, the
    path is **inside** one (so there is a correction to offer), or there is no drive above it at
    all (so registration is the answer). Reporting all three as "is the drive connected?" asks a
    question whose answer is plainly yes, and leaves the user with nothing to do.
    """

    given: Path
    root: Path | None = None
    marker: DriveMarker | None = None

    @property
    def is_root(self) -> bool:
        return self.marker is not None and self.root == self.given

    @property
    def is_inside(self) -> bool:
        """The path sits below a drive root - the case that used to read as 'not connected'."""
        return self.marker is not None and self.root != self.given


class DriveReach(StrEnum):
    """Whether a registered drive is here right now. **Three states, not a boolean.**

    A boolean would have to fold ``UNKNOWN`` into one of the other two, and both folds lie. Read
    as connected it invents a drive that may not be plugged in; read as offline it tells someone
    their backup drive is missing when the truth is only that truestill has never recorded where
    it lives. The alarming reading is the worse one for a custody tool, and the honest answer -
    *we do not know* - is available, so it is reported.

    ``UNKNOWN`` is not a corner case: a drive registered and used entirely from the CLI has no
    remembered path until something records one, so it is the *normal* state for that user.
    """

    CONNECTED = "connected"  # the remembered path is there and carries this drive's marker
    OFFLINE = "offline"  # we know where it was; it is not there now
    UNKNOWN = "unknown"  # no remembered path, so there is nothing to check


def drive_path_hint(uuid: str) -> str:
    """Settings key for where a drive was last seen mounted.

    A *hint*, never identity: a drive that remounts elsewhere is the same drive, and this key is
    simply stale until something sees it again. It lives in core rather than in the app because
    both front-ends need it - the CLI cannot import `truestill_app` (`IMPLEMENTATION_STANDARDS`
    §2), and a second key spelled the same way in two packages is how they drift apart.
    """
    return f"path_hint.drive.{uuid}"


class _SettingsWriter(Protocol):
    """The one thing :func:`remember_drive_path` needs. See :class:`_SettingsReader` for why."""

    def set_local_setting(self, key: str, value: str) -> None: ...


def remember_drive_path(settings: _SettingsWriter, uuid: str, path: Path | str) -> str:
    """Record where a drive was last seen. **The stored path is always absolute.** Returns it.

    🔑 **The single home for this write**, which is the fix rather than a tidiness preference.
    **Seven** call sites each turned a user-supplied path into a string with `str(...)`, none made
    it absolute, and two spelled the setter differently from the other five - so
    `truestill organize src dest` stored `dest`, a path whose meaning depends on the working
    directory of whoever reads it next. `(ahu)`

    **`Path.absolute()`, and both alternatives were rejected for stated reasons.** `resolve()`
    follows symlinks, which is wrong for removable media: a user reaching a drive through a stable
    `~/backup-drive` symlink would have the volatile mount point stored instead, and the hint would
    go stale the next time that volume was assigned a different node. Drive identity is the marker
    uuid and never the path - :func:`drive_reach` checks the marker - so canonicalising through
    symlinks buys nothing and costs the stable handle. `os.path.abspath` avoids symlinks but
    rewrites `..` **lexically**, which is unsound when a `..` crosses one: `a/link/../b` is not
    `a/b` on disk. `absolute()` does neither - it prepends the working directory and changes
    nothing else, which is exactly and only what was missing.

    ⚠ **So a stored hint may contain `..`** when the user typed one. Cosmetic: it is absolute,
    `read_marker` opens it, and it names the place the user named. ⚠ **ruff PTH100 suggests
    `resolve()` as the replacement for `abspath()`, which is not an equivalence** - a known
    upstream defect in that rule, and neither call is used here.

    ⚠ **`set_local_setting`, which `(afc)` already ruled.** A `path_hint.` write through
    `set_setting` marks the catalog dirty, and a dirty close publishes the decisions document to
    every reachable drive - so recording where a drive was found would turn a read-only command
    into one that writes to the user's disks.
    """
    absolute = str(Path(path).absolute())
    settings.set_local_setting(drive_path_hint(uuid), absolute)
    return absolute


#: Days after which the custody claim SOFTENS and names its age. `(abg)` Stage 3.
#:
#: **A judgement informed by an industry cadence, not a measurement**, recorded the way
#: `run_health.TICK_SECONDS` is. The 3-2-1 rule is written 3-2-1-1-0 in current practice and the
#: trailing 0 is *zero errors* - restores actually tested rather than assumed; CISA carries the
#: form in the joint #StopRansomware Guide. The cadence those write-ups converge on is
#: verification monthly at file level and a deeper check quarterly, and 30 and 90 are those two
#: periods. A claim is not stale on the day it falls due; it is stale when a whole period has
#: been missed.
#:
#: Nothing was measured: no library was left unchecked to watch its claim stop being true, and
#: none could be - the observation takes months and the answer would be one library's. Whoever
#: revisits should know there is no data behind either number.
CUSTODY_SOFTENS_AFTER_DAYS = 30

#: Days after which it says so firmly. **Judgement, not measurement** - see above.
CUSTODY_STALE_AFTER_DAYS = 90


class CustodyTier(StrEnum):
    """How old the oldest DATED place is. **Three tiers, and none of them is an alarm.**

    A copy checked in June is probably fine, so `at-risk` stays reserved for real exposure and
    firmness lives in the wording alone. The tier is what legitimately changes with time - the
    date beside it does not, which is why the date is never replaced by a relative form.

    ⚠ **Never-checked is NOT a tier**, it is a separate state carried by
    :attr:`CustodyFreshness.never_checked`. It is a different claim - not *"checked long ago"*
    but *"never looked at"* - it has no age for a threshold to act on, and it already pre-empts
    every date branch on every surface. Folding it in would make it a severity, which it is not.
    """

    FRESH = "fresh"  # under the softening threshold, or nothing dated to be old
    SOFTENING = "softening"  # a monthly cadence has been missed
    STALE = "stale"  # a quarterly one has


class CustodyFreshness(NamedTuple):
    """How old the custody claim is, and which places have never been looked at.

    `(abg)`. The catalog reports history as if it were state: a `file_copies` row is a true
    statement about the moment it was written and is read as a true statement about now. This
    carries the age of that statement to the surfaces that make the claim.

    **Pure, and it touches nothing.** It reads rows the caller already has - `last_verified` has
    been on `drives` all along and is already shown per drive; it simply never reached the number
    a person reads. No disk access, no query, no freshness *tracking* being added.

    **Lives in core because both surfaces make the claim.** The CLI's `status` and the app's
    custody strip would otherwise each grow their own version, which is the drift §4 names.
    """

    #: ⚠ **`checked_at` WAS HERE AND WAS REMOVED 2026-08-19, WITH ITS RULE INTACT.** It held the
    #: oldest check across the counted places, and went `None` the moment any of them had never
    #: been checked, because **no single date is true of the whole claim**. That rule survives the
    #: field: it is now carried by :attr:`never_checked` being non-empty, and by every surface
    #: leading with that rather than with a date. What the field added on top was a second
    #: encoding of the same fact - `checked_at == dated_at if not never_checked else None` - and
    #: after Stage 3 gave both surfaces `dated_at` to read, nothing read it at all. A value
    #: computed and read by nobody is how the next divergence gets in; `(aeb)` is the same shape
    #: one level up, where two names for one path produced a false claim because nothing forced
    #: them to agree.
    #:
    #: Counted places never checked, **named unambiguously** - see :func:`distinguishing_names`.
    #: Named, not counted: the name is the only clue a reader has to what happened, which is also
    #: why an ambiguous one is worse than none. `(acr)`.
    never_checked: tuple[str, ...]
    #: The oldest check across the places that HAVE one, **which an unchecked place does not
    #: blank**. That is the whole point of it: without this a library with one never-checked
    #: drive can say nothing whatever about its other drives - the shape of the maintainer's own
    #: catalog, and the reason the tiers below would otherwise never fire. It answers *"how old
    #: is the oldest thing we did look at"*; whether the claim as a whole is backed is answered
    #: by :attr:`never_checked` being empty. `(abg)` Stage 3.
    dated_at: str | None = None
    #: Whole days from :attr:`dated_at` to now, or `None` when nothing is dated.
    dated_days: int | None = None
    #: The tier of the OLDEST dated place - per-drive tiering, reported at the claim.
    tier: CustodyTier = CustodyTier.FRESH


class _DriveRowLike(Protocol):
    """What `was_ever_checked` needs of a row, which `sqlite3.Row` and `dict` both satisfy.

    Narrower than `Mapping`: `sqlite3.Row` is not one, and typing it as such would be a claim the
    production callers falsify.
    """

    def keys(self) -> Iterable[str]: ...
    def __getitem__(self, key: str) -> Any: ...


def was_ever_checked(drive: _DriveRowLike) -> bool:
    """Whether anything has ever LOOKED at this drive's copies. `(aes)`

    ⚠ **NOT the same question as `drives.last_verified`, and conflating them is the defect this
    exists to end.** That stamp is derived by `Catalog.refresh_drive_verified` as *"MIN over the
    copies, and NULL the moment any of them has never been confirmed"* - `(abg)` Stage 2, and it
    is right. It answers **is this drive wholly confirmed, and as of when**. NULL therefore covers
    two situations a reader must never see merged: *nobody has looked* and *we looked and found
    gaps* - missing, unreadable, unverifiable, or cancelled part way through.

    Soak two measured the merge: seven files deleted by hand, `verify` reporting `MISSING: 7` and
    naming each, and `status` in the same minute saying *"Truestill has not looked since the copy
    was written"* over a catalog holding 2,262 confirmed copies and 7 missing ones.

    **The evidence was already in the row.** `Catalog.list_drives` computes `confirmed_count` and
    `missing_count` per drive, and both callers of `custody_freshness` pass its rows - so this
    needs no new column, no third value and no second query. It was simply not read.

    **`confirmed_count` alone will not do**, which is the trap `(aej)` recorded at the one site it
    fixed: a copy can be unconfirmed **without** being missing, so a run cancelled at the first
    file leaves confirmations and no missing marks, while a drive whose every copy vanished leaves
    the reverse. Either is a look.

    A row that does not carry the aggregates answers **False**: a caller who cannot show evidence
    of a look does not get to claim one.

    ⚠ **`keys()` rather than `.get()`, because `sqlite3.Row` has no `.get()`** - it is a mapping
    in the ways that matter and not in that one. Both production callers pass `Catalog.list_drives`
    rows, so a `dict`-only implementation type-checks, passes a `dict`-based unit test, and raises
    `AttributeError` on every real run. Caught here only because the tests either side of this one
    go through `custody_freshness` with real rows.
    """
    available = set(drive.keys())
    return any(bool(drive[key]) for key in ("confirmed_count", "missing_count") if key in available)


def custody_freshness(
    settings: _SettingsReader,
    holding: Iterable[Any],
    registered: Iterable[Any],
    *,
    now: datetime | None = None,
) -> CustodyFreshness:
    """Freshness for the drives that HOLD copies, naming them unambiguously.

    Filtering `holding` is the caller's job - a registered drive with no copies is not one of the
    places the claim is about, so it can neither supply the date nor withhold it.

    **`registered` is every known drive, and it is a SEPARATE argument because a collision is not
    a property of the sentence - it is a property of what the user owns.** Judging collisions among
    `holding` alone leaves a hole: with two drives called `Morrowkeep` and only one of them never
    checked, the warning would print a bare `Morrowkeep` and the reader still could not tell which.
    Passing the wider set costs nothing - `library_status` has already fetched these rows - and
    closes it.

    **`now` is injectable so a tier is never a function of when the suite happened to run.** The
    age below is the one thing here that depends on the clock, and a test that hardcodes a
    verification date would otherwise cross a threshold by calendar - green today, red on a date
    with no commit behind it. Production passes nothing and gets `datetime.now(UTC)`.
    """
    rows = list(registered)
    named = dict(
        zip(
            (str(r["uuid"]) for r in rows),
            distinguishing_names(settings, [(str(r["uuid"]), str(r["label"])) for r in rows]),
            strict=True,
        )
    )
    # ⚠ `was_ever_checked`, not `last_verified`. The stamp is NULL both when nobody looked and
    # when a verify looked and found gaps - `(aes)`. One predicate, four surfaces.
    never = sorted(
        named[str(d["uuid"])] for d in holding if not d["last_verified"] and not was_ever_checked(d)
    )
    checked = [str(d["last_verified"]) for d in holding if d["last_verified"]]
    # The OLDEST of the places that carry a date, computed **whether or not** another place is
    # unchecked - which is the whole of `(abg)` Stage 3. The rule that no single date is true of
    # the whole claim is NOT weakened by this: it is stated by `never_checked` and by the
    # surfaces leading with it, rather than by blanking a second date field nobody read.
    oldest = min(checked) if checked else None
    days = _whole_days_since(oldest, now) if oldest else None
    return CustodyFreshness(
        never_checked=tuple(never),
        dated_at=oldest,
        dated_days=days,
        tier=_tier_for(days),
    )


def _whole_days_since(when: str, now: datetime | None) -> int | None:
    """Whole days from an ISO timestamp to `now`, or `None` if it cannot be read as one.

    **Unparseable is `None`, never zero.** A zero would read as *"checked today"* about a value
    nothing could make sense of, which is the confident-wrong-answer failure. `last_verified` is
    written by `refresh_drive_verified` alone and is always ISO, so this is a guard rather than a
    branch anyone should reach; it exists because the field is also a plain TEXT column.

    A naive timestamp is read as UTC, matching how `mark_copy_verified`'s callers write it.
    """
    try:
        stamp = datetime.fromisoformat(when)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return max(0, ((now or datetime.now(UTC)) - stamp).days)


def _tier_for(days: int | None) -> CustodyTier:
    """The tier of an age in days. **Undated is FRESH, not STALE.**

    Nothing has been checked, so there is no age to have exceeded - calling that stale would read
    as *"checked long ago"* about a place nothing has ever looked at. `never_checked` carries that
    claim instead, and it is a different one.
    """
    if days is None or days < CUSTODY_SOFTENS_AFTER_DAYS:
        return CustodyTier.FRESH
    return CustodyTier.STALE if days >= CUSTODY_STALE_AFTER_DAYS else CustodyTier.SOFTENING


#: How long the probe of a drive's remembered path may take before it is abandoned. `(adx)`.
#:
#: **A judgement, not a measurement**, recorded the way `run_health.TICK_SECONDS` is. The fast
#: case is priced: `run_health` measures `read_marker` at **21.18 us** locally and a FUSE `stat`
#: at **~600 us**, so a live marker read on a slow mount is ~1.2-1.8 ms and this is ~550x it. What
#: is *not* measured is the case the bound exists for - a wedged mount that never answers - because
#: no such mount could be staged. Whoever revisits should know there is no data behind the 1.0.
#:
#: The operations this runs in front of (`verify`, `drives --init`, an organize run) take seconds
#: to hours, so the worst case is invisible against them.
SECOND_LOCATION_PROBE_SECONDS = 1.0

#: Remembered paths whose probe did not answer, for this process only.
#:
#: **Why a memo is needed at all.** A blocked `stat` cannot be interrupted - `SIGALRM` does not
#: reach it - so a probe that times out leaves a thread parked for the life of the process. One is
#: acceptable; one per verify against the same wedged mount is a leak. Per-process rather than
#: persisted, so a mount that comes back is probed again on the next launch and a transient stall
#: never becomes a permanent silence.
_SLOW_PATHS: set[str] = set()


def forget_slow_paths() -> None:
    """Clear the memo. For tests; nothing in production needs it, since the memo dies with the process."""
    _SLOW_PATHS.clear()


def _marker_within(root: Path, seconds: float) -> DriveMarker | None:
    """`read_marker(root)`, abandoned if it has not answered in ``seconds``.

    **Abandoned, never cancelled, and that distinction is the whole design.** A `stat` or `read`
    blocked on a hard mount is uninterruptible; the thread can only be left behind. That is safe
    on this runtime and was not always: bpo-32186 - *"io.FileIO can hang all threads when accessing
    an inaccessible NFS server"*, `fstat` holding the GIL inside `fileio_init` - was fixed in
    December 2017 for 3.6/3.7+, far below this project's floor. Verified rather than assumed: while
    one thread blocks in a syscall another keeps running. **The floor is named nowhere here on
    purpose** - what matters is that the fix predates every version we could run, and a version
    number written here is one more thing to update the next time the floor moves.

    The abandoned thread holds one file descriptor and discards its result. It writes nothing, so a
    timeout can never leave state behind.

    ⚠ **A probe that finishes just past the join reads as a timeout**, because the answer lands
    after the decision. `list.append` is atomic, so nothing is corrupted; the outcome is silence
    and a memo entry for a path that was not really slow. Both are the safe direction, and the
    memo is per-process, so the next launch asks again.
    """
    answer: list[DriveMarker | None] = []

    def probe() -> None:
        answer.append(read_marker(root))

    worker = threading.Thread(target=probe, name="drive-marker-probe", daemon=True)
    worker.start()
    worker.join(timeout=seconds)
    return answer[0] if answer else None


def _live_second_path(uuid: str, here: Path, remembered: str | None) -> Path | None:
    """The remembered path, when it is a DIFFERENT place that still answers with this uuid.

    ``None`` for every other outcome, and they are deliberately not distinguished: no remembered
    path, the same path, a path that is gone, someone else's drive there, or a probe that did not
    answer in time. A move and a clone whose original is unplugged produce the identical
    observation, so only the unambiguous case gets an answer.
    """
    if not remembered:
        return None
    other = Path(remembered)
    if other == here or remembered in _SLOW_PATHS:
        return None
    marker = _marker_within(other, SECOND_LOCATION_PROBE_SECONDS)
    if marker is None:
        # Did not answer. Indistinguishable from "gone", so treated as gone - but if the path is
        # still THERE, the probe was slow rather than absent, and a slow one left a thread parked
        # that cannot be killed. Remember it so the next call does not park another.
        if other.exists():
            _SLOW_PATHS.add(remembered)
        return None
    return other if marker.uuid == uuid else None


def second_location_note(
    *,
    uuid: str,
    label: str,
    here: Path,
    remembered: str | None,
    previously_seen: str | None,
) -> str | None:
    """What to tell someone whose drive identity answers at a second live path. `(adx)` gap 1.

    **Reports only the case that cannot be wrong.** If the remembered path still answers with this
    uuid, two complete copies exist and nothing is being inferred - the catalog counts them as one
    drive, so its custody claim is short by one. Every other outcome is silent; see
    :func:`_live_second_path` for why they are not told apart.

    ⚠ **This does not disambiguate and must not start to.** `drive-identity-research.md` ruled that
    clones share one identity until they diverge, and that ruling stands: minting a second id here
    would count one copy as two, the same error mirrored. This states an observation and names the
    command a person can run; the decision stays theirs.

    **Fails open.** Silence is the default and only a positive same-uuid answer produces output, so
    every failure mode of the probe lands in the direction that says nothing.
    """
    other = _live_second_path(uuid, here, remembered)
    if other is None:
        return None
    when = f" (last seen {previously_seen})" if previously_seen else ""
    return (
        f"note: drive '{label}' also answers at {other}{when}.\n"
        f"       in use now : {here}\n"
        f"       also here  : {other}\n"
        f"       Both places carry the same drive id, so Truestill counts them as ONE drive and "
        f"your photos are in more places than it reports.\n"
        f"       If these are two real drives, give one its own identity:\n"
        f"         truestill drives --init {other} --force-new-identity"
    )


class _DriveMemory(Protocol):
    """What :func:`second_location_for` needs from a catalog: the hint, and when it was last seen.

    A protocol for the reason `_SettingsReader` gives - `drive.py` is a leaf and identity has no
    business depending on storage - and a second one rather than widening that one, because
    `reach_of` genuinely needs less and should not gain a dependency it does not use.
    """

    def get_setting(self, key: str) -> str | None: ...

    def drive_row(self, uuid: str) -> Any: ...


def second_location_for(memory: _DriveMemory, *, uuid: str, label: str, here: Path) -> str | None:
    """Read the two things the question needs, then ask it. `(adx)` gap 1.

    ⚠ **THE READS MUST HAPPEN BEFORE `upsert_drive` AND BEFORE THE HINT WRITE**, which is why this
    exists as a function rather than as two lines at each call site: those two statements destroy
    the two halves of the evidence - `upsert_drive` refreshes ``last_seen``, the hint write
    replaces the remembered path - and in `_cmd_verify` they sit five lines apart.

    **One home rather than one copy per surface.** The CLI and the app both need exactly this, and
    a second spelling of it is the drift `ENGINEERING_STANDARD.md` §4 names - caught here by
    `test_surface_parity` on the first run, when both surfaces had written the same
    ``last_seen`` lookup with different variable names.
    """
    row = memory.drive_row(uuid)
    return second_location_note(
        uuid=uuid,
        label=label,
        here=here,
        remembered=memory.get_setting(drive_path_hint(uuid)),
        previously_seen=None if row is None else row["last_seen"],
    )


def drive_reach(hint: str | None, uuid: str) -> DriveReach:
    """Where ``uuid`` stands, given the path it was last seen at. **O(1)** - one marker read.

    Pure on purpose: it takes the remembered path rather than a `Catalog`, so it is the same
    answer on both surfaces, is trivially testable, and cannot become a second reachability
    mechanism by accident. Callers do their own settings read.

    A *different* drive at the remembered path is ``OFFLINE``, not ``CONNECTED``: the question is
    whether **this** drive is reachable, and someone else's marker is not a yes.

    ⚠ **A RELATIVE hint is ``UNKNOWN``, not a path to try.** `(ahu)` Catalogs written before
    :func:`remember_drive_path` existed can hold one, and its meaning depends on the working
    directory of whoever reads it - so one drive read ``CONNECTED`` from the directory a command
    happened to run in and ``OFFLINE`` from anywhere else. **``UNKNOWN`` is not a concession, it
    is the only true answer**: the working directory it was written from was never recorded, so
    the product cannot say where that drive is. That is
    `catalog._make_the_inplace_journal_an_intent_log`'s rule one layer up - never assert an outcome
    you did not observe - and it is why `(ahu)` repairs old catalogs here rather than in a
    migration, which the no-backfill rule would have refused.
    """
    if not hint or not Path(hint).is_absolute():
        return DriveReach.UNKNOWN
    marker = read_marker(Path(hint))
    if marker is None:
        return DriveReach.OFFLINE
    return DriveReach.CONNECTED if marker.uuid == uuid else DriveReach.OFFLINE


class _SettingsReader(Protocol):
    """The one thing :func:`reach_of` needs from a catalog.

    A protocol rather than importing `Catalog`: `drive.py` is a leaf module and identity has no
    business depending on storage. It also makes the helper testable with a dict.
    """

    def get_setting(self, key: str) -> str | None: ...


def reach_of(settings: _SettingsReader, uuid: str) -> DriveReach:
    """:func:`drive_reach` for a drive whose hint is in the catalog. **O(1)**.

    Exists because reading the hint and interpreting it is one rule, and it was briefly written
    at two call sites - the app's drive listing and the CLI's. `test_surface_parity` caught that,
    correctly: the pair that drifts is the one where only one side later learns something.
    """
    return drive_reach(settings.get_setting(drive_path_hint(uuid)), uuid)


class DriveGhostError(Exception):
    """Refusal: this path is a known drive's recorded location and its marker is not there.

    One type in core rather than one per surface, so `jobs.py` reports the same `code` the CLI
    exits on and neither can word the refusal differently (§9).
    """


class DriveWriteError(Exception):
    """Refusal: this drive would not accept its marker. `(aek)`

    Sibling of :class:`DriveGhostError`, here for the same reason and carrying the same wording
    rule: one type in core, so the CLI's exit code and `jobs.py`'s `code` name the same condition
    and neither surface can word it differently (§9).

    **The message is already a sentence** - `drive_unwritable.explain_unwritable_drive` composed
    it - so a caller prints it rather than interpreting it. This is the end of
    :func:`write_marker`'s never-raise contract that exists for callers with nothing to do without
    an identity; the outcome-returning form is still there for callers that have.
    """


@dataclass(frozen=True, slots=True)
class GhostDrive:
    """A registered drive the catalog places at a path where its marker is no longer present."""

    uuid: str
    label: str
    #: The path the catalog recorded for it, which is the path being written to.
    recorded_at: str


def ghost_drive_at(
    path: Path, settings: _SettingsReader, drives: Iterable[tuple[str, str]]
) -> GhostDrive | None:
    """The known drive this path is recorded as, when no marker is there. **O(drives)**.

    **The failure this exists for, and it is a data-loss one.** A FUSE mountpoint with nothing
    mounted on it is an ordinary empty directory: writes into it succeed, and they land on the
    computer's own disk. `DestinationDevice` cannot see it - that guard latches the device on
    **first sighting**, so a run that STARTS in this state adopts the local disk as its baseline
    and never fires. The marker cannot see it either: an empty directory has none, and absence is
    what makes the surfaces mint a *new* identity for a library the catalog already knows, which
    is `(aap)` arriving through the one door `(aap)`'s content-based guard is blind to - it
    recognises a folder that HOLDS a known library, and this one holds nothing.

    **Only a recorded path discriminates it**, which is why this reads the hint. An empty
    directory carries no information about which drive it was, so the answer has to come from
    outside it. Measured alternatives that do not work: `os.path.ismount` is true only while
    something IS mounted, so it returns False for exactly this case; the mount table and
    `/etc/fstab` keep no record once a FUSE mount is gone; and matching the drive LABEL against
    the directory name is a coin toss, because `create_marker` defaults the label to that same
    directory name and every second `Backup` folder would be refused.

    **Fails open on purpose.** No hint, a differently-spelled path, or a marker actually present
    all mean "no opinion" - this must never block a genuine new destination. Compared lexically
    rather than through `resolve()`, for the reason `check_contained` gives: a path that cannot
    be resolved (a stale mount raises `ENOTCONN`) must still get an answer.
    """
    if existing_marker_path(path) is not None:
        return None  # a marker is here: whatever this is, it is not a ghost
    for uuid, label in drives:
        hint = settings.get_setting(drive_path_hint(uuid))
        if hint and Path(hint) == path:
            return GhostDrive(uuid=uuid, label=label, recorded_at=hint)
    return None


def drives_without_a_known_location(
    settings: _SettingsReader, drives: Iterable[tuple[str, str]]
) -> tuple[str, ...]:
    """Labels of registered drives the catalog cannot place. **O(drives)**.

    These are the ones :func:`ghost_drive_at` can say nothing about: with no recorded path there
    is no way to tell an empty folder that is one of them from an empty folder that is new. The
    caller asks before minting a *second* identity, so the person who does know can answer.
    """
    return tuple(label for uuid, label in drives if not settings.get_setting(drive_path_hint(uuid)))


def distinguishing_names(
    settings: _SettingsReader, drives: Iterable[tuple[str, str]]
) -> tuple[str, ...]:
    """A name per drive, in the caller's order, disambiguated **only** where the label collides
    within this set. **O(drives)**, and it reads a setting only for a colliding label.

    **The invariant is not that labels are unique. It is that Truestill never names a drive
    ambiguously** - a property of the moment of naming, where the set being named is known, and
    one that cannot be established at registration, where it is not. `(acr)`.

    **Uniqueness is deliberately not enforced anywhere.** :func:`ghost_drive_at` already ruled on
    this: matching a label against a directory name is *"a coin toss, because ``create_marker``
    defaults the label to that same directory name and every second ``Backup`` folder would be
    refused."* Collisions are how people name folders, not an error to prevent - and a label lives
    in the marker on the user's own disk, so renaming one would mean writing to their drive to fix
    our bookkeeping.

    **A unique label is returned untouched, as the first branch** - not usually, but structurally.
    A one-drive library and a set of distinctly-named drives produce byte-identical output to
    having never called this, which is what keeps it invisible on the common case.

    **When the label collides:**

    - a recorded path is the only honest discriminator we have, so it is shown;
    - with no recorded path we **say so**. ``The Memory Cabinet`` has no hint in the real catalog,
      so this is a live case and not a defensive branch. It is stated plainly rather than
      apologetically: the user is told what Truestill does not know, which is actionable - plug it
      in and let it be seen - where silence is not.

    **Two unplaceable drives sharing a label stay two entries, reading alike.** Collapsing them is
    most tempting exactly here and would break `(acs)`'s invariant: hiding may reduce detail, never
    the count nor a drive's identity as a distinct thing. Ordinals were rejected for the opposite
    reason - ``#1`` and ``#2`` would invent an identity the user cannot act on.

    **`file_count`, `size` and `first_seen` are available and are deliberately unused.** They will
    look tempting to whoever extends this. They discriminate but do not locate, and a custody
    warning that answers *where is it* with *how big is it* is a change of subject dressed as an
    answer.

    Wording lives here rather than at the surfaces, for the reason :func:`ghost_drive_refusal`
    gives: one home, so the CLI and the app cannot word it differently (§9).
    """
    pairs = list(drives)
    seen = Counter(label for _, label in pairs)
    names: list[str] = []
    for uuid, label in pairs:
        if seen[label] == 1:
            names.append(label)
            continue
        hint = settings.get_setting(drive_path_hint(uuid))
        names.append(f"{label} at {hint}" if hint else f"{label} (location not known)")
    return tuple(names)


def ghost_drive_refusal(ghost: GhostDrive) -> str:
    """What to say. One home, so the CLI and the app cannot word this differently (§9).

    Three facts, and the third is the one nobody can discover for themselves: files written into
    a mountpoint while nothing is mounted there are **shadowed the moment the filesystem returns**
    while still occupying the disk. `verify` then reports them missing and `df` shows the space
    gone, and the only way to see them again is to unmount - which nobody thinks to do.
    """
    return (
        f"{ghost.recorded_at} is where Truestill recorded the drive '{ghost.label}', "
        f"but that drive's marker file is not there.\n"
        f"       The drive is probably not plugged in or not mounted.\n"
        f"       Anything written here now would go onto THIS computer's disk, and would "
        f"DISAPPEAR from view the moment the drive comes back - while still using the space.\n"
        f"       Connect the drive and run again. If this folder is genuinely a different "
        f"place now, re-run with --force-new-identity."
    )


def path_is_usable_dir(path: Path) -> bool:
    """True when ``path`` is an existing directory we can stat.

    Stale mount hints (ENOENT, ENOTDIR, ``PermissionError`` on a locked vault folder, dead
    FUSE) must not escape as raw ``OSError`` to the UI. False means "do not trust this path";
    identity still lives on the marker uuid elsewhere, never here.
    """
    try:
        return path.is_dir()
    except OSError:
        return False


def locate_drive(path: Path) -> DriveLocation:
    """Find the drive a path belongs to, by walking **up** for a marker.

    A user pointing at ``.../The Memory Cabinet/2014`` has connected the drive; they simply named
    a folder inside it. Walking the parents turns an unanswerable error into a correction the
    caller can offer in one click.

    Reads only, and never above the filesystem root. **O(depth)** stat calls - a handful, and
    independent of library size. An unreachable path (missing, not a directory, or raising
    ``OSError`` on access) returns an empty location - never propagates the OS error.
    """
    try:
        exists = path.exists()
    except OSError:
        return DriveLocation(given=path)
    try:
        resolved = path.resolve() if exists else path
    except OSError:
        resolved = path
    for candidate in (resolved, *resolved.parents):
        marker = read_marker(candidate)
        if marker is not None:
            return DriveLocation(given=resolved, root=candidate, marker=marker)
    return DriveLocation(given=resolved)


@dataclass(frozen=True, slots=True)
class DriveIdentity:
    """What names a drive for locking, and what to call it in a refusal. `(aaw)`

    ``key`` is ``uuid:<marker>`` for a marked drive and ``path:<resolved>`` otherwise, so the same
    drive reached through two mountpoints collides and two different drives never block each other.

    ⚠ **Key and label are produced together, from ONE marker read.** Deriving them separately meant
    reading the marker twice and, worse, invited a `marker=None` parameter that answers *"not
    marked"* and *"I did not look"* with one value - the conflation this codebase keeps paying for
    (`(aac)`, `(aer)`, `(afo)`).
    """

    key: str
    label: str


def drive_identity(root: Path) -> DriveIdentity:
    """Lock identity for a path an operation will touch. **One spelling for both surfaces.**

    In core rather than in `truestill_app.service`, for the reason `drive_path_hint` is:
    `truestill-cli` cannot import that package (`IMPLEMENTATION_STANDARDS.md` §2), and the CLI and
    the app must agree on this key exactly or their locks pass through each other.
    """
    marker = read_marker(root)
    if marker is not None:
        return DriveIdentity(key=f"uuid:{marker.uuid}", label=marker.label)
    try:
        resolved = str(root.expanduser().resolve())
    except OSError:
        # `resolve()` on a path whose parent refused is not an answer we can improve on here, and
        # a lock keyed by the unresolved spelling is still better than no lock.
        resolved = str(root)
    return DriveIdentity(key=f"path:{resolved}", label=root.name or resolved)


def read_marker(root: Path) -> DriveMarker | None:
    """Return the drive's marker, or ``None`` if absent or unreadable/invalid.

    Honours legacy marker names (see the module docstring). This function never writes, so a
    legacy drive stays legacy on disk until something explicitly upgrades it.
    """
    found = existing_marker_path(root)
    if found is None:
        return None
    try:
        data = json.loads(found.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    uuid, label, created = data.get("uuid"), data.get("label"), data.get("created")
    if not isinstance(uuid, str) or not isinstance(label, str):
        return None
    return DriveMarker(uuid=uuid, label=label, created=created if isinstance(created, str) else "")


#: Appended to the marker's name while its bytes are in flight. Same idea as
#: `safe_copy.STAGING_SUFFIX` and `decisions`' `.writing`, and it sits beside the target on purpose:
#: a temp in the system temp directory would make the final step a copy across filesystems, which
#: is exactly the non-atomic write staging exists to avoid.
_MARKER_STAGING_SUFFIX = ".writing"


def write_marker(root: Path, marker: DriveMarker) -> MarkerWrite:
    """Write ``marker`` to the drive root under the canonical name. **Never raises.** `(aek)`

    Any legacy marker present is left untouched, so an interrupted or downgraded run still finds
    a readable identity.

    **Staged, because a zero-byte marker is worse than none.** ``write_text`` opens
    ``O_CREAT|O_TRUNC``, so a full disk fails at the *write* with the real name already taken - the
    first soak left an empty ``.truestill-drive.json`` at a drive root that way, and this is the
    only truestill-named artifact the product ever writes to a user's disk
    (`IMPLEMENTATION_STANDARDS.md` §3.1). Bytes take the name only once they are all there, and a
    failure removes what it staged. The discipline and the wording are both
    :func:`truestill_core.decisions.write_decisions`', which is older and already proven - one
    mechanism, two callers, rather than a second one that drifts.

    **Never raises, and that contract is the whole of `(aek)`.** ``organize`` into an unregistered
    destination on a full disk died here with a `pathlib` traceback a few steps from a copy path
    that handles the same errno per file. A read-only disk, a full one, a used-up quota and one
    pulled out mid-write are ordinary events for removable media; every one comes back as a
    reported outcome. :func:`create_marker` is the end that turns a refusal into an exception for
    callers that cannot continue without an identity.
    """
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return MarkerWrite(written=False, error=explain_unwritable_drive(error))

    target = marker_path(root)
    temp = target.with_name(target.name + _MARKER_STAGING_SUFFIX)
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(marker.to_json())
            handle.flush()
            # The marker is the key every `file_copies` row is recorded against, so it is worth a
            # flush the way the decisions document is - and unlike `safe_copy`, which deliberately
            # does not fsync, this is one ~150-byte write per registration rather than per file.
            os.fsync(handle.fileno())
        temp.replace(target)
    except OSError as error:
        # A drive that will not take the write may not take the cleanup either; a cleanup that
        # raised would replace a reported failure with an unreported one.
        with contextlib.suppress(OSError):
            temp.unlink(missing_ok=True)
        return MarkerWrite(written=False, error=explain_unwritable_drive(error))
    return MarkerWrite(written=True, path=target)


def needs_marker_upgrade(root: Path) -> bool:
    """True when ``root`` carries only a legacy marker and no canonical one."""
    found = existing_marker_path(root)
    return found is not None and found.name != MARKER_NAME


def upgrade_marker(root: Path) -> DriveMarker | None:
    """Write a canonical marker for a legacy-only drive, preserving identity verbatim.

    Returns the marker now stored canonically, or ``None`` if ``root`` carries no marker at all.
    Already-canonical drives are returned unchanged without a write. The legacy file is
    deliberately left in place (see the module docstring).

    ``None`` keeps its single meaning - *there is no marker here* - because a failed write raises
    :class:`DriveWriteError` rather than returning it. Two situations behind one ``None`` is the
    conflation `(abv)` was, in miniature.

    :raises DriveWriteError: the drive would not accept the canonical marker.
    """
    marker = read_marker(root)
    if marker is None:
        return None
    if needs_marker_upgrade(root):
        _write_marker_or_raise(root, marker)  # uuid/label/created copied verbatim
    return marker


def create_marker(root: Path, label: str, *, uuid: str | None = None) -> DriveMarker:
    """Mint (or re-attach, if ``uuid`` given) a marker and write it to ``root``.

    The end of :func:`write_marker` for callers that cannot continue without an identity, which is
    every production caller: a registration that did not happen must stop the run, not be carried
    forward as a marker nobody wrote. Same relationship `copy_leaving_nothing` has to `staged_copy`
    - one mechanism, two ends, and the signature is what says which end you are on.

    :raises DriveWriteError: the drive would not accept the marker. Every call site is required to
        handle it, and `test_marker_writes_are_handled.py` enumerates them from the source rather
        than trusting anyone to remember (ENGINEERING_STANDARD.md §4, twenty-seventh member).
    """
    marker = DriveMarker(
        uuid=uuid or str(uuid4()),
        label=label,
        created=datetime.now(UTC).isoformat(),
    )
    _write_marker_or_raise(root, marker)
    return marker


def _write_marker_or_raise(root: Path, marker: DriveMarker) -> None:
    """Write, turning a refusal into the typed error. One conversion, so the two ends agree."""
    outcome = write_marker(root, marker)
    if not outcome.written:
        message = f"{root} could not be set up as a drive: {outcome.error}"
        raise DriveWriteError(message)
