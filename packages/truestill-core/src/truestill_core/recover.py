"""Bring photographs back from a drive into a library. **Copies in; deletes nothing, ever.**

Stage 2 of the restore arc. Stage 1 (`carried`) counted the gap; this fills it.

⚠ **THE NAME IS `recover`, NOT `restore`.** `restore` is taken by the decisions command, declared
in the CLI's own lock table as *"writes catalog rows from a drive's document, never files onto the
drive"*. Two commands that both "restore" and move entirely different things is how a user runs the
wrong one.

**The engine was already here and is deliberately not changed.** `backup._files_missing_on_target`
computes this exact gap - by content hash, credible-checked against the destination's own disk -
and is already imported by the CLI and by the app's service layer. It is reused verbatim.
`safe_copy.staged_copy` is the proven copy primitive and is reused too. Nothing in `backup.py`,
`organizer.py` or the catalog schema is touched.

**What could NOT be reused, and it is the reason this module exists rather than a flag on backup.**
`StagedCopy.commit` finishes with ``self.temp.replace(self.target)``, and its own docstring says
so: *"Give the staged bytes the target's name, replacing whatever is there."* That is correct for
`backup`, which owns its target drive. It is **forbidden here**: a library is the user's own tree,
and a recover that silently replaced a file in it would be the documented rclone data-loss mode -
*"a sync job running in the wrong direction can overwrite newer files with older versions"*. So
this loop stages, hashes, **checks the target is still absent**, and only then commits; an
occupied path is abandoned and reported.

**The three rules, absolute:**

1. **COPY SEMANTICS.** Nothing at the destination is deleted. Not a file, not a directory, not for
   any reason. There is no unlink in this module and no caller may add one.
2. **NEVER OVERWRITE.** A file already at the target path is skipped and named, never replaced -
   even when the catalog believes it should be there. The collision case is stage 4.
3. **THE GAP IS CONTENT, NOT PATH.** Identity is ``sha256``. A photograph already in the library
   under a different name is not a gap, and re-copying it would be a duplicate the user then has
   to clean up.

⚠ **A ROW IS A CLAIM, AND HERE IT IS THE *SOURCE* ROWS THAT LIE.** `backup` trusts its source: the
library is in front of it. This reads rows describing a **removable drive**, measured at *"429 rows
against 124 files actually there, 305 false custody claims"*. So a source file that is not there is
an ordinary, named, counted skip - never a failure of the run.
"""

from __future__ import annotations

import errno
import shutil
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from truestill_core.backup import MissingCopy, _files_missing_on_target
from truestill_core.catalog import Catalog
from truestill_core.catalog_session import open_catalog
from truestill_core.destinations.base import DestinationDevice
from truestill_core.drive import DriveMarker, existing_marker_path
from truestill_core.drive_unwritable import persists_for_the_run
from truestill_core.hashing import sha256_file
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.run_record import RunHeader, build_run_record, record_organize
from truestill_core.safe_copy import staged_copy

#: Headroom over the recorded size before a run is allowed to start, matching `backup`'s. The
#: sizes are the catalog's, and a file can have grown since; refusing at exactly 100% would start
#: runs that fill the disk on the last file.
_FREE_SPACE_MARGIN = 1.1


#: ⚠ **THE SENTENCE A FRIGHTENED PERSON READS BEFORE THEY PRESS ANYTHING, and it is in core
#: because both surfaces must say it identically.** The user arriving here has met restores that
#: destroy things: UrBackup ships restore **disabled by default** and treats it as the dangerous
#: direction; Backblaze tells people to make another backup first. That fear is
#: inherited from other software and it is entirely reasonable - but it is wrong about this
#: operation, and **the remedy is a sentence, not a smaller button**. So it is stated plainly,
#: up front, in words that do not require knowing what a catalog is.
NOTHING_IS_LOST = (
    "Nothing in your library is deleted or replaced. Files are only added. If something is "
    "already there, it is left exactly as it is."
)

#: The drive is read and not written to - the other half of the reassurance, and separately
#: worded because it answers a different fear: not "will I lose my library" but "will this
#: damage my backup too".
DRIVE_IS_READ_ONLY = "The drive is only read from. Nothing on it is changed."

#: Why a drive nobody has walked cannot be recovered from, and what to do instead. The worst
#: wrong answer in the product is telling somebody who has just lost a library that there is
#: nothing to bring back, about a drive holding all of it.
NEVER_WALKED = (
    "This catalog has no record of anything on this drive, so it cannot say what is on it. "
    "That is not the same as the drive being empty: a drive that was registered but never "
    "checked has no record yet. Check it first, then come back."
)


class Skipped(Enum):
    """Why one recorded file was not copied. **Skips are not failures**, and the split matters.

    A failure is Truestill unable to do something it should have managed. These two are the
    product working correctly on a library and a drive that are not what the catalog says - and a
    user reading *"6 failed"* for six files they already have would go looking for a defect.
    """

    #: Something is already at that path in the library. **Never replaced.** Rule 2.
    ALREADY_THERE = "already_there"
    #: The drive's row is a claim the drive did not honour - the file is not on it. `(aiz)`
    NOT_ON_THE_DRIVE = "not_on_the_drive"


#: One sentence per skip class, for whichever surface is reporting. ⚠ **Keyed on the enum rather
#: than on its string value**, so adding a member and forgetting to word it is a `KeyError` at
#: the call site rather than a skip that renders as nothing.
SKIP_REASONS: dict[Skipped, str] = {
    Skipped.ALREADY_THERE: (
        "already in your library at that exact place, and left exactly as it is"
    ),
    Skipped.NOT_ON_THE_DRIVE: (
        "recorded as being on this drive, but not actually there when we looked"
    ),
}


@dataclass(frozen=True, slots=True)
class RecoverPair:
    """The drive being read and the library being written into, each resolved by its surface.

    ⚠ **The fields are named `drive` and `library`, not `source` and `target`, and that is the
    whole defence against the first documented data-loss mode for this operation** - *"if B has
    older versions, they overwrite your newer files"*. `BackupPair` carries the same four values
    under directional names, so passing one where the other belongs would type-check and run
    backwards. These names make the direction unmistakable at every call site.
    """

    #: Read from. Never written to, never deleted from.
    drive: Path
    drive_marker: DriveMarker
    #: Written into, additively.
    library: Path
    library_marker: DriveMarker


@dataclass(frozen=True, slots=True)
class RecoverPlan:
    """What a recover would do, before it does anything. The preview's whole content."""

    drive_label: str
    library_label: str
    gaps: tuple[MissingCopy, ...]
    bytes_needed: int
    #: ⚠ False when `file_copies` holds nothing for the drive - **nobody walked it**, which is not
    #: the same as it being empty. Stage 1's distinction, and a recover must not read it as
    #: "nothing to bring back". See `carried.Carried.drive_walked`.
    drive_walked: bool

    @property
    def count(self) -> int:
        return len(self.gaps)


@dataclass(slots=True)
class RecoverOutcome:
    """What one recover actually did. **Built from what happened, never from the plan.**"""

    #: relative -> the digest actually written, for every copy that completed. **The one record
    #: of what landed**; `copied` and `copied_names` are read off it rather than counted beside
    #: it, because two tallies of one fact are two things that can disagree.
    written: dict[str, str] = field(default_factory=dict)
    bytes_copied: int = 0
    #: ``(relative, why)`` for every recorded file deliberately not copied.
    skipped: list[tuple[str, Skipped]] = field(default_factory=list)
    #: ``(relative, detail)`` for every file Truestill could not copy and should have managed.
    failures: list[tuple[str, str]] = field(default_factory=list)

    @property
    def copied(self) -> int:
        return len(self.written)

    @property
    def copied_names(self) -> list[str]:
        return list(self.written)

    @property
    def attempted(self) -> int:
        """Every file the run REACHED - copied, skipped or failed alike.

        `backup`'s recorder argues this arithmetic: understating `attempted` OVERSTATES
        `never_attempted`, producing a record that claims files were skipped when they were in
        fact tried. Two different facts, kept apart.
        """
        return self.copied + len(self.skipped) + len(self.failures)


class RecoverStoppedError(OSError):
    """A recover stopped part way, carrying what it managed. `BackupStoppedError`'s shape.

    ⚠ **An `OSError` subclass for that type's recorded reason**: the surfaces already catch
    `OSError` around a drive that vanished, and a stop that reports nothing is the worse defect -
    a user cannot tell 6 copied from 2,000 without running `verify` themselves.
    """

    def __init__(self, *, outcome: RecoverOutcome, cause: OSError) -> None:
        # `cause` rather than a `detail`/`errno` pair: they always come from the same object, and
        # splitting them is how one gets passed without the other.
        super().__init__(cause.errno, str(cause))
        self.outcome = outcome
        self.detail = str(cause)


def plan_recovery(
    pair: RecoverPair, db: Path, *, progress: ProgressCallback | None = None
) -> RecoverPlan:
    """What is on the drive and not in the library. **Reads two tables and stats the library.**

    The gap is `backup._files_missing_on_target` with the arguments in the recovering direction -
    the drive is the source of truth about what exists, the library is the target being checked.
    Reused rather than rewritten: it is the same comparison, it already runs the library's rows
    through `credible_copies`, and a second implementation of the product's most safety-critical
    set difference is a second thing to get wrong.

    ⚠ **``progress`` announces the phase; it does not tick through it, and that limit is real.**
    The stat pass is one call inside the reused helper - measured at **85% of 896 ms** over a
    40,000-file library on local ext4, which is seconds on USB or a network mount. The recorded
    complaint about Time Machine's restore is exactly this window: *a minute with no indication
    anything is happening*. A named, visible phase is not a per-file bar, but it is the
    difference between waiting and wondering, and it is what can be had without a second
    implementation of the comparison.
    """
    if progress is not None:
        progress(Progress(0, 0, Phase.SCANNING, pair.library_marker.label))
    with open_catalog(db) as catalog:
        gaps = _files_missing_on_target(
            catalog, pair.drive_marker.uuid, pair.library_marker.uuid, pair.library
        )
        walked = bool(catalog.copies_on_drive(pair.drive_marker.uuid))
    return RecoverPlan(
        drive_label=pair.drive_marker.label,
        library_label=pair.library_marker.label,
        gaps=tuple(gaps),
        bytes_needed=sum(int(row.size or 0) for row in gaps),
        drive_walked=walked,
    )


def recover_into_library(
    pair: RecoverPair,
    db: Path,
    *,
    progress: ProgressCallback,
    cancel: threading.Event,
) -> RecoverOutcome:
    """Copy every gap into the library, verifying each file before it takes its name.

    :raises ValueError: the two folders are one drive, or the library has no room. Neither is a
        per-file condition the run can carry on past, so both are stated rather than folded into
        the outcome - `copy_to_drive`'s rule, kept.
    :raises RecoverStoppedError: a guard above the copy said stop. The run record is written
        first, and the counts travel with the stop.
    """
    if pair.drive_marker.uuid == pair.library_marker.uuid:
        message = "the drive and the library are the same drive."
        raise ValueError(message)
    plan = plan_recovery(pair, db)
    free = shutil.disk_usage(pair.library).free
    if free < plan.bytes_needed * _FREE_SPACE_MARGIN:
        message = (
            f"not enough space in {plan.library_label}: needs "
            f"{plan.bytes_needed / 1e9:.1f} GB, only {free / 1e9:.1f} GB free."
        )
        raise ValueError(message)
    with open_catalog(db) as catalog:
        return _copy_gaps(
            _Run(pair=pair, db=db, plan=plan, catalog=catalog),
            progress=progress,
            cancel=cancel,
        )


@dataclass(frozen=True, slots=True)
class _Run:
    """Everything the copy loop needs that does not change while it runs.

    **A context object rather than six parameters**, which is the complexity rule answered by
    naming the group instead of suppressing the count - `backup._CopyRun`'s own reasoning, and it
    also stops a caller passing the drive and the library in the wrong order.
    """

    pair: RecoverPair
    db: Path
    plan: RecoverPlan
    catalog: Catalog


def _copy_gaps(run: _Run, *, progress: ProgressCallback, cancel: threading.Event) -> RecoverOutcome:
    """The loop. Lifted out so `recover_into_library` stays under its statement ceiling."""
    pair, plan = run.pair, run.plan
    outcome = RecoverOutcome()
    device = DestinationDevice()
    attempting: MissingCopy | None = None
    try:
        for row in plan.gaps:
            if cancel.is_set():
                break
            attempting = row
            # The library is a mounted place too - a dropped mount must stop the folder being
            # created at all, because a verify-after-write would re-read the copy we just made on
            # the LOCAL disk and find it perfectly correct. `copy_to_drive`'s reasoning.
            device.check(pair.library)
            _copy_one(pair, run.catalog, row, outcome)
            attempting = None
            progress(
                Progress(outcome.copied, len(plan.gaps), Phase.COPYING, Path(row.relative).name)
            )
    except OSError as exc:
        aborted = (attempting.relative if attempting is not None else "", str(exc))
        _record(run, outcome, aborted=aborted)
        raise RecoverStoppedError(outcome=outcome, cause=exc) from exc
    _record(run, outcome, aborted=None)
    return outcome


def _copy_one(
    pair: RecoverPair, catalog: Catalog, row: MissingCopy, outcome: RecoverOutcome
) -> None:
    """One file: stage it, verify it, and commit it **only onto an empty path**."""
    rel = row.relative
    origin = pair.drive / rel
    target = pair.library / rel
    if not origin.is_file():
        # ⚠ **TWO STATES SHARE THIS BRANCH AND THEY ARE OPPOSITE**, which a rename of the drive
        # folder mid-run is what proved: one file missing is the measured NTFS case - a row the
        # medium never honoured - and the run should carry on. **The whole drive being gone is an
        # abort**, and reading it as the first would report *"the catalog records N files that
        # are not actually on that drive"* about a drive that has everything and was unplugged.
        #
        # The marker is the discriminator, and it is one stat: `.truestill-drive.json` sits at
        # the drive root, so it disappears with the mount and survives any per-file accident.
        if existing_marker_path(pair.drive) is None:
            message = f"{pair.drive} is no longer a Truestill drive - was it unplugged?"
            raise OSError(errno.ENOENT, message)
        # Rule 4. Named, counted, and the run carries on.
        outcome.skipped.append((rel, Skipped.NOT_ON_THE_DRIVE))
        return
    if target.exists():
        # ⚠ Rule 2, checked before a byte is read. The cheap half, so the usual case costs one
        # stat; it is checked AGAIN below, after staging, because this one is not atomic.
        #
        # ⚠ **NEITHER CHECK IS PROVABLE ALONE, AND A MUTATION RUN IS WHAT ESTABLISHED THAT.**
        # Removing either one leaves the other catching every case a test can construct, so both
        # mutations survive and only removing THE PAIR goes red. That is redundancy working, not
        # a missing guard - but it means the second check's own reason (a file appearing during
        # the staging window) is defended by argument rather than by a test, because reproducing
        # it needs a race this suite cannot schedule. Stated rather than left to look proven.
        outcome.skipped.append((rel, Skipped.ALREADY_THERE))
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = staged_copy(origin, target)
    if not staged.ok:
        assert staged.error is not None
        if persists_for_the_run(staged.error):
            # The disk is full or the mount is gone: every remaining file would fail the same
            # way, so the run stops and the record is written. `_stop_the_run`'s reasoning.
            raise OSError(staged.error.errno, f"copying {rel} failed: {staged.error}")
        outcome.failures.append((rel, f"copying {rel} failed: {staged.error}"))
        return
    assert staged.temp is not None
    written = sha256_file(staged.temp)
    if row.verify_sha is not None and written != row.verify_sha:
        staged.abandon()
        outcome.failures.append((rel, f"{rel} on the drive did not match what was recorded."))
        return
    # ⚠ **THE SECOND ABSENCE CHECK, AND IT IS THE ONE THAT ENFORCES RULE 2.** Staging takes as
    # long as the file is big, and `commit()` replaces whatever it lands on. Checking here leaves
    # a window of microseconds instead of minutes, and there is no wider primitive available: the
    # atomic non-overwriting move is `os.link` + unlink, which **exFAT and FAT32 do not support**
    # - the two filesystems this product's removable media most often carry. So the window is
    # narrowed and stated rather than claimed away.
    if target.exists():
        staged.abandon()
        outcome.skipped.append((rel, Skipped.ALREADY_THERE))
        return
    committed = staged.commit()
    if not committed.ok:
        assert committed.error is not None
        outcome.failures.append((rel, f"copying {rel} failed: {committed.error}"))
        return
    catalog.record_copy(
        sha256=row.sha256,
        drive_uuid=pair.library_marker.uuid,
        relative=rel,
        # The digest of what was just written, never the one inherited from the drive's row -
        # authoritative by construction, so a copy made by recover is never UNVERIFIABLE.
        copy_sha256=written,
        size=int(row.size or 0) or None,
    )
    outcome.bytes_copied += int(row.size or 0)
    outcome.written[rel] = written


def _record(run: _Run, outcome: RecoverOutcome, *, aborted: tuple[str, str] | None) -> None:
    """Write the run record. **Its own failure must never fail the run.** §1.

    Called from inside an `except` block on the abort path, so anything raised here would
    *replace* the exception being handled - turning a vanished drive into a `TypeError` about
    paperwork. `backup`'s recorder makes the same catch for the same reason.
    """
    try:
        pair, plan = run.pair, run.plan
        stopped: dict[str, object] | None = None
        if aborted is not None:
            # ⚠ `never_attempted` is derived from what the run REACHED, so the record cannot
            # claim a file landed that never did - and cannot claim one was skipped that was
            # tried. `stopped` is present ONLY on an abort; a run that finished with failures
            # reports `stopped: null` and a non-zero failed count.
            stopped = {
                "never_attempted": len(plan.gaps) - outcome.attempted,
                "reason": aborted[1],
            }
        payload = build_run_record(
            RunHeader(
                kind="recover",
                source=str(pair.drive),
                destination=str(pair.library),
                destination_uuid=pair.library_marker.uuid,
                destination_label=pair.library_marker.label,
            ),
            files=_entries(plan.gaps, outcome),
            intended_total=len(plan.gaps),
            attempted=outcome.attempted,
            stopped=stopped,
        )
        record_organize(run.db, payload)
    except Exception:
        # Swallowed on purpose, argued above: the run's outcome must survive its paperwork.
        pass


def _entries(gaps: tuple[MissingCopy, ...], outcome: RecoverOutcome) -> list[dict[str, object]]:
    """One entry per file the run reached. ⚠ **Never one per file it planned to reach.**

    A record built from the plan would name every gap as though it had been handled, which is the
    *"false custody record, worse than no record"* organize's own handler warns about. Only files
    with an outcome appear here, and `intended_total` beside them says how many there were.
    """
    why = dict(outcome.failures)
    skips = dict(outcome.skipped)
    entries: list[dict[str, object]] = []
    for row in gaps:
        rel = row.relative
        if rel in outcome.written:
            status, detail = "copied", None
        elif rel in skips:
            status, detail = "skipped", skips[rel].value
        elif rel in why:
            status, detail = "failed", why[rel]
        else:
            continue  # never reached: the run stopped before it
        entries.append(
            {
                "relative": rel,
                "sha256": row.sha256,
                "status": status,
                "detail": detail,
                "copy_sha256": outcome.written.get(rel),
                "size": row.size,
            }
        )
    return entries
