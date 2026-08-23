"""What a run did, per file, written beside the catalog. `(afl)`, moved to core by `(afu)`.

`IMPLEMENTATION_STANDARDS.md` §1 states this as a **product** invariant - *"a run that changes the
library writes down what it did, beside the catalog, without being asked… automatic because the
user who most needs it is the one who did not know to ask"*.

⚠ **AND IT SHIPPED IN `truestill-cli`, WHICH THE APP IS FORBIDDEN TO IMPORT.** `(afl)` touched
`cli.py` and `app_paths.py`: the *constant* went to the shared package and the *logic* did not, so
`truestill-app` - the surface §1's own justification names, since a person typing
`truestill organize` is precisely the one who could have passed ``--report`` - **could not have
called this even had someone thought of it.** That is `ENGINEERING_STANDARD.md` §4's fifty-sixth
member with a **structural** cause rather than an oversight: not a rule nobody carried across, but
one the package boundary made unreachable. `(afu)`

**So the shape here follows `run_health.watcher_for`'s**, which argues it in its own words: taking
plain values rather than a `Destination` and a `Catalog` keeps this module free of both imports,
and keeps the two callers honest about what they are asking for. The CLI's arg-reaching stays in
the CLI.
"""

from __future__ import annotations

import contextlib
import gzip
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from truestill_core.app_paths import (
    RUN_INDEX_FILENAME,
    record_path_for,
    run_index_for,
    runs_dir_for,
    superseded_record_path,
)
from truestill_core.drive_lock import DriveBusyError, lock_for
from truestill_core.models import ActionResult, ActionStatus, DuplicateMatch, Resolution
from truestill_core.undo import UndoOutcome, UndoPlan, classify

#: Bumped when a reader would have to change. `decisions.FORMAT_VERSION`'s precedent: a document
#: a person or a later version may read says which shape it is, rather than being sniffed.
#:
#: ⚠ **2 since 2026-08-23** (`(afw)`): the ``run`` block gained ``kind``, and the shape of a
#: ``files`` entry now depends on it. A reader that assumed every entry carries ``category`` and
#: ``date_source`` was right for every record written before this and is wrong for a backup's.
#: **That is exactly the condition this constant exists to announce**, so it is announced rather
#: than left to be discovered by a reader that gets a `KeyError`.
#: ⚠ **3 since `(afw)`'s undo stage**: a `files` entry's shape depends on `run.kind`, and `undo`
#: is a third shape. A reader written against 2 knows `organize` and `backup` and would meet
#: unknown keys silently, which is the one thing a format number exists to prevent.
RUN_RECORD_FORMAT = 3

#: How many bytes of superseded per-file detail to keep. ⚠ **MEASURED, not chosen**: a real
#: 33,000-file in-place run over `~/TruestillLibrary` produced a **36.9 MiB** record beside an
#: **8.0 MiB** catalog - the record is **4.6x the catalog it describes**, so keeping every one
#: forever is not an option. Compressed it is 2.5 MiB (6.9%), so this budget holds roughly
#: twenty-five full-library runs or thousands of ordinary ones.
#:
#: ⚠ **A BYTE BUDGET RATHER THAN A COUNT, and that is the point of measuring.** Run sizes span
#: four orders of magnitude; "keep the last 50" would hold 1.8 GB for one user and 100 KB for
#: another. Bytes adapt; counts do not.
DETAIL_BUDGET_BYTES = 64 * 1024 * 1024


def _match_json(match: DuplicateMatch | None) -> dict[str, object] | None:
    if match is None:
        return None
    return {
        "kind": match.kind.value,
        "matched_path": match.matched_path,
        "origin": match.origin,
        "distance": match.distance,
    }


def stop_block(
    resolutions: list[Resolution], results: list[ActionResult]
) -> dict[str, object] | None:
    """What the run never got to, or ``None`` if it got to everything.

    ⚠ **A record silent about what was never tried READS AS COMPLETE AND IS NOT** - the same shape
    as `unreachable` meaning four things in `(afa)`. So the gap is stated, and `intended_total`
    against `attempted` shows it even to a reader who ignores this block. `(afl)`

    **The reason is read from the last result, and only because of a reachability fact.** `execute`
    stops in three places: a cancel that records nothing, a health stop, and a catalog stop. The
    last two record a `FAILED` result carrying the sentence first. ⚠ **It is still not asserted**:
    if the results are short and the last is not a failure, this says the reason was not recorded
    rather than inventing one from the file that happened to be last.

    ⚠ **THE SILENT CASE IS REACHABLE FROM THE APP AND WAS NOT FROM THE CLI** (`(afu)`). This
    docstring used to close *"the CLI passes no `cancel`, so the silent one is unreachable from
    here"* - true of that caller and **false of `truestill-app`**, which passes a `cancel` event
    and whose `execute` breaks on it with partial results whose last entry is not `FAILED`. A
    caller that knows why it stopped **passes ``stopped`` explicitly** rather than letting this
    derive *"the reason was not recorded"* about a reason it had in hand.
    """
    if len(results) == len(resolutions):
        return None
    last = results[-1] if results else None
    recorded = last.detail if last is not None and last.status is ActionStatus.FAILED else ""
    return {
        "never_attempted": len(resolutions) - len(results),
        "reason": recorded or "the run stopped early, and the reason was not recorded",
    }


def files_from_resolutions(
    resolutions: list[Resolution], results: list[ActionResult]
) -> list[dict[str, object]]:
    """Organize's per-file entries: the plan joined to what actually happened to each file.

    **The adapter half of the split** (`(afw)`). :func:`build_run_record` used to take
    `Resolution` objects directly, which made it organize-shaped in its signature *and* in every
    key it emitted - `category`, `date_source`, `needs_review`, `perceptual`, the duplicate
    verdicts. Backup has none of those: it copies catalog rows and never dates or categorises
    anything, so it could only have filled fourteen keys with `null`.

    ⚠ **Fourteen nulls would have rebuilt the defect this file already fixed once.** The
    `unreadable` comment below records why a `null` that means two things is not acceptable here;
    a `null` `category` meaning *"backup does not categorise"* and *"the category is unknown"*
    alike is the same shape fourteen times over. So each surface emits the keys that are **true**
    for it, and the `run` block says which shape a reader is holding.
    """
    by_source = {str(r.resolution.decision.source): r for r in results}
    files: list[dict[str, object]] = []
    for resolution in resolutions:
        source_path = str(resolution.decision.source)
        outcome = by_source.get(source_path)
        files.append(
            {
                "source": source_path,
                # ⚠ Not `null` for a file the run never reached: "attempted" is the fact, and a
                # missing status would make an unattempted file look like an unrecorded one.
                "status": outcome.status.value if outcome is not None else "not attempted",
                "detail": outcome.detail if outcome is not None else "",
                "landed_at": (
                    outcome.final_relative.as_posix()
                    if outcome is not None and outcome.final_relative is not None
                    else None
                ),
                "planned_relative": resolution.decision.relative.as_posix(),
                "category": resolution.decision.category.label,
                "confidence": resolution.decision.category.confidence.value,
                "rule": resolution.decision.category.rule,
                "reason": resolution.decision.category.reason,
                "captured_at": (
                    resolution.decision.captured_at.isoformat()
                    if resolution.decision.captured_at
                    else None
                ),
                "date_source": resolution.decision.date_source.value,
                "date_tag": resolution.decision.date_tag,
                "needs_review": resolution.decision.needs_review,
                "sha256": (outcome.sha256 if outcome is not None else None)
                or resolution.hashes.sha256,
                "perceptual": resolution.hashes.perceptual,
                # ⚠ **WITHOUT THIS THE RECORD REPRODUCES THE CONFLATION `(aac)` EXISTS TO END.**
                # An unreadable file the run never reached recorded `"not attempted"` with a null
                # `sha256` - which is also exactly what the size pre-filter's legitimate skip
                # looks like, so a reader could not tell *"truestill could not read this"* from
                # *"truestill correctly did not hash this"*. `FileHashes.unreadable` is the field
                # that already tells them apart everywhere else; it was simply not emitted here.
                # Fixed before anything relied on the record, and on both surfaces at once because
                # there is now only one builder. `(afu)`
                "unreadable": (
                    resolution.hashes.unreadable.value
                    if resolution.hashes.unreadable is not None
                    else None
                ),
                "should_upload": resolution.should_upload,
                "is_unique": resolution.is_unique,
                "exact_duplicate": _match_json(resolution.exact_duplicate),
                "near_duplicate": _match_json(resolution.near_duplicate),
            }
        )
    return files


@dataclass(frozen=True, slots=True)
class RunHeader:
    """Who wrote a run record, and where the run wrote to. `(afw)`

    **A value rather than five parameters**, which is `IMPLEMENTATION_STANDARDS.md`'s complexity
    rule answered by naming the group. It also keeps the identity pair together, which is the
    point of it: ``destination_uuid`` is **authoritative** and ``destination_label`` is the human
    name beside it. A label can be renamed in Settings, and a record naming a since-relabelled
    drive is unresolvable - which defeats the record.

    ``kind`` is what lets one file hold two shapes honestly: a reader branches on it rather than
    guessing which keys a ``files`` entry carries.
    """

    kind: str
    source: str
    destination: str
    destination_uuid: str | None = None
    destination_label: str | None = None
    #: The run this one reversed, for ``kind="undo"``. ⚠ **Without it an undo record says "16
    #: files moved back" and nothing connects it to the run that moved them** - and those two
    #: documents are exactly the pair a person needs together. `(afw)`
    undid_run_id: str | None = None


def build_run_record(
    header: RunHeader,
    *,
    files: list[dict[str, object]],
    intended_total: int,
    attempted: int,
    stopped: dict[str, object] | None,
) -> dict[str, object]:
    """The record one run leaves behind. **Built from what happened, never from the plan.**

    ⚠ Until 2026-08-22 this was written from `resolutions`, before execution, and only when asked
    for - so it recorded what was **decided** and never what happened. Nothing else in the product
    persisted an outcome either: `files.upload_status` only ever holds ``'uploaded'``, so a row
    exists only for a file that succeeded, and there is no logging anywhere. **After the terminal
    scrolled, nothing could answer "which photos failed?"** `(afl)`

    **Generic since 2026-08-23** (`(afw)`): it takes already-shaped ``files`` and the two counts,
    so a second surface can record a run without owning organize's vocabulary. The adapters are
    :func:`files_from_resolutions` for organize and `service/backup.py`'s `_copy_entries`.
    """
    run: dict[str, object] = {
        "kind": header.kind,
        "source": header.source,
        "destination": header.destination,
        # `intended_total` matches `organize_runs`, which already derives "stopped early" the
        # same way rather than trusting a completion flag. One vocabulary for one idea.
        "intended_total": intended_total,
        "attempted": attempted,
        "stopped": stopped,
    }
    # ⚠ **Absent rather than ``null`` where the caller has no drive identity to give.** A `null`
    # here would mean *"this run wrote to no registered drive"* and *"this surface does not record
    # which"* alike - the two-states-one-value shape this file argues against fourteen keys up,
    # and the one `(aek)` and `(aft)` each removed from a different module. Organize omits them
    # today; that it COULD supply them is a gap named in `(afw)`, not a null to fill in later.
    if header.destination_uuid is not None:
        run["destination_uuid"] = header.destination_uuid
    if header.destination_label is not None:
        run["destination_label"] = header.destination_label
    if header.undid_run_id is not None:
        run["undid_run_id"] = header.undid_run_id
    # ⚠ **Stamped, and the stamp is load-bearing rather than decorative.** A superseded record is
    # filed under this time, so it is what makes `runs/` sort chronologically and what lets an
    # unindexed detail file still identify itself. Without it the name was `unknown-...-unknown`,
    # which carries nothing and defeats the rebuild route the index relies on.
    run["written_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    return {"format": RUN_RECORD_FORMAT, "run": run, "files": files}


def write_run_record(path: Path, payload: dict[str, object]) -> str | None:
    """Write the record atomically. **Returns an error to report, never raises.**

    ⚠ **Never-raising matters more here than it did for `--report`.** This is written on every
    applied run rather than on request, so an unwritable location would turn a successful organize
    into a traceback about its own paperwork. `decisions.write_decisions` makes the same choice for
    the same reason, and `selfcheck.write_findings` is where the sibling-then-rename comes from: no
    reader may ever open a half-written file.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_name(path.name + ".partial")
        partial.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        partial.replace(path)
    except OSError as exc:
        return str(exc)
    return None


def files_from_undo(plan: UndoPlan, outcome: UndoOutcome) -> list[dict[str, object]]:
    """Undo's per-file entries: what each journalled move became when it was reversed. `(afw)`

    **Its own key set, not organize's with nulls in it**, for the reason `_copy_entries` gives:
    undo does not date, categorise or deduplicate anything, so `category`, `date_source`,
    `perceptual` and the duplicate verdicts have no value here that is not an invention.

    ⚠ **THREE OUTCOMES, NOT TWO, AND ONLY ONE IS A FAILURE.** `undo.SkipClass` is the one place
    that decides which, and this reads it rather than re-deriving it - the third copy of a rule is
    where the copies disagree. A reader can tell *"there was nothing to undo"* from *"you can fix
    this and re-run"* from *"we could not do it"* without counting anything.
    """
    entries: list[dict[str, object]] = [
        {
            "restored_to": str(step.original),
            "from": str(step.current),
            "sha256": step.sha256,
            "status": "restored",
            "outcome_class": None,
            "detail": "",
        }
        for step in plan.steps
        if not any(item.step is step for item in outcome.skipped)
    ]
    entries.extend(
        {
            "restored_to": str(item.step.original),
            "from": str(item.step.current),
            "sha256": item.step.sha256,
            "status": item.reason.value,
            # The class, beside the reason, so a reader branches on three states rather than
            # memorising which of seven reasons are failures.
            "outcome_class": (klass.value if (klass := classify(item.reason)) else None),
            "detail": item.detail,
        }
        for item in outcome.skipped
    )
    return entries


def undo_stop_block(outcome: UndoOutcome) -> dict[str, object] | None:
    """What an undo did not get to, or ``None`` if it got to everything. `(afw)`

    ⚠ **`stop_block` is NOT reusable here**, and the reason is structural rather than stylistic:
    it computes `never_attempted` as ``len(resolutions) - len(results)`` and reads the reason from
    the **last** result. Undo's unattempted files are not a suffix - skips interleave with
    restores, and a skip is not an attempt. Undo counts what it never reached instead.
    """
    if outcome.stopped is None:
        return None
    return {"never_attempted": outcome.stopped.never_attempted, "reason": outcome.stopped.reason}


def _prune_detail(runs: Path) -> list[str]:
    """Drop the oldest superseded detail past :data:`DETAIL_BUDGET_BYTES`. `(afw)`

    ⚠ **NO PREVIEW AND NO CONFIRMATION, and that is a ruling rather than an oversight.** This
    repo refuses automatic deletes - `reclaim` demands a typed word, `clean-empty` reports and
    never removes - because those delete **the user's photographs**. This deletes only records
    this product generated, and it cannot delete a *fact*: the index line for every run is kept
    forever, so what a prune costs is the per-file detail of an old run, never the knowledge that
    it happened. Pruning removes redundancy in time, not information about the past - which is
    the whole reason history was split from detail.

    ⚠ **The newest record cannot be reached from here**, structurally rather than by a guard: it
    is `last-run.json` beside this directory and is never a candidate.
    """
    detail = sorted(
        (p for p in runs.glob("*.json*") if p.name != RUN_INDEX_FILENAME),
        key=lambda p: p.name,
        reverse=True,
    )
    dropped: list[str] = []
    used = 0
    for path in detail:
        used += path.stat().st_size
        if used > DETAIL_BUDGET_BYTES:
            path.unlink(missing_ok=True)
            dropped.append(path.name)
    return dropped


def _supersede(catalog: Path, runs: Path) -> None:
    """Move the current `last-run.json` into ``runs/`` and compress it. `(afw)`

    ⚠ **`last-run.json` IS the newest record; it is not a symlink or a copy to one.** A symlink
    needs a privilege ordinary Windows users do not have, and Windows is a launch platform; a copy
    would duplicate 37 MiB and create two sources of truth; a small file *naming* the newest would
    break every reader that opens `last-run.json` expecting a record. Rotating on write is
    logrotate's shape and keeps the name meaning exactly what it says.

    Compression is applied on demotion only, so the newest stays directly readable by a person.
    Measured on the 33k record: **6.9%** of the original, a 15x saving for no lost information.
    """
    current = record_path_for(catalog)
    if not current.is_file():
        return
    try:
        payload = json.loads(current.read_text(encoding="utf-8"))
        run = payload["run"]
        target = superseded_record_path(
            catalog,
            started_at=str(run.get("written_at", "unknown")),
            kind=str(run.get("kind", "run")),
            run_id=str(run.get("run_id", run.get("undid_run_id", "")))[:12],
        )
    except (OSError, ValueError, KeyError, TypeError):
        # An unreadable or foreign `last-run.json` is still somebody's record: it is moved
        # aside under a name that sorts oldest rather than deleted or overwritten.
        target = runs / "unknown-run.json"
    runs.mkdir(parents=True, exist_ok=True)
    current.replace(target)
    with contextlib.suppress(OSError):
        target.with_suffix(target.suffix + ".gz").write_bytes(gzip.compress(target.read_bytes()))
        target.unlink()


def record_run(
    catalog: Path, payload: dict[str, object], *, index_line: dict[str, object]
) -> str | None:
    """Write one run's index line and its detail. **Returns an error to report, never raises.**

    `IMPLEMENTATION_STANDARDS.md`'s record rule says a record's own failure must never fail the
    run, and that holds for **both** writes here.

    ⚠ **THE INDEX LINE GOES FIRST, AND THE LINE NEVER SAYS WHETHER ITS DETAIL EXISTS.** Those two
    choices together are what make an orphan impossible:

    * index first, detail second - a failure after the line leaves a run recorded with no detail,
      which is **the same state a pruned run is in** and which every reader already handles;
    * the line asserts nothing about detail - a reader *looks* - so it can never become false,
      which matters because the index is append-only and a wrong line could never be corrected.

    Detail-first would invert both: a failed index write would leave a detail file nothing points
    at, and the only way to avoid it would be deleting the detail on failure - destroying the very
    thing being preserved. `(aem)` made the same derive-rather-than-assert choice for
    *"interrupted"*.

    ⚠ **Serialised across processes by `drive_lock`, not by `O_APPEND`.** Two runs on two drives
    share one catalog and therefore one `runs/`, and append atomicity is not guaranteed on
    Windows at all. Each line is self-contained JSON, so even a torn write damages one line and a
    reader skips it rather than losing the file.
    """
    runs = runs_dir_for(catalog)
    try:
        runs.mkdir(parents=True, exist_ok=True)
        with lock_for(runs, operation="run-record"):
            with run_index_for(catalog).open("a", encoding="utf-8") as index:
                index.write(json.dumps(index_line, sort_keys=True) + "\n")
            _supersede(catalog, runs)
            _prune_detail(runs)
    except (OSError, DriveBusyError) as exc:
        return str(exc)
    return write_run_record(record_path_for(catalog), payload)


def record_undo(catalog: Path, plan: UndoPlan, outcome: UndoOutcome) -> str | None:
    """Write an undo's record and index line. **One builder, both surfaces.** `(afw)`

    ⚠ **In core because undo has TWO callers** - `truestill_cli.cli` and
    `truestill_app.service.organize_undo` - and `truestill-app` may not import `truestill-cli`.
    `(afu)` is the recorded precedent: its builder was placed where one of its two callers could
    not reach it, and the app went without a record for it. Backup's `_copy_entries` lives in the
    app legitimately, because backup has one caller.
    """
    entries = files_from_undo(plan, outcome)
    payload = build_run_record(
        RunHeader(
            kind="undo",
            source=str(plan.dest_root),
            destination=str(plan.source_root),
            undid_run_id=plan.run_id,
        ),
        files=entries,
        intended_total=len(plan.steps) + len(plan.skipped),
        attempted=outcome.restored + len(outcome.skipped),
        stopped=undo_stop_block(outcome),
    )
    block = payload["run"]
    line: dict[str, object] = {
        "kind": "undo",
        "written_at": block.get("written_at") if isinstance(block, dict) else None,
        "run_id": plan.run_id,
        "undid_run_id": plan.run_id,
        "restored": outcome.restored,
        "skipped": len(outcome.skipped),
        "stopped": outcome.stopped is not None,
    }
    return record_run(catalog, payload, index_line=line)


def record_organize(
    catalog: Path, payload: dict[str, object], *, run_id: str | None = None
) -> str | None:
    """Write an organize or backup record with its index line. `(afw)`

    ⚠ **Every run gets a line, not just undo.** A partial index is worse than none: a superseded
    record with no line can be pruned, and then nothing anywhere says the run happened - which is
    exactly the loss the split was designed to prevent.
    """
    run = payload.get("run")
    block = run if isinstance(run, dict) else {}
    line: dict[str, object] = {
        "kind": block.get("kind", "run"),
        "written_at": block.get("written_at"),
        "intended_total": block.get("intended_total"),
        "attempted": block.get("attempted"),
        "stopped": block.get("stopped") is not None,
    }
    # ⚠ **Absent rather than ``null``**, for the reason `build_run_record` gives about
    # `destination_uuid`: a null would mean *"this run had no id"* and *"this surface does not
    # record one"* alike, which is the two-states-one-value shape this file argues against.
    if run_id is not None:
        line["run_id"] = run_id
    return record_run(catalog, payload, index_line=line)
