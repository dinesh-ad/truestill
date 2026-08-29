"""`(afu)`: an app organize run writes the record `IMPLEMENTATION_STANDARDS` §1 requires.

Three claims, deliberately separate because they fail for different reasons:

1. **The app path writes one, end to end** - driven through `organize_run`'s real job, never
   through the builder. A test that called `build_run_record` directly would have passed on the
   day the gap existed, because the builder was never the broken part: it was **unreachable** from
   this package, `truestill-app` depending on `truestill-core` only (§2). §4's thirteenth member -
   assert the subject entered the path.
2. **The two surfaces record the same fields** - the whole point of one builder. Compared key by
   key rather than by spot-checking, so a field added on one side cannot quietly not exist on the
   other.
3. **Every mutating app run is enumerated** as writing or not writing, with its reason - so the
   four that are out of `(afu)`'s scope are *recorded as absent* rather than merely missing.

⚠ **WHAT IS MECHANICAL HERE, AND WHAT IS PROSE. Understated on purpose** (`(ahg)`'s ruling about
its own table): implying a guard is worse than admitting there is none.

============================================  ================================================
checked by code                               a human read
============================================  ================================================
the `writes` boolean, against four record      **every `reason` string.** They are interpolated
entry-point spellings                          into the failure message and compared to nothing
the listed module exists                       which surface is *missing* a row entirely, when
                                               it writes no record - nothing declares the set of
no service writes a record without a row       mutating services, so that direction cannot be
(the derivable direction, added 2026-08-25)    derived
============================================  ================================================

⚠ **AND THE REASONS DRIFTED, WHICH IS WHY THIS SECTION EXISTS (P69).** `backup`'s row asserted
*"It still FAILS FAST"* for two days after `(afw)` Stage 4 made it false. Nothing linked
`service/backup.py`'s policy to this table, and **the correction was already in the suite** -
`test_backup_leaves_no_partial.py:57` said the opposite the whole time. Two statements of one
fact, one of which nothing reads: the index-headline-versus-body shape `(acc)` records, inside
the guard written to prevent exactly that class.

**Proved rather than assumed**: a mutation that rewrites a row's stated policy without touching
behaviour **survives** this file. The reasons are documentation, and are now labelled as such
rather than read as assertions.
"""

from __future__ import annotations

import ast
import json
import random
import threading
from dataclasses import replace
from pathlib import Path

import pytest
import truestill_core
from PIL import Image
from truestill_app.service.organize import organize_run
from truestill_core import organizer
from truestill_core.app_paths import record_path_for
from truestill_core.models import ActionStatus, Resolution, UnreadableReason
from truestill_core.progress import Phase, Progress
from truestill_core.run_record import RUN_RECORD_FORMAT, RunHeader, build_run_record

#: Every app service that changes the library, and whether `(afu)` gave it a run record.
#:
#: ⚠ **The absent ones are listed WITH THEIR REASON, which is the point of the table.** A guard
#: that only checked organize would be true and would say nothing about the other four, and
#: "nobody wrote a test for it" and "it was ruled out of scope" look identical from outside.
#:
#: ⚠ **ALL FIVE READ `True` SINCE `(agm)` (2026-08-25), so the "absent ones" half of the sentence
#: above now describes a state this table cannot demonstrate.** It is kept because it is the rule,
#: not the census: the next mutating service to arrive with no record is what it exists for, and
#: `test_no_service_writes_a_record_without_a_row_here` is the end that still bites today.
#:
#: ⚠ **WHAT IS STILL NOT MECHANICAL, and it is most of the value here.** `_wires_a_record` proves
#: a record entry point is CALLED somewhere reachable from the service. It does not prove a record
#: is written on every run - `(agj)` was exactly that defect - and it cannot read the reasons
#: below, which are prose no mutation can kill. This file measured that itself: a mutation that
#: rewrites a row's stated policy without touching behaviour SURVIVES. The five rows are now
#: uniform in their verdict and still carry five different policies; only the prose says so.
MUTATING_RUNS: dict[str, tuple[bool, str]] = {
    "organize": (True, "has a per-file ActionResult list; `(afu)` wires it"),
    "backup": (
        True,
        (
            "records under `kind: backup` with its own per-file entries; `(afw)` Stage 3. ⚠ THIS "
            "SAID 'It still FAILS FAST' UNTIL 2026-08-25 AND WAS FALSE FROM 2026-08-23 - `(afw)` "
            "Stage 4 landed that day: `_copy_verified` returns a verdict instead of raising, and "
            "`backup.py:569` appends the failure and continues. The correction was already in "
            "the suite, in `test_backup_leaves_no_partial.py:57` - a sibling file said the "
            "opposite of this row for two days and nothing compared them"
        ),
    ),
    "migrate": (
        True,
        # ⚠ **THIS ROW SAID `False` BECAUSE OF A PREMISE THAT WAS WRONG**, corrected by `(agm)`
        # on 2026-08-25. It rested on *"its durable per-file state is `migration_journal`"* - but
        # `start_migration_run` DELETES the previous run's journal (`catalog.py:1486`), so that
        # store has retention ONE and its consumer is undo. Migrate was the surface with the
        # history gap, and this row named it as the surface that did not need one.
        (
            "records under `kind: migrate` with FAILURES-ONLY entries, `(afd)`'s ruling: the "
            "successes are `migrated` and where each went is `plan.moves`. It reuses the "
            "`run_id` migrate already mints, so its superseded records are self-identifying"
        ),
    ),
    "bake": (
        True,
        (
            "writes an INDEX LINE AND NO DETAIL (`record_organize(detail=False)`), `(agm)`. The "
            "observation this row carried is unchanged and is the reason for the shape: it "
            "counts FILES and names only DRIVES (`awaiting`), so `files` would be `[]` for a run "
            "of any size. What the entry got wrong was the argument - the load-bearing fact is "
            "`file_copies.date_baked_at`, a PERMANENT per-copy timestamp, so which copies a bake "
            "wrote outlives every later run while a record's detail is bounded by a byte budget. "
            "⚠ THE ROW IS TRUE FOR A RUN THAT WRITES NO `files`, which is why `_wires_a_record` "
            "asking only 'is a record entry point CALLED' is the honest question here"
        ),
    ),
    "organize_undo": (
        True,
        # ⚠ **THIS SAID "returns counts only" AND WAS FALSE THE DAY IT WAS WRITTEN.** `(afw)`
        # grouped undo with bake on that basis, which made it look like a design problem. In fact
        # `UndoOutcome` has carried `plan.steps` and `skipped: list[UndoSkipped]` since the
        # original in-place commit `dee4785` - organize's shape, with a RICHER outcome model than
        # backup's `(relative, why)` tuples, because `UndoSkip` is a seven-member enum. Undo was
        # the cheapest of the four remaining surfaces, not the hardest.
        "returns a per-file plan AND typed per-file outcomes; writes one since `(afw)`",
    ),
}


#: The four spellings of "this run writes a record". `(afw)` found one name was not enough when
#: undo reached `record_run` through `record_undo`.
RECORD_ENTRIES = ("write_run_record", "record_run", "record_organize", "record_undo")


def _wires_a_record(service: Path, name: str) -> bool:
    """Whether this run writes a record - **following the engine, not just the panel**.

    ⚠ **THE FILE STOPPED BEING THE ANSWER ON 2026-08-25.** This grepped `service/<name>.py` alone,
    which was exact while every engine lived in the app. `(ahd)` and `(ahf)` moved bake's and
    backup's engines into `truestill_core`, so `service/backup.py` became a panel that no longer
    mentions `record_organize` - and the guard reported "does not write a record" about a run that
    still writes one. Caught by this file the same commit the move landed, which is the guard
    doing its job rather than the guard being wrong.

    So the question is asked of the run: the service module **and every `truestill_core` module it
    imports from**. That follows `(ahd)`'s core-computes/app-wraps line instead of assuming the
    code never moves.
    """
    module = service / f"{name}.py"
    source = module.read_text(encoding="utf-8")
    reachable = [source]
    core = Path(truestill_core.__file__).parent
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("truestill_core."):
            engine = core / f"{(node.module or '').split('.', 1)[1]}.py"
            if engine.is_file():
                reachable.append(engine.read_text(encoding="utf-8"))
    return any(_calls_a_record_entry(text) for text in reachable)


def _calls_a_record_entry(source: str) -> bool:
    """Whether this source **calls** a record entry point, rather than merely naming one.

    ⚠ **Text presence is too loose once core modules are followed.** Eight service modules reach a
    core module that *mentions* `record_organize` in a docstring; only three reach one that calls
    it. A guard that counted mentions would have reported five surfaces as recording runs they do
    not - the 69th member, on the widening rather than on the original.
    """
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        called = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        if called in RECORD_ENTRIES:
            return True
    return False


def _photo(path: Path, seed: int) -> None:
    """The app suite's own helper, so this fixture is the shape every other app test uses."""
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


def _library(tmp_path: Path, count: int = 1) -> tuple[Path, Path, Path]:
    source, destination = tmp_path / "src", tmp_path / "dest"
    source.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        _photo(source / f"{index}.jpg", seed=index)
    return source, destination, tmp_path / "catalog.sqlite"


def _run(
    source: Path, destination: Path, db: Path, *, cancel: threading.Event | None = None
) -> object:
    """Drive the real app job, the way a route does."""
    target = organize_run(source, destination, db)
    return target(lambda _progress: None, cancel or threading.Event())


def _record(db: Path) -> dict[str, object]:
    return json.loads(record_path_for(db).read_text(encoding="utf-8"))


def test_an_app_run_writes_the_record_without_being_asked(tmp_path: Path) -> None:
    """§1's invariant, on the surface its own justification names.

    Asserts the record's CONTENT, not that a file exists: a file at the right path with a
    plausible size is exactly what a torn write leaves (§4's fiftieth member).
    """
    source, destination, db = _library(tmp_path)

    _run(source, destination, db)

    record = _record(db)
    assert record["format"] == RUN_RECORD_FORMAT
    run = record["run"]
    assert isinstance(run, dict)
    assert run["source"] == str(source)
    assert run["destination"] == str(destination)
    assert run["intended_total"] == 1
    assert run["attempted"] == 1
    assert run["stopped"] is None
    files = record["files"]
    assert isinstance(files, list)
    assert [f["source"] for f in files] == [str(source / "0.jpg")]
    assert files[0]["status"] == ActionStatus.UPLOADED.value


def test_the_record_names_a_file_the_run_could_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`(aac)`'s conflation, fixed inside the record before anything relied on it.

    Without `unreadable`, a file the run never reached recorded ``"not attempted"`` and a null
    ``sha256`` - which is **also** what the size pre-filter's legitimate skip looks like. This
    asserts the two are distinguishable in the document.
    """
    source, destination, db = _library(tmp_path)
    real_resolve = organizer.resolve

    def unreadable(*args: object, **kwargs: object) -> list[Resolution]:
        resolutions = real_resolve(*args, **kwargs)  # type: ignore[arg-type]
        return [
            replace(r, hashes=replace(r.hashes, unreadable=UnreadableReason.PERMISSION))
            for r in resolutions
        ]

    monkeypatch.setattr("truestill_app.service.organize.resolve", unreadable)
    _run(source, destination, db)

    files = _record(db)["files"]
    assert isinstance(files, list)
    assert files[0]["unreadable"] == UnreadableReason.PERMISSION.value


def test_a_cancelled_run_records_the_reason_it_actually_stopped_for(tmp_path: Path) -> None:
    """⚠ The branch the CLI could never reach, and the reason `stopped=` is passed explicitly.

    `stop_block` reads the reason off the last result, which works for the two stops that record
    a `FAILED` row and **not** for a cancel, which records nothing. Driven through a real `cancel`
    event rather than a fabricated `stopped` dict, because the fabricated one would pass whether
    or not the plumbing existed.
    """
    source, destination, db = _library(tmp_path, count=4)

    # ⚠ **Set MID-RUN, not before it.** Cancelling before the plan exists leaves nothing planned
    # either, so `never_attempted` is legitimately 0 and the fixture proves nothing - the first
    # version of this test did exactly that. A user presses stop while files are being copied.
    cancel = threading.Event()

    def stop_after_the_first_copy(progress: Progress) -> None:
        # ⚠ **Gated on the PHASE, and that is not decoration.** The same callback is handed to
        # `resolve`, so a bare `done >= 1` cancels during PLANNING - which truncates `resolutions`
        # and `results` equally and leaves `never_attempted` at 0. The first version of this test
        # did that and passed alone, then failed when another file's run warmed the cache and
        # moved where the count landed. Only ORGANIZING is the copying loop.
        if progress.phase == Phase.ORGANIZING and progress.done >= 1:
            cancel.set()

    target = organize_run(source, destination, db)
    target(stop_after_the_first_copy, cancel)

    stopped = _record(db)["run"]
    assert isinstance(stopped, dict)
    block = stopped["stopped"]
    assert isinstance(block, dict), "a cancelled run recorded no stop block"
    assert block["reason"] == "you stopped this run", block
    assert block["never_attempted"] >= 1


def test_a_failed_write_reaches_the_completion_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record must not fail the run, and its absence must not be silent - `(acc)`'s shape."""
    source, destination, db = _library(tmp_path)

    monkeypatch.setattr(
        # `record_organize` since `(afw)`: organize writes an index line as well as its detail,
        # so this is the entry point whose failure the completion payload has to carry.
        "truestill_app.service.organize.record_organize",
        lambda _db, _payload: "No space left on device",
    )
    done = _run(source, destination, db)

    assert isinstance(done, dict)
    assert done["organized"] == 1, "the paperwork failing must not fail the run"
    assert done["record_error"] == "No space left on device"


def test_a_successful_write_says_nothing(tmp_path: Path) -> None:
    """Cry-wolf half: the key is present ONLY on failure, or it becomes noise on every run."""
    source, destination, db = _library(tmp_path)

    done = _run(source, destination, db)

    assert isinstance(done, dict)
    assert "record_error" not in done


def test_both_surfaces_record_the_same_fields(tmp_path: Path) -> None:
    """One builder, so the two surfaces cannot drift - compared key by key, not spot-checked.

    ⚠ **This is the claim the move exists to make.** Before `(afu)` the app had no record at all,
    so "the surfaces agree" was vacuously true in the worst way. Comparing the full key sets means
    a field added for one caller cannot quietly not exist for the other.
    """
    source, destination, db = _library(tmp_path)

    _run(source, destination, db)
    from_app = _record(db)

    # The CLI's own payload, from the same builder both surfaces now call.
    from_cli = build_run_record(
        RunHeader(kind="organize", source=str(source), destination=str(destination)),
        files=[],
        intended_total=0,
        attempted=0,
        stopped=None,
    )

    assert from_app.keys() == from_cli.keys()
    app_run, cli_run = from_app["run"], from_cli["run"]
    assert isinstance(app_run, dict)
    assert isinstance(cli_run, dict)
    assert app_run.keys() == cli_run.keys()

    files = from_app["files"]
    assert isinstance(files, list)
    expected = {
        "source",
        "status",
        "detail",
        "landed_at",
        "planned_relative",
        "category",
        "confidence",
        "rule",
        "reason",
        "captured_at",
        "date_source",
        "date_tag",
        "needs_review",
        "sha256",
        "perceptual",
        "unreadable",
        "should_upload",
        "is_unique",
        "exact_duplicate",
        "near_duplicate",
    }
    assert files[0].keys() == expected, (
        "the per-file shape changed; both surfaces read this builder, so update the expectation "
        "deliberately rather than to make this pass"
    )


def test_every_mutating_app_run_is_accounted_for() -> None:
    """⚠ The four out of `(afu)`'s scope are recorded as absent WITH A REASON, not merely missing.

    §4's fifty-second member in spirit: a guard that checks only the surface that works says
    nothing about the four that do not, and silence there is what let `(afl)` ship on one surface.
    """
    service = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "service"
    for name, (writes, reason) in MUTATING_RUNS.items():
        assert (service / f"{name}.py").is_file(), f"{name} is listed here and does not exist"
        wires_it = _wires_a_record(service, name)
        assert wires_it is writes, (
            f"service/{name}.py {'writes' if wires_it else 'does not write'} a run record, and "
            f"this table says the opposite. If that is deliberate, change the table and its "
            f"reason - recorded reason: {reason}"
        )


#: The operations `server.py` declares that this guard can ask about **by entry point**, with the
#: real answer. ⚠ **Keyed by (module, function), not by module** - `(ahi)`'s undo survived because
#: `_wires_a_record` is module-granular: `service/migrate.py` reaches `record_organize` through
#: `truestill_core.migrate._record_migration` on the FORWARD path, so `migrate` answered `True`
#: however `undo_migration` behaved. A guard that cannot see a function cannot see a gap inside one.
ENTRY_POINTS: dict[str, tuple[str, str, bool, str]] = {
    "migrate": ("migrate", "migration_apply", True, "the forward path, via `_record_migration`"),
    "undo": (
        "migrate",
        "migration_undo",
        True,
        (
            "`(ahi)`, 2026-08-29. It wrote NOTHING until then, and the module-granular check "
            "could not see it: its own module records on the forward path. The record carries "
            "per-file detail - the opposite of `(agm)`'s bake ruling - because a migration's "
            "durable per-file store is `migration_journal`, which `start_migration_run` DELETES "
            "for the drive on the next run. Retention one, so the record is the only account "
            "that survives a second migration"
        ),
    ),
    "archive unpack": (
        "takeout",
        "archive_ingest_run",
        False,
        "`(ahi)`'s remaining set. Unbuilt, and its shape is its own judgement - see the note",
    ),
    "clean empty": (
        "clean_empty",
        "clean_empty_apply",
        False,
        "`(ahi)`'s remaining set. Unbuilt, and its shape is its own judgement - see the note",
    ),
}


def _reaches_a_record(service: Path, module: str, function: str, *, depth: int = 3) -> bool:
    """Whether THIS FUNCTION reaches a record entry point, following the calls it makes.

    Bounded reachability rather than a module grep: from ``function``, every call it makes is
    resolved against functions defined in the same module and in the `truestill_core` modules that
    module imports, and followed to ``depth``. That is what lets the guard answer about
    `migration_undo` and `migration_apply` separately when both live in one file whose sibling
    records.

    **The depth is a cap, not a claim.** Three levels reaches
    `migration_apply -> run_migration -> _record_migration` with one to spare; a chain longer than
    that answers `False`, which fails toward "does not record" - the direction that reports a gap
    rather than hiding one.
    """
    # ⚠ **A LIST, NOT A DICT KEYED BY MODULE NAME** - `service/migrate.py` and
    # `truestill_core/migrate.py` share the name `migrate`, so a name-keyed store silently
    # dropped one of them and this guard reported that `migration_apply` reaches no record.
    # Caught by the guard failing on its own rewrite.
    head = (service / f"{module}.py").read_text(encoding="utf-8")
    sources: list[str] = [head]
    core = Path(truestill_core.__file__).parent
    for node in ast.walk(ast.parse(head)):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("truestill_core."):
            engine = core / f"{(node.module or '').split('.', 1)[1]}.py"
            if engine.is_file():
                sources.append(engine.read_text(encoding="utf-8"))

    functions: dict[str, ast.FunctionDef] = {}
    for text in sources:
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.FunctionDef):
                functions.setdefault(node.name, node)

    seen: set[str] = set()

    def walk(name: str, left: int) -> bool:
        if left < 0 or name in seen:
            return False
        seen.add(name)
        node = functions.get(name)
        if node is None:
            return False
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            called = (
                call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
            )
            if called in RECORD_ENTRIES:
                return True
            if walk(called, left - 1):
                return True
        return False

    return walk(function, depth)


def test_the_table_has_rows_to_check_and_both_answers_in_it() -> None:
    """Anti-vacuity. **There was none until 2026-08-25** - an emptied table iterated nothing.

    The `for` loop in the guard above is the whole check, so a table with no rows passes it
    perfectly.

    ⚠ **THE SECOND HALF USED TO BE `answers == {True, False}` AND STOPPED BEING TESTABLE ON
    2026-08-25**, when `(agm)` gave migrate and bake theirs and every row went `True`. That
    assertion was a proxy for the real worry, which it stated plainly: *"the grep could be
    returning `True` unconditionally and nothing would notice."*

    **The proxy is replaced by the thing itself.** `_wires_a_record` is pointed at three real
    services that genuinely write no record - `(ahi)`'s remaining set - and must answer `False`
    for them. That is a stronger floor than a non-uniform table: it exercises the DETECTOR against
    real negatives instead of requiring the world to keep supplying one, which is the shape
    `test_live_documents_cite_code_that_exists.py` reached for the same reason. A table that
    legitimately becomes uniform must not cost a guard its teeth.
    """
    assert len(MUTATING_RUNS) >= 5, f"only {len(MUTATING_RUNS)} mutating runs listed"
    for name, (_writes, reason) in MUTATING_RUNS.items():
        assert len(reason) > 20, f"{name}'s row has no reason, which is the point of the table"

    service = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "service"

    # ⚠ **THE FLOOR USED TO NAME `("trips", "clean_empty", "takeout")` AND WAS WRONG IN BOTH
    # DIRECTIONS.** `trip apply` RECORDS - its route reaches `service/migrate.py::migration_apply`,
    # which reaches `_record_migration` - so it was never in `(ahi)`'s remaining set, and the row
    # asserted the opposite. Meanwhile the operation that genuinely wrote nothing, migrate's
    # `undo`, was invisible: the check was module-granular and its module records on the forward
    # path. Both halves are fixed by asking per ENTRY POINT.
    for operation, (module, function, writes, reason) in ENTRY_POINTS.items():
        assert (service / f"{module}.py").is_file(), f"service/{module}.py moved; floor is blind"
        assert len(reason) > 20, f"{operation}'s row has no reason, which is the point"
        assert _reaches_a_record(service, module, function) is writes, (
            f"operation {operation!r} ({module}.{function}) "
            f"{'no longer' if writes else 'now'} reaches a run record. If that is real it is "
            "`(ahi)`'s work landing or regressing, and this row is what must change with it"
        )


def test_no_service_writes_a_record_without_a_row_here() -> None:
    """The direction that IS derivable, and the one this table could silently miss.

    ⚠ **The guard above only ever checks rows that exist.** A new service that wires a run record
    and is never listed would be invisible to it - the same hand-list exposure
    `check_product_name.CHECKED` carries. That half is closable, because "writes a record" is
    readable from the source, and it is closed here.

    ⚠ **The other half is NOT closable and is stated rather than implied**: a new mutating service
    that writes **no** record cannot be detected, because nothing in this codebase declares the
    set of mutating services. `server.py`'s `mutating=True` marks routes, not modules, and the
    operation strings do not map onto file names.
    """
    service = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "service"
    writers = {
        module.stem
        for module in sorted(service.glob("*.py"))
        if _wires_a_record(service, module.stem)
    }
    listed = {name for name, (writes, _reason) in MUTATING_RUNS.items() if writes}

    assert writers, "no service wires a run record; is the entry-point list still right?"
    assert writers == listed, (
        f"services that write a record: {sorted(writers)}; rows claiming to: {sorted(listed)}. "
        "A service that records a run and is not listed here is invisible to the guard above."
    )
