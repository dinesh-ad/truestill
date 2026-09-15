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

**Complexity** (`IMPLEMENTATION_STANDARDS.md` §8): writing is **O(n) in time and O(1) in memory**
over the entry count, since `(akr)`; reading through :func:`iter_record_entries` is the same. Only
:func:`read_record` is O(n) in memory, and its name and docstring say so. It was O(n) in memory
until `(akr)` - 750 MiB peak at 300,000 files, measured in `PERFORMANCE.md` §1.3.

**So the shape here follows `run_health.watcher_for`'s**, which argues it in its own words: taking
plain values rather than a `Destination` and a `Catalog` keeps this module free of both imports,
and keeps the two callers honest about what they are asking for. The CLI's arg-reaching stays in
the CLI.
"""

from __future__ import annotations

import contextlib
import gzip
import json
import shutil
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

from truestill_core.app_paths import (
    LEGACY_RUN_RECORD_FILENAME,
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
RUN_RECORD_FORMAT = 4

#: ⚠ **4 since `(akr)`: the record is JSON LINES, and that is a whole-file shape change.** A
#: reader written against 3 opened one JSON document with ``format``, ``run`` and ``files`` keys
#: and would now get a `JSONDecodeError` on the second line. **Nothing in the product reads a
#: record** (`(ahm)`'s null, re-run and still true on 2026-09-15), so no reader was migrated -
#: what this number announces is for a person holding an old file, and for the tests.
#:
#: **Why the shape changed**: format 3 assembled the whole record in memory and serialised it with
#: one ``json.dumps``. Measured at 300,000 files, that peaked at **750.2 MiB RSS** - of which
#: **476.8 MiB** was the serialisation step alone, because the encoder's `str` and its UTF-8
#: encoding are both live at the rename. It is a cliff rather than a curve: it lands at the last
#: moment of a long run, after every file has already been copied, and takes the whole record with
#: it. JSON Lines makes the cost **proportional to one entry** instead of to the file.

#: Line kinds. A reader branches on ``type``; every line is self-contained, so a torn write costs
#: one line rather than the file - the property `record_run` already relies on for `index.jsonl`.
#:
#: ⚠ **``type`` is a RESERVED key in an entry**, and `test_no_entry_adapter_uses_a_reserved_key`
#: is what keeps it free rather than this comment. No adapter emits one today: organize, backup,
#: recover, undo, archive and cleanup between them use twenty-four other names.
LINE_RUN = "run"
LINE_FILE = "file"
LINE_END = "end"

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
) -> Iterator[dict[str, object]]:
    """Organize's per-file entries: the plan joined to what actually happened to each file.

    **The adapter half of the split** (`(afw)`). :func:`build_run_record` used to take
    `Resolution` objects directly, which made it organize-shaped in its signature *and* in every
    key it emitted - `category`, `date_source`, `needs_review`, `perceptual`, the duplicate
    verdicts. Backup has none of those: it copies catalog rows and never dates or categorises
    anything, so it could only have filled fourteen keys with `null`.

    ⚠ **A GENERATOR SINCE `(akr)`, and that is what makes the writer's memory constant.** It
    yields rather than building the list, so at 300,000 files the record costs one entry at a time
    instead of a 238 MiB list and the 476.8 MiB serialisation on top of it. ⚠ **One-shot**: the
    only consumer is `write_run_record`, which walks it exactly once.

    ⚠ **Fourteen nulls would have rebuilt the defect this file already fixed once.** The
    `unreadable` comment below records why a `null` that means two things is not acceptable here;
    a `null` `category` meaning *"backup does not categorise"* and *"the category is unknown"*
    alike is the same shape fourteen times over. So each surface emits the keys that are **true**
    for it, and the `run` block says which shape a reader is holding.
    """
    by_source = {str(r.resolution.decision.source): r for r in results}
    for resolution in resolutions:
        source_path = str(resolution.decision.source)
        outcome = by_source.get(source_path)
        yield {
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
            "sha256": (outcome.sha256 if outcome is not None else None) or resolution.hashes.sha256,
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

    #: Run-level facts a surface records beyond identity - `archive unpack`'s ``files_written``
    #: and ``bytes_written``. ⚠ **A field rather than the caller mutating the built record**,
    #: which is what `archive_extract` did until `(akr)`: ``payload["run"]["files_written"] = ...``
    #: only worked because the record was a plain dict, and it is exactly the reach a value type
    #: removes. It lives on the header rather than as a sixth argument to `build_run_record` for
    #: the reason this class exists at all, stated above - naming the group beats another
    #: parameter. Empty for every other surface.
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunSummary:
    """What the run added up to. **The trailer, written after the last entry.** `(akr)`

    ⚠ **Its absence is the signal, and that is `(aem)`'s precedent rather than a new idea.** A
    record whose last line is not an ``end`` line is a run that did not finish - derived by
    looking, never asserted by a flag that a crash would leave lying. Format 3 could not say this
    at all: it wrote one document at the very end, so an interrupted run left **no record**.
    """

    intended_total: int
    attempted: int
    stopped: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class RunRecord:
    """A record as a value: who ran, the entries, and what it added up to. `(akr)`

    ⚠ **``entries`` MAY BE A ONE-SHOT ITERATOR, and that is the whole point of the change.** It is
    consumed exactly once, by :func:`write_run_record`, streaming - so a caller that can yield its
    entries never builds the list at all. A caller that already holds a list passes it unchanged
    and loses nothing.

    ``written_at`` is stamped here rather than at write time so the index line and the record
    agree by construction: `record_organize` reads this same value.
    """

    header: RunHeader
    entries: Iterable[dict[str, object]]
    summary: RunSummary
    written_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def run_block(self) -> dict[str, object]:
        """The opening line's ``run`` fields - identity only, never the counts.

        ⚠ **The counts are deliberately NOT here.** They are only true once the last entry is
        written, and a header asserting them up front would be a promise the run has not yet
        kept - exactly the stale-flag shape `(agk)` and `(aem)` each removed elsewhere.
        """
        run: dict[str, object] = {
            "kind": self.header.kind,
            "source": self.header.source,
            "destination": self.header.destination,
        }
        # ⚠ **Absent rather than ``null`` where the caller has no drive identity to give.** A
        # `null` here would mean *"this run wrote to no registered drive"* and *"this surface does
        # not record which"* alike - the two-states-one-value shape this file argues against
        # fourteen keys up, and the one `(aek)` and `(aft)` each removed from a different module.
        if self.header.destination_uuid is not None:
            run["destination_uuid"] = self.header.destination_uuid
        if self.header.destination_label is not None:
            run["destination_label"] = self.header.destination_label
        if self.header.undid_run_id is not None:
            run["undid_run_id"] = self.header.undid_run_id
        run.update(self.header.extra)
        run["written_at"] = self.written_at
        return run


def build_run_record(
    header: RunHeader,
    *,
    files: Iterable[dict[str, object]],
    intended_total: int,
    attempted: int,
    stopped: dict[str, object] | None,
) -> RunRecord:
    """The record one run leaves behind. **Built from what happened, never from the plan.**

    ⚠ Until 2026-08-22 this was written from `resolutions`, before execution, and only when asked
    for - so it recorded what was **decided** and never what happened. Nothing else in the product
    persisted an outcome either: `files.upload_status` only ever holds ``'uploaded'``, so a row
    exists only for a file that succeeded, and there is no logging anywhere. **After the terminal
    scrolled, nothing could answer "which photos failed?"** `(afl)`

    **Generic since 2026-08-23** (`(afw)`): it takes already-shaped ``files`` and the two counts,
    so a second surface can record a run without owning organize's vocabulary. The adapters are
    :func:`files_from_resolutions` for organize and `service/backup.py`'s `_copy_entries`.

    ⚠ **It returns a value, not a payload dict, since `(akr)`**, and ``files`` is now any iterable
    rather than a list. The signature is otherwise unchanged, which is why ten call sites did not
    move: what changed is that nothing here materialises the record.
    """
    return RunRecord(
        header=header,
        entries=files,
        summary=RunSummary(intended_total=intended_total, attempted=attempted, stopped=stopped),
    )


#: Bytes between explicit flushes. ⚠ **A flush, never an `fsync` - and never per file.**
#:
#: 300,000 files would be 300,000 `fsync`s, and `fsync` is the expensive one: it waits for the
#: device. This is the **group commit** shape every storage engine exposes (PostgreSQL's
#: ``commit_delay``, MySQL's binlog group commit) - amortise a fixed cost over a batch - applied
#: to a log rather than to a WAL.
#:
#: 🔑 **A run record is not a durability primitive, which is what makes no-`fsync` correct rather
#: than merely cheap.** Nothing acks on it, nothing reads it, and re-running is free: the warm
#: re-run of an organised library uploads **zero** and skips every file as an exact duplicate.
#: A `flush` puts the bytes in the OS page cache, so the record survives the process dying - a
#: crash, a `SIGKILL`, a traceback. Only power loss can take the unflushed tail, and what it takes
#: is the last few lines of a log nobody restores from.
#:
#: ⚠ **BYTES RATHER THAN AN ENTRY COUNT, AND A SURVIVING MUTATION IS WHY.** This was
#: ``FLUSH_EVERY_ENTRIES = 1000`` and **it was inert**: `io.DEFAULT_BUFFER_SIZE` is **131,072**
#: bytes, which at the measured 942-byte organize entry fills every **139** entries, so the
#: interpreter had always flushed seven times over before entry 1000 arrived. Removing the flush
#: entirely changed nothing any test could see. An entry count also means a different real bound
#: per surface - 1000 backup entries is 80 KiB and 1000 organize entries is 920 KiB.
#:
#: 64 KiB is deliberately **tighter than the interpreter's 128 KiB**, so this is the bound that
#: binds and it is ours. `ENGINEERING_STANDARD.md` §4: *a binding clause that asserts a machine
#: state expires silently* - `io.DEFAULT_BUFFER_SIZE` is exactly such a state, and relying on it
#: would be a promise CPython could change without anything here going red.
FLUSH_EVERY_BYTES = 64 * 1024


def _write_lines(handle: IO[str], record: RunRecord) -> int:
    """Stream one record into an open handle. Returns the number of entry lines written."""
    opening: dict[str, Any] = {
        "type": LINE_RUN,
        "format": RUN_RECORD_FORMAT,
        "run": record.run_block(),
    }
    handle.write(json.dumps(opening, sort_keys=True) + "\n")
    written = 0
    unflushed = 0
    for entry in record.entries:
        # ⚠ **OURS LAST, SO OURS WINS.** Written `{"type": ..., **entry}` an adapter emitting its
        # own `type` would shadow the discriminator and make its lines unreadable as entries. No
        # adapter does today - organize, backup, recover, undo, archive and cleanup use
        # twenty-four other names - and this ordering means none ever can. **The stated cost**: an
        # entry carrying `type` loses that value in the record. `type` is reserved; it is the one
        # key an adapter may not use, and `test_an_entry_can_never_shadow_the_line_kind` is what
        # makes that a control rather than this comment.
        line = json.dumps({**entry, "type": LINE_FILE}, sort_keys=True) + "\n"
        handle.write(line)
        written += 1
        unflushed += len(line)
        if unflushed >= FLUSH_EVERY_BYTES:
            handle.flush()
            unflushed = 0
    summary = record.summary
    trailer: dict[str, Any] = {
        "type": LINE_END,
        "intended_total": summary.intended_total,
        "attempted": summary.attempted,
        # ⚠ **Derived here rather than taken from the caller.** `attempted` counts files the run
        # REACHED; this counts lines this record actually holds, and they are legitimately
        # different - an entry is emitted for a planned file the run never got to. Two numbers
        # that can be compared are what makes a truncated record detectable by a reader.
        "entries": written,
        "stopped": summary.stopped,
    }
    handle.write(json.dumps(trailer, sort_keys=True) + "\n")
    handle.flush()
    return written


def write_run_record(path: Path, record: RunRecord) -> str | None:
    """Stream the record to ``path``. **Returns an error to report, never raises.**

    ⚠ **Never-raising matters more here than it did for `--report`.** This is written on every
    applied run rather than on request, so an unwritable location would turn a successful organize
    into a traceback about its own paperwork. `decisions.write_decisions` makes the same choice for
    the same reason.

    ⚠ **WRITTEN AT ITS FINAL NAME, NOT STAGED AND RENAMED - A DELIBERATE DEPARTURE, `(akr)`.**
    `decisions.write_decisions` states the general rule this breaks: *"A truncated file at the
    right path is worse than no file, because it looks like a backup."* That reasoning is about a
    document someone RESTORES FROM, and it does not transfer here:

    * a run record is a **log**, not a restore source - nothing in the product reads one, and no
      decision anywhere is taken from its contents;
    * staging and renaming is precisely what makes the failure all-or-nothing, which is the defect
      `(akr)` exists to remove: a six-hour run that dies at the rename loses the whole record;
    * every line is self-contained, so a torn final line costs that line and a reader skips it -
      the property `record_run`'s docstring already relies on for `index.jsonl`;
    * a record with no ``end`` line **says so**, which is strictly more than the nothing format 3
      left behind.

    So the cost is stated rather than hidden: a reader must tolerate a missing trailer and a torn
    last line. :func:`read_record` does both, and `test_a_truncated_record_still_reads` pins it.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            _write_lines(handle, record)
    except OSError as exc:
        return str(exc)
    return None


@dataclass(frozen=True, slots=True)
class LoadedRecord:
    """A record read back. ``summary`` is ``None`` when the run did not finish. `(akr)`"""

    header: dict[str, object]
    entries: list[dict[str, object]]
    summary: dict[str, object] | None

    @property
    def interrupted(self) -> bool:
        """No trailer means the writer stopped before the end. Derived, never a stored flag."""
        return self.summary is None

    @property
    def run(self) -> dict[str, object]:
        """Identity and counts as one block - what a reader listing runs actually wants.

        ⚠ **The two halves are written at opposite ends of the file and that is deliberate**:
        identity is knowable when the run starts, the counts only when it ends (`RunSummary`).
        Joining them here is a *reader's* convenience and never a writer's shortcut - a header
        that asserted counts up front would be promising what the run has not yet done.

        An interrupted record contributes no counts, so a caller reading ``run["attempted"]``
        gets a `KeyError` rather than a plausible zero. That is the intended failure: absent and
        zero are different answers, which is §9's rule one surface over.
        """
        header_run = self.header.get("run")
        block = dict(header_run) if isinstance(header_run, dict) else {}
        block.update(self.summary or {})
        return block


def _open_record(path: Path) -> IO[str]:
    """Open a record, transparently through gzip for a superseded one."""
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def iter_record_lines(path: Path) -> Iterator[dict[str, object]]:
    """Yield each line of a record, streaming. **Constant memory in the file's length.**

    ⚠ **A line that does not parse is SKIPPED, not raised on.** The writer appends at the final
    name, so the last line of an interrupted record can be half a line; every complete line before
    it is still true, and losing them to a `JSONDecodeError` would throw away the evidence this
    format exists to keep.
    """
    with _open_record(path) as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                yield parsed


def iter_record_entries(path: Path) -> Iterator[dict[str, object]]:
    """Just the per-file entries, streaming, with the ``type`` tag removed."""
    for line in iter_record_lines(path):
        if line.get("type") == LINE_FILE:
            yield {k: v for k, v in line.items() if k != "type"}


def read_record(path: Path) -> LoadedRecord:
    """Read a whole record into memory. **For small records and for tests.** `(akr)`

    ⚠ **This one is NOT constant in memory and says so in its name's absence of "iter".** It
    exists because the tests and any future `truestill runs` want the whole of a small record;
    anything walking a 300,000-entry file uses :func:`iter_record_entries`, which is why both are
    here rather than only the convenient one.
    """
    header: dict[str, object] = {}
    entries: list[dict[str, object]] = []
    summary: dict[str, object] | None = None
    for line in iter_record_lines(path):
        kind = line.get("type")
        if kind == LINE_RUN:
            header = line
        elif kind == LINE_FILE:
            entries.append({k: v for k, v in line.items() if k != "type"})
        elif kind == LINE_END:
            summary = {k: v for k, v in line.items() if k != "type"}
    return LoadedRecord(header=header, entries=entries, summary=summary)


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

    ⚠ **`kind` is recorded beside the reason** (`(agl)`): a record that says only *"stopped"* makes
    a user's own cancel indistinguishable from a failing drive when it is read back weeks later,
    and the reason is a sentence nothing should have to parse.
    """
    if outcome.stopped is None:
        return None
    return {
        "kind": outcome.stopped.kind.value,
        "never_attempted": outcome.stopped.never_attempted,
        "reason": outcome.stopped.reason,
    }


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
    """Move the current record into ``runs/`` and compress it. `(afw)`

    ⚠ **`last-run.jsonl` IS the newest record; it is not a symlink or a copy to one.** A symlink
    needs a privilege ordinary Windows users do not have, and Windows is a launch platform; a copy
    would duplicate 37 MiB and create two sources of truth; a small file *naming* the newest would
    break every reader that opens it expecting a record. Rotating on write is logrotate's shape
    and keeps the name meaning exactly what it says.

    Compression is applied on demotion only, so the newest stays directly readable by a person.
    Measured on the 33k record: **6.9%** of the original, a 15x saving for no lost information.

    ⚠ **TWO MEMORY CLIFFS LIVED HERE UNTIL `(akr)`, AND NEITHER WAS THE ONE ANYBODY HAD NAMED.**
    Both were on the READ side, and both fired at the *start* of the next run rather than the end
    of this one:

    * the previous record was parsed in full - ``json.loads(current.read_text())`` - to recover
      **three header fields** for the rotated filename. At 300,000 entries that is a 238 MiB file
      read, decoded and built into Python objects to learn a timestamp, a kind and an id.
    * it was then compressed with ``gzip.compress(target.read_bytes())``, which holds the whole
      file **and** its compressed image live at once.

    Both are gone, and the format is what made it easy: the identity fields are on **line one**,
    so `readline` answers the naming question in constant memory, and `shutil.copyfileobj` streams
    the compression in 64 KiB chunks. Neither needed a design - only a format whose first line is
    self-contained.
    """
    current = record_path_for(catalog)
    legacy = current.with_name(LEGACY_RUN_RECORD_FILENAME)
    # ⚠ **The pre-`(akr)` name is rotated too, and NEVER parsed.** A catalog whose last run
    # predates the format change has a `last-run.json` beside it that supersession would otherwise
    # never touch, because supersession keys on the current name - so it would sit there forever,
    # indistinguishable from a current record to a person reading the directory. It is moved aside
    # under its own mtime; its CONTENTS are not read, because nothing reads a record and a format
    # 3 document has nothing this function needs that its mtime does not give.
    if not current.is_file() and legacy.is_file():
        stamp = datetime.fromtimestamp(legacy.stat().st_mtime, UTC).isoformat(timespec="seconds")
        runs.mkdir(parents=True, exist_ok=True)
        _demote(legacy, runs / f"{stamp.replace(':', '-')}-format3.json")
        return
    if not current.is_file():
        return
    try:
        with _open_record(current) as handle:
            opening = json.loads(handle.readline())
        run = opening["run"]
        target = superseded_record_path(
            catalog,
            started_at=str(run.get("written_at", "unknown")),
            kind=str(run.get("kind", "run")),
            run_id=str(run.get("run_id", run.get("undid_run_id", "")))[:12],
        )
    except (OSError, ValueError, KeyError, TypeError):
        # An unreadable or foreign record is still somebody's record: it is moved aside under a
        # name that sorts oldest rather than deleted or overwritten.
        target = runs / "unknown-run.jsonl"
    runs.mkdir(parents=True, exist_ok=True)
    _demote(current, target)


def _demote(current: Path, target: Path) -> None:
    """Rename a record into ``runs/`` and gzip it **streaming**, never whole-file. `(akr)`"""
    current.replace(target)
    compressed = target.with_suffix(target.suffix + ".gz")
    with contextlib.suppress(OSError):
        with target.open("rb") as raw, gzip.open(compressed, "wb") as packed:
            # 64 KiB at a time: peak is the chunk plus gzip's window, never the file.
            shutil.copyfileobj(raw, packed, length=64 * 1024)
        target.unlink()


def record_run(
    catalog: Path,
    record: RunRecord,
    *,
    index_line: dict[str, object],
    detail: bool = True,
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

    ⚠ **``detail=False`` writes the line and nothing else, for a surface that has no per-file
    truth to write.** Bake is the one (`(agm)`): `BakeOutcome` counts files and names only drives,
    so its ``files`` would be ``[]`` however large the run was. It **also skips the supersede**,
    which is the half that is easy to get wrong: rotating `last-run.json` away and then writing no
    replacement would demote a real record and leave the name meaning nothing.

    ⚠ **A line with no detail is NOT a new state** - it is the state every pruned run is already
    in, which is why the two rules above make it safe. It is also **indistinguishable** from a
    pruned run by inspection; what tells them apart is ``kind``, which the line always carries and
    which a reader is already required to branch on. Stated because it is a real limit:
    *"bake wrote no detail"* and *"this run's detail was pruned"* look identical on disk.

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
            if detail:
                _supersede(catalog, runs)
            _prune_detail(runs)
    except (OSError, DriveBusyError) as exc:
        return str(exc)
    if not detail:
        return None
    return write_run_record(record_path_for(catalog), record)


def record_undo(catalog: Path, plan: UndoPlan, outcome: UndoOutcome) -> str | None:
    """Write an undo's record and index line. **One builder, both surfaces.** `(afw)`

    ⚠ **In core because undo has TWO callers** - `truestill_cli.cli` and
    `truestill_app.service.organize_undo` - and `truestill-app` may not import `truestill-cli`.
    `(afu)` is the recorded precedent: its builder was placed where one of its two callers could
    not reach it, and the app went without a record for it. Backup's `_copy_entries` lives in the
    app legitimately, because backup has one caller.
    """
    record = build_run_record(
        RunHeader(
            kind="undo",
            source=str(plan.dest_root),
            destination=str(plan.source_root),
            undid_run_id=plan.run_id,
        ),
        files=files_from_undo(plan, outcome),
        intended_total=len(plan.steps) + len(plan.skipped),
        attempted=outcome.restored + len(outcome.skipped),
        stopped=undo_stop_block(outcome),
    )
    line: dict[str, object] = {
        "kind": "undo",
        "written_at": record.written_at,
        "run_id": plan.run_id,
        "undid_run_id": plan.run_id,
        "restored": outcome.restored,
        "skipped": len(outcome.skipped),
        "stopped": outcome.stopped is not None,
    }
    return record_run(catalog, record, index_line=line)


def record_organize(
    catalog: Path,
    record: RunRecord,
    *,
    run_id: str | None = None,
    detail: bool = True,
) -> str | None:
    """Write an organize, backup or migrate record with its index line. `(afw)`, `(agm)`

    ⚠ **The name is organize's and the function is not** - it derives the line from the record's
    own header and summary, which every kind fills the same way. Renaming it would touch four call
    sites to say what this sentence says; `(agm)` chose the sentence.

    ⚠ **Every run gets a line, not just undo.** A partial index is worse than none: a superseded
    record with no line can be pruned, and then nothing anywhere says the run happened - which is
    exactly the loss the split was designed to prevent.
    """
    line: dict[str, object] = {
        "kind": record.header.kind,
        "written_at": record.written_at,
        "intended_total": record.summary.intended_total,
        "attempted": record.summary.attempted,
        "stopped": record.summary.stopped is not None,
    }
    # ⚠ **Absent rather than ``null``**, for the reason `build_run_record` gives about
    # `destination_uuid`: a null would mean *"this run had no id"* and *"this surface does not
    # record one"* alike, which is the two-states-one-value shape this file argues against.
    if run_id is not None:
        line["run_id"] = run_id
    return record_run(catalog, record, index_line=line, detail=detail)
