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

import json
from dataclasses import dataclass
from pathlib import Path

from truestill_core.models import ActionResult, ActionStatus, DuplicateMatch, Resolution

#: Bumped when a reader would have to change. `decisions.FORMAT_VERSION`'s precedent: a document
#: a person or a later version may read says which shape it is, rather than being sniffed.
#:
#: ⚠ **2 since 2026-08-23** (`(afw)`): the ``run`` block gained ``kind``, and the shape of a
#: ``files`` entry now depends on it. A reader that assumed every entry carries ``category`` and
#: ``date_source`` was right for every record written before this and is wrong for a backup's.
#: **That is exactly the condition this constant exists to announce**, so it is announced rather
#: than left to be discovered by a reader that gets a `KeyError`.
RUN_RECORD_FORMAT = 2


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
