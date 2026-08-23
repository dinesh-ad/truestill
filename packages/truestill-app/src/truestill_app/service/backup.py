"""Backup: copy the library to a second drive with verify-after-write."""

from __future__ import annotations

import shutil
import sqlite3
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, NoReturn, NotRequired, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.catalog_session import open_catalog
from truestill_core.destinations.base import DestinationDevice
from truestill_core.drive import DriveMarker, read_marker
from truestill_core.drive_adoption import AdoptionOffer, AdoptionVerdict
from truestill_core.drive_unwritable import persists_for_the_run
from truestill_core.hashing import sha256_file
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.run_health import RunHealth, watcher_for
from truestill_core.run_record import RunHeader, build_run_record, record_organize
from truestill_core.safe_copy import staged_copy

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import not_a_drive
from truestill_app.service.drives import BACKUP_PATH_HINT, attach_drive
from truestill_app.service.media_support import media_breakdown


def _now() -> str:
    return datetime.now(UTC).isoformat()


_GB = 1_000_000_000
_MB = 1_000_000


def _gb(n: int) -> str:
    """A human byte size for space messages (GB for anything sizeable, else MB)."""
    return f"{n / _GB:.1f} GB" if n >= _GB else f"{n / _MB:.0f} MB"


_FREE_SPACE_MARGIN = 1.03  # keep a little headroom so a copy never fills the target drive


@dataclass(frozen=True, slots=True)
class MissingCopy:
    """One library file still absent on the backup target.

    Carries both hashes deliberately: ``sha256`` is the content/dedup identity, ``copy_sha256``
    is the verification identity (§3). The copy-verify loop must never treat them as
    interchangeable - that is why this is a dataclass, not ``list[Any]`` (audit F8).
    """

    sha256: str
    relative: str
    copy_sha256: str | None
    size: int | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MissingCopy:
        """Build from a ``copies_on_drive`` or ``organized_files`` catalog row."""
        size_raw = row["size"]
        copy_raw = row["copy_sha256"]
        return cls(
            sha256=str(row["sha256"]),
            relative=str(row["relative"]),
            copy_sha256=None if copy_raw is None else str(copy_raw),
            size=None if size_raw is None else int(size_raw),
        )

    @property
    def verify_sha(self) -> str | None:
        """Digest the on-disk copy must match after write, or ``None`` if none was recorded.

        No fallback to the source hash. That asserted the copy is byte-identical to its source,
        which the Takeout bake already breaks and date-rescue baking will break again - and it
        made an un-recorded hash indistinguishable from a legacy row.
        """
        return self.copy_sha256


def _files_missing_on_target(
    catalog: Catalog, source_uuid: str, target_uuid: str
) -> list[MissingCopy]:
    """Copies present on the source drive but not yet on the target -- keyed on per-drive presence,
    not the catalog-global dedup that would wrongly skip a genuine second copy."""
    on_target = {r["sha256"] for r in catalog.copies_on_drive(target_uuid)}
    return [
        MissingCopy.from_row(r)
        for r in catalog.copies_on_drive(source_uuid)
        if r["sha256"] not in on_target
    ]


class BackupPreviewErr(TypedDict):
    ok: Literal[False]
    error: str


# ``from`` is a reserved word; functional form keeps the JSON key exact.
BackupPreviewOk = TypedDict(
    "BackupPreviewOk",
    {
        "ok": Literal[True],
        "from": str,
        "to": str,
        "will_register": list[str],
        #: How many already-organized copies the run will read end to end to establish this
        #: drive's own hashes. Stated before the run because attach is no longer instant: a
        #: full read of a library is minutes to hours, and a progress bar that appears without
        #: warning reads as a hang. Zero on an already-attached drive, which is the usual case.
        "will_read": int,
        "count": int,
        "photos": int,
        "videos": int,
        "audio": int,
        "bytes": int,
        "free": int,
        "enough": bool,
    },
)


def _blocked_message(side: str, blocked: AdoptionOffer) -> str:
    """Why this folder was not registered. **Two blocks, two sentences.**

    ⚠ This read only ``blocked.label`` and always said the folder *"already holds"* a known
    library. True for a matched drive; **false** for one whose sample could not be read, where the
    whole point is that Truestill does not know what it holds. Saying the wrong one is worse than
    the refusal it explains. `(afn)`
    """
    if blocked.verdict is AdoptionVerdict.UNREADABLE:
        return (
            f"That {side} folder could not be read well enough to say whether it is a drive "
            f"Truestill already knows - {blocked.refused} of {blocked.sampled} sampled files "
            "would not open. Registering it now could give one library two drive ids, and "
            "Truestill would count a single copy of your photos as two. Check the drive is "
            "fully mounted and readable, then try again."
        )
    return (
        f"That {side} folder already holds the library recorded as '{blocked.label}'. "
        "Registering it again would give one library two drive ids, and truestill would count "
        "a single copy of your photos as two. If this drive moved, re-attach it with "
        "'truestill drives --init <folder> --label x --adopt-existing'."
    )


def backup_preview(source: Path, target: Path, db: Path) -> BackupPreviewOk | BackupPreviewErr:
    """Preview copying the library from one connected drive to another (writes nothing).

    Reports how many files (and bytes) are missing on the target, and whether the target has room
    -- a disk-full part-way through is the failure this whole feature exists to prevent.
    """
    if not source.is_dir():
        return {
            "ok": False,
            "error": "The From folder was not found. Check the path, then pick an existing folder.",
        }
    if not target.is_dir():
        return {
            "ok": False,
            "error": "The To folder was not found. Check the path, then pick or create a folder.",
        }
    if source.resolve() == target.resolve():
        return {
            "ok": False,
            "error": "From and To point to the same folder. Pick a different destination drive.",
        }
    # Preview writes nothing, so an unregistered folder is *reported* as one that will be
    # registered rather than rejected -- the run does the registering.
    src = attach_drive(source, db, write=False)
    tgt = attach_drive(target, db, write=False)
    # Refused before anything else is computed: a folder that already holds a known library
    # must not be registered a second time, or truestill would count one copy of the user's
    # photos as two and say so on the very screen that promises redundancy ((aap)).
    for side, attachment in (("From", src), ("To", tgt)):
        if attachment.blocked_by is not None:
            return {"ok": False, "error": _blocked_message(side, attachment.blocked_by)}
    src_marker, tgt_marker = read_marker(source), read_marker(target)
    if src_marker is not None and tgt_marker is not None and src_marker.uuid == tgt_marker.uuid:
        return {
            "ok": False,
            "error": "From and To are the same drive. Pick a different backup drive.",
        }
    with open_catalog(db) as catalog:
        missing = (
            _files_missing_on_target(catalog, src_marker.uuid, tgt_marker.uuid)
            if src_marker is not None and tgt_marker is not None
            else [MissingCopy.from_row(r) for r in catalog.organized_files()]
        )
    need = sum(int(r.size or 0) for r in missing)
    free = shutil.disk_usage(target).free
    breakdown = media_breakdown([r.relative for r in missing])
    return {
        "ok": True,
        "from": src.label,
        "to": tgt.label,
        "will_register": [d.label for d in (src, tgt) if d.registered],
        "will_read": src.linked + tgt.linked,
        "count": len(missing),
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "bytes": need,
        "free": free,
        "enough": free >= need * _FREE_SPACE_MARGIN,
    }


class BackupRunSummary(TypedDict):
    copied: int
    to: str
    photos: int
    videos: int
    audio: int
    bytes_copied: int
    #: Files this run could not copy. `ENGINEERING_STANDARD.md` §4 Errors: one bad file does not
    #: abort the batch, so it is counted and named rather than ending the run. `(afw)` Stage 4.
    failed: int
    #: ⚠ **`bool`, and it was `Literal[True]` until 2026-08-23** - the type itself asserted the
    #: claim, so mypy would have rejected the honest value. That is worth more than the flag: an
    #: invariant baked into a type is one nothing can report a violation of.
    verified: bool
    target_path: str
    elapsed_seconds: NotRequired[float]


def _nothing_copied(label: str, target: Path) -> BackupRunSummary:
    """The summary for a run that stopped before copying anything. Still ``verified``: nothing
    was written, so nothing went unchecked."""
    return {
        "copied": 0,
        "failed": 0,
        "to": label,
        "photos": 0,
        "videos": 0,
        "audio": 0,
        "bytes_copied": 0,
        "verified": True,
        "target_path": str(target),
    }


def _stop_if_ground_moved(health: RunHealth | None, *, ahead: int, written: int) -> None:
    """Stop the backup if the ground under it has moved. Silent when all is well.

    **Raised, not returned, because this loop already stops this way**: an unverifiable copy
    raises `ValueError` a few lines into the loop and the app renders it as the run's error. A
    second mechanism for the same class of event would be a second thing to keep in step. What
    was copied is already recorded per file, so the next run resumes from there.
    """
    if health is None:
        return
    verdict = health.check(largest_remaining=ahead, written_bytes=written)
    if not verdict.ok:
        raise ValueError(verdict.detail)


@dataclass(frozen=True, slots=True)
class CopyVerdict:
    """What happened to one file: its digest, or why it could not be copied. `(afw)` Stage 4.

    ⚠ **Returned rather than raised, and that is the whole of the policy change.** Until
    2026-08-23 a per-file failure raised out of the loop and ended the run, against
    `ENGINEERING_STANDARD.md` §4 Errors - *"one bad file never aborts a batch - it is logged,
    counted, and reported at the end."* Organize has always continued
    (`organizer.py`'s `except (OSError, DestinationError)` records `FAILED` and does not break);
    backup was the surface that did not.

    🔑 **A return value rather than organize's `except` clause, deliberately.** Organize catches
    because its failure is raised several frames down inside `_execute_one`. Backup's is one call
    away, so an outcome is *explicit* where a caught exception would be incidental - and it
    removes a real collision: the mismatch used to be a `ValueError`, which is also what
    `_stop_if_ground_moved` raises to **stop the run**. One type meaning both *"skip this file"*
    and *"stop everything"* is this repo's signature defect, and after this change a `ValueError`
    in the copy loop means exactly one thing.
    """

    digest: str | None
    detail: str = ""
    #: ⚠ **Will the next file hit this too?** `(agi)`. A per-file failure is skipped and counted;
    #: a condition that outlives the file stops the run, because continuing buys N failures
    #: describing one condition. Decided by `drive_unwritable.persists_for_the_run`, which is the
    #: only place that question is answered in this product.
    persistent: bool = False
    #: The `OSError` behind a failure, kept so an abort can re-raise **it** rather than a fresh
    #: exception. ⚠ A newly constructed `OSError(detail)` has `errno=None`, so anything downstream
    #: that wanted to classify it again - or word it through `drive_unwritable` - would get
    #: nothing. The first draft of `(agi)` did exactly that.
    error: OSError | None = None

    @property
    def ok(self) -> bool:
        return self.digest is not None


def _copy_verified(source_file: Path, dst: Path, rel: str, want: str | None) -> CopyVerdict:
    """Copy one file and give it the real name **only if its bytes verify** - `(abu)`, `(acj)`.

    **The window this closes, and why `(abu)`'s fix did not reach it.** That fix was aimed at the
    copy: it removed a partial after `copy2` died. This is the step *after* the copy - the file
    was written whole, at its real name, and only then hashed. A copy that failed to verify was
    therefore sitting at the organized name for the length of a full re-read of its own bytes,
    and was then unlinked. Same shape as the defect, one step later, and nothing noticed because
    the copy itself had succeeded.

    Staging removes the window rather than shortening it: the bytes are hashed where they are
    staged, and a mismatch abandons them without the target ever being written.

    **`want` may be `None`** - a row with no recorded hash is unverifiable, not suspect, and the
    copy is committed as before. That is `verify`'s `UNVERIFIABLE` distinction, not a new one.

    When a cleanup itself fails the staged bytes survive and the message says where and how big:
    the run stops either way, and the user should not have to hunt 800 MB down.

    Returns the digest on success, because the caller records it as `copy_sha256`; on
    failure a :class:`CopyVerdict` carrying the reason, which the caller counts and names.
    """
    staged = staged_copy(source_file, dst)
    if not staged.ok:
        assert staged.error is not None
        lasting = persists_for_the_run(staged.error)
        if staged.leftover is None:
            return CopyVerdict(
                None,
                f"copying {rel} failed: {staged.error}",
                persistent=lasting,
                error=staged.error,
            )
        # ⚠ The leftover matters MOST on a persistent failure: a full disk may refuse the cleanup
        # too, so these bytes are both unremovable and part of what filled it. `(agi)`
        return CopyVerdict(
            None,
            f"copying {rel} failed: {staged.error}. {staged.leftover_bytes:,} bytes are still "
            f"at {staged.leftover} and could not be removed.",
            persistent=lasting,
            error=staged.error,
        )

    assert staged.temp is not None
    # Hashed unconditionally, exactly as before: the digest is not only the check, it is what
    # `record_copy` stores as `copy_sha256`. Computing it only when there is something to compare
    # against would leave a row with no recorded hash - the UNVERIFIABLE case this path exists to
    # stop propagating.
    written = sha256_file(staged.temp)
    if want is not None and written != want:
        # Verified BEFORE it takes the name: a copy that does not match is never at the real path
        # for any interval at all, so nothing downstream can read it and nothing has to undo it.
        staged.abandon()
        # ⚠ No longer *"stopping to stay safe"*: the file is skipped, counted and named, and the
        # run carries on. Nothing was written at the target, so skipping costs this file and
        # nothing else - which is precisely the condition `ENGINEERING_STANDARD.md` §4 Errors'
        # partial-failure policy describes. `(afw)` Stage 4.
        return CopyVerdict(None, f"copy of {rel} did not match what was recorded for it.")

    outcome = staged.commit()
    if outcome.ok:
        return CopyVerdict(written)
    assert outcome.error is not None
    lasting = persists_for_the_run(outcome.error)
    if outcome.leftover is None:
        return CopyVerdict(
            None,
            f"copying {rel} failed: {outcome.error}",
            persistent=lasting,
            error=outcome.error,
        )
    return CopyVerdict(
        None,
        f"copying {rel} failed: {outcome.error}. {outcome.leftover_bytes:,} bytes are still "
        f"at {outcome.leftover} and could not be removed.",
        persistent=lasting,
        error=outcome.error,
    )


@dataclass(frozen=True, slots=True)
class _CopyRun:
    """Everything one backup copy loop needs that does not change while it runs. `(afw)`

    **A context object rather than eleven parameters**, which is `IMPLEMENTATION_STANDARDS.md`'s
    complexity rule answered by naming the group instead of suppressing the count - the same
    reasoning `MissingCopy` records for itself (audit F8): these travel together, and a caller
    must not be able to pass them in the wrong order.
    """

    catalog: Catalog
    source: Path
    target: Path
    marker: DriveMarker
    missing: Sequence[MissingCopy]
    ahead: list[int]
    device: DestinationDevice
    health: RunHealth | None
    record: Callable[[dict[str, str], Sequence[tuple[str, str]], tuple[str, str] | None], None]


def _stop_the_run(verdict: CopyVerdict) -> NoReturn:
    """Re-raise a persistent failure so the loop's handler records and the run ends. `(agi)`

    ⚠ **Raises the ORIGINAL error's errno**, not a bare `OSError(detail)`. A freshly constructed
    one carries `errno=None`, so nothing downstream could classify it again or word it through
    `drive_unwritable` - and the first draft of this change did exactly that. The chained cause
    keeps the original traceback as well.

    A named function rather than a `raise` inside the loop: it says what the raise MEANS at the
    call site, which a bare `raise` in a branch does not.
    """
    assert verdict.error is not None, "a persistent verdict always has an error behind it"
    raise OSError(verdict.error.errno, verdict.detail) from verdict.error


def _copy_entries(
    missing: Sequence[MissingCopy],
    done: dict[str, str],
    failures: Sequence[tuple[str, str]],
) -> list[dict[str, object]]:
    """Backup's per-file record entries. `(afw)`

    **Its own key set, not organize's with nulls in it.** A backup copies catalog rows: it never
    dates, categorises or deduplicates anything, so `category`, `date_source`, `needs_review`,
    `perceptual` and the duplicate verdicts have no value here that is not an invention. Emitting
    them as ``null`` would make *"backup does not categorise"* and *"the category is unknown"* one
    value - fourteen times over, and `run_record`'s own `unreadable` comment records why one is
    already unacceptable. The `run` block's ``kind`` tells a reader which shape this is.

    ``"not attempted"`` is spelled exactly as `run_record.files_from_resolutions` spells it, for
    the reason that function gives: a missing status makes an unattempted file look like an
    unrecorded one, and those are different facts.
    """
    why = dict(failures)
    entries: list[dict[str, object]] = []
    for row in missing:
        if row.relative in done:
            status, detail = "uploaded", ""
        elif row.relative in why:
            status, detail = "failed", why[row.relative]
        else:
            status, detail = "not attempted", ""
        entries.append(
            {
                "relative": row.relative,
                "status": status,
                "detail": detail,
                "sha256": row.sha256,
                # The digest of what was actually written - the point of verify-before-commit -
                # not the one inherited from the source row.
                "copy_sha256": done.get(row.relative),
                "size": int(row.size or 0) or None,
            }
        )
    return entries


def _recorder(
    db: Path, *, source: Path, target: Path, marker: DriveMarker, missing: Sequence[MissingCopy]
) -> Callable[[dict[str, str], Sequence[tuple[str, str]], tuple[str, str] | None], None]:
    """Bind what is fixed for this run and return the one call the loop makes. `(afw)`

    ⚠ **`except Exception`, not `except OSError`, and that is the whole reason this exists.**
    `write_run_record` already returns a string rather than raising on `OSError`, but this is
    called from inside an `except` block: anything it *does* raise - a `TypeError` from
    `json.dumps` on a value that will not serialise - would **replace the exception being
    handled**, turning a read-only disk into a `TypeError` about paperwork. That is the failure
    this stage exists to prevent, arriving one level up from where it was found.
    `IMPLEMENTATION_STANDARDS.md` §1: *"Its own failure must never fail the run"*, the promise
    `decisions.write_decisions` already makes.

    `BaseException` is deliberately not caught, per `(aet)`: a wrapper that ate a
    `KeyboardInterrupt` would make Ctrl-C stop working on the operation people most want to stop.
    """

    def record(
        done: dict[str, str],
        failures: Sequence[tuple[str, str]],
        aborted: tuple[str, str] | None,
    ) -> None:
        try:
            # ⚠ **`attempted` counts every file the run REACHED, successes and failures alike.**
            # Until `(afw)` Stage 4 a failure ended the run, so one failed entry was the most
            # there could be and `+ 1` was right. Under the partial-failure policy there can be
            # many, and `+ 1` would understate `attempted` and therefore OVERSTATE
            # `never_attempted` - a record claiming files were skipped that were in fact tried
            # and failed. Two different facts, and the arithmetic has to keep them apart.
            attempted = len(done) + len(failures)
            stopped: dict[str, object] | None = None
            if aborted is not None:
                # 🔑 `stopped` is present ONLY on an abort. A run that finished with failures
                # reports `stopped: null` and a non-zero `failed` count; a run that stopped
                # reports both. That is what lets a reader tell the two apart.
                stopped = {
                    "never_attempted": len(missing) - attempted,
                    "reason": aborted[1],
                }
            payload = build_run_record(
                RunHeader(
                    kind="backup",
                    source=str(source),
                    destination=str(target),
                    destination_uuid=marker.uuid,
                    destination_label=marker.label,
                ),
                files=_copy_entries(missing, done, list(failures) + ([aborted] if aborted else [])),
                intended_total=len(missing),
                attempted=attempted,
                stopped=stopped,
            )
            record_organize(db, payload)
        except Exception:
            # Swallowed on purpose, argued above: the run's own outcome must survive its
            # paperwork. `BLE001`/`S110` are not enabled here, so there is nothing to suppress
            # and this comment is the enforcement - as `(aet)` records for its own broad catch.
            pass

    return record


def _copy_missing(
    run: _CopyRun, progress: ProgressCallback, cancel: threading.Event
) -> tuple[int, list[str], int, list[tuple[str, str]]]:
    """Copy every missing file, writing the run record whether or not it finishes. `(afw)`

    Lifted out of `backup_run` so that function stays under its statement ceiling. A **nested**
    function would not have done: ruff counts nested statements against the enclosing function
    either way, which is worth knowing before anyone tries it again.
    """
    copied, copied_bytes = 0, 0
    copied_names: list[str] = []
    #: relative -> the digest actually written, for every copy that completed.
    done: dict[str, str] = {}
    #: (relative, why) for every file that could not be copied. A LIST, not one entry: under
    #: `ENGINEERING_STANDARD.md` §4 Errors there can be many, and a record holding only the last
    #: would be the shape `(afd)` capped a failure list into. `(afw)` Stage 4.
    failures: list[tuple[str, str]] = []
    # ⚠ **Bound BEFORE the try, and this is not defensive style.** `row` is the loop variable, so
    # a raise from `_stop_if_ground_moved` on the FIRST iteration - or from `enumerate` itself -
    # leaves it unbound, and naming it in the handler would raise `NameError` **inside the
    # handler**, replacing the original exception with one about the record. That is precisely
    # the failure this record exists to survive, one level up.
    attempting: MissingCopy | None = None
    try:
        for index, row in enumerate(run.missing):
            if cancel.is_set():
                break
            attempting = row
            _stop_if_ground_moved(run.health, ahead=run.ahead[index], written=copied_bytes)
            rel = row.relative
            dst = run.target / rel
            run.device.check(run.target)
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Verify-before-commit: the hash is taken on the staged copy, so a bad one never
            # wears the real name even briefly.
            verdict = _copy_verified(run.source / rel, dst, rel, row.verify_sha)
            if not verdict.ok:
                if verdict.persistent:
                    # ⚠ **In FRONT of the watcher, not instead of it** (`(agi)`). This is the fast
                    # path for a condition we can name from the errno; `_stop_if_ground_moved`
                    # above stays the backstop for the ones we cannot - a disk filled by another
                    # process, a mount that goes between ticks. They cannot fight: only one
                    # exception leaves this loop, and both land in the same handler, so the
                    # record shape is identical either way.
                    _stop_the_run(verdict)
                # ⚠ **Counted, named, and the run carries on.** `ENGINEERING_STANDARD.md` §4
                # Errors. Nothing was written at the target - `staged_copy` never touches it -
                # so skipping costs this file and nothing else.
                failures.append((rel, verdict.detail))
                attempting = None
                progress(Progress(copied, len(run.missing), Phase.COPYING, Path(rel).name))
                continue
            written = verdict.digest
            assert written is not None
            run.catalog.record_copy(
                sha256=row.sha256,
                drive_uuid=run.marker.uuid,
                relative=rel,
                # The hash of the copy just written, not the one inherited from the source row.
                # Authoritative by construction, and it means a copy made by backup can never be
                # the UNVERIFIABLE case - the unknown stops propagating here.
                copy_sha256=written,
                size=int(row.size or 0) or None,
            )
            run.catalog.mark_copy_verified(
                sha256=row.sha256, drive_uuid=run.marker.uuid, when=_now()
            )
            copied += 1
            copied_names.append(rel)
            copied_bytes += int(row.size or 0)
            done[rel] = written
            attempting = None
            progress(Progress(copied, len(run.missing), Phase.COPYING, Path(rel).name))
    except Exception as exc:
        # ⚠ **An ABORT reaches here, and only an abort, since `(afw)` Stage 4.** A bad *file* no
        # longer raises - `_copy_verified` returns a verdict and the loop carries on
        # (`ENGINEERING_STANDARD.md` §4 Errors). What still raises past this point is a guard
        # above the copy saying stop: `_stop_if_ground_moved` or `device.check`. The record is
        # written and the exception re-raised UNCHANGED.
        # An ABORT: a guard above the copy said stop. The record gets the per-file failures so
        # far AND the stop, which are different facts - `never_attempted` is non-zero only here.
        aborted = (attempting.relative, str(exc)) if attempting is not None else ("", str(exc))
        run.record(done, failures, aborted)
        raise
    run.record(done, failures, None)
    return copied, copied_names, copied_bytes, failures


def _largest_copy_ahead(missing: Sequence[MissingCopy]) -> list[int]:
    """For each position, the biggest copy at or after it. A suffix maximum in one pass.

    Sizes come from the catalog rows this loop already holds - no `stat`, and none is wanted:
    the point of watching is to cost nothing next to the copying.
    """
    suffix = [0] * (len(missing) + 1)
    for index in range(len(missing) - 1, -1, -1):
        suffix[index] = max(suffix[index + 1], int(missing[index].size or 0))
    return suffix


def backup_run(source: Path, target: Path, db: Path) -> JobTarget:
    """Build a job that copies the library to another drive: verify-after-write, record each copy."""

    def target_job(progress: ProgressCallback, cancel: threading.Event) -> BackupRunSummary:
        if not source.is_dir() or not target.is_dir():
            message = "both the 'from' and 'to' folders must exist."
            raise ValueError(message)
        # Register whatever is not yet a drive, and attach a library organized before its
        # folder was registered. Without this the app rejects the very library it just built.
        # Attach reads every copy it links to establish that drive's own hashes, so it takes
        # the job's progress and cancel: on an unattached library this is the long part of the
        # run, and it must be visible and stoppable rather than a silent wait before copying.
        attach_drive(source, db, write=True, progress=progress, cancel=cancel)
        attach_drive(target, db, write=True, progress=progress, cancel=cancel)
        src_marker, tgt_marker = read_marker(source), read_marker(target)
        if src_marker is None or tgt_marker is None:
            raise not_a_drive(source if src_marker is None else target, db)
        if src_marker.uuid == tgt_marker.uuid:
            message = "the 'from' and 'to' folders are the same drive."
            raise ValueError(message)
        if cancel.is_set():
            # Stopped during attach. What was hashed is recorded and the next run resumes from
            # there. Returning here rather than falling through means a cancelled run cannot be
            # answered with "not enough space" - a true statement about a run nobody asked to
            # continue, and a confusing one to be handed after pressing stop.
            return _nothing_copied(tgt_marker.label, target)
        with open_catalog(db) as catalog:
            missing = _files_missing_on_target(catalog, src_marker.uuid, tgt_marker.uuid)
            need = sum(int(r.size or 0) for r in missing)
            free = shutil.disk_usage(target).free
            if free < need * _FREE_SPACE_MARGIN:
                message = (
                    f"not enough space on {tgt_marker.label}: needs {_gb(need)}, "
                    f"only {_gb(free)} free."
                )
                raise ValueError(message)
            copied = 0
            copied_names: list[str] = []
            copied_bytes = 0
            # A backup writes into a mounted drive for as long as an organize does, and the
            # verify-after-write below cannot catch a dropped mount: it would re-read the copy
            # we just made on the LOCAL disk and find it correct. The guard has to stop the
            # folder being created at all -- see `DestinationDevice`.
            device = DestinationDevice()
            # The free-space check above measures `target`. On a mounted cloud drive that is the
            # REMOTE's free space, while the disk that actually fills is this computer's - the
            # client caches everything written to it. That is the confusion `RunHealth` exists to
            # correct, and backup had it too. The device half is already covered above, and more
            # strictly: `device.check` fails closed on the first bad reading.
            health = watcher_for(target, db)
            ahead = _largest_copy_ahead(missing)
            copied, copied_names, copied_bytes, failures = _copy_missing(
                _CopyRun(
                    catalog=catalog,
                    source=source,
                    target=target,
                    marker=tgt_marker,
                    missing=missing,
                    ahead=ahead,
                    device=device,
                    health=health,
                    record=_recorder(
                        db, source=source, target=target, marker=tgt_marker, missing=missing
                    ),
                ),
                progress,
                cancel,
            )
            catalog.set_setting(BACKUP_PATH_HINT, str(target))
        breakdown = media_breakdown(copied_names)
        return {
            "copied": copied,
            "to": tgt_marker.label,
            "photos": breakdown["photos"],
            "videos": breakdown["videos"],
            "audio": breakdown["audio"],
            "bytes_copied": copied_bytes,
            "failed": len(failures),
            # ⚠ **DERIVED, never asserted** (`(afw)` Stage 4). This was the literal `True`, and
            # the comment justifying it said *"a copy that failed that check aborts the run"* -
            # which stopped being true the moment one bad file stopped aborting. A custody
            # product cannot ship a record claiming verification it did not perform: that is
            # BackInTime #1587's shape, where per-file failures reported only through an exit
            # code left users believing the backup was fine.
            "verified": not failures,
            "target_path": str(target),
        }

    return target_job
