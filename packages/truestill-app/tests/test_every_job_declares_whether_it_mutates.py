"""Every route that starts a job says whether it writes files on the drive. `(aaw)`

`jobs.start`'s ``mutating`` is keyword-only and has **no default**, so mypy already fails a call
site that says nothing. This adds the half mypy cannot see: that the answers are *right*, checked
against what the route is called, and that nobody reintroduces a default.

⚠ **Why not derive it from ``operation``.** `"organize"` and `"organize preview"` differ by one
word, and a control derived from a display string is one rename away from a lock that stops
firing. `(afm)` renamed report wording twice in a week; this must not be that fragile.

⚠ ✅ **AND THIS FILE DID IT ANYWAY, ONE SCREEN BELOW THAT PARAGRAPH - corrected 2026-08-23,
`(agg)`.** The check was ``if "preview" in operation: assert not mutating``. `(agg)` found
`/api/ingest/archives/run` registered ``operation="import preview", mutating=False`` while
unpacking archives onto the destination drive, so the lock never engaged - and **this test
required that**, because the label said preview. A guard that reads the display string does not
merely fail to catch the defect: it **enforces** it, and the obvious fix turned this file red.

⚠ **Renaming the operation made it green again, which is the wrong reason to be green** - proof
that the label was never the property. The expectation is now a **table**, so a route is checked
against a recorded decision rather than against its own wording, and a new one must be added
deliberately.

🔑 **A table is a declaration, not a derivation, so the cause is still open** (`(agg)`): nothing
here knows what a route *does*. The candidates - a one-hop call-graph check for known write
helpers, or having the write take the lock itself - are the entry's, not this file's.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from pathlib import Path

from truestill_app import jobs

_SERVER = Path(__file__).resolve().parents[1] / "src/truestill_app/server.py"


def test_mutating_has_no_default_so_a_new_caller_must_answer() -> None:
    """⚠ **The guard the ruling asked for.** A default is a decision nobody made."""
    parameter = inspect.signature(jobs.JobManager.start).parameters["mutating"]

    assert parameter.default is inspect.Parameter.empty, (
        "`mutating` gained a default. Unlocked silently skips the cross-process lock the next "
        "time a writing route is added; locked makes a preview refuse with nobody deciding."
    )
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, (
        "`mutating` must stay keyword-only so a call site cannot set it by position"
    )


def _declared() -> list[tuple[str, bool]]:
    """Every route that declares an operation, as (operation, mutating). **Shape-agnostic.**

    ⚠ **THIS ENUMERATED CALLEES BY NAME AND MISSED ONE, WHICH IS THE DEFECT ITSELF.** It matched
    `_start_drive_job` in two shapes - called directly, or handed to `run_in_threadpool` as an
    argument - and **`clean empty` declares through `jobs.claim`** (`server.py:485`), the
    exclusion-without-a-job that `(agu)` introduced for exactly that route. So the route `(agu)`
    fixed was absent from the table `(agu)` built: 15 operations read where 16 exist, and
    `mutating=True` on that call answered to nobody. `ENGINEERING_STANDARD.md` §4's 71st member -
    an audit that refreshed one half.

    **So the match is on the DECLARATION, not the callee.** Any call carrying both `operation=`
    and `mutating=` as literals is a route declaring itself, whatever function it is calling, and
    a fourth shape is covered the day it is written rather than the day someone notices.

    ⚠ **The literal requirement is what keeps `jobs.start` out**, and that is load-bearing rather
    than incidental: `_start_drive_job` forwards its own parameters (`server.py:194`), so the
    names are variables there. Matching on the callee would have needed that exclusion spelled
    out; matching on literals gets it for free.
    """
    tree = ast.parse(_SERVER.read_text(encoding="utf-8"))
    found: list[tuple[str, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kwargs = {k.arg: k.value for k in node.keywords if k.arg}
        operation, mutating = kwargs.get("operation"), kwargs.get("mutating")
        if isinstance(operation, ast.Constant) and isinstance(mutating, ast.Constant):
            found.append((operation.value, bool(mutating.value)))
    return found


def test_every_route_declares_and_the_declarations_are_read() -> None:
    """Anti-vacuity: if this finds nothing, the assertions below are vacuously true."""
    declared = _declared()

    assert len(declared) >= 12, f"only {len(declared)} routes were read; the scan is broken"


_CLI = Path(__file__).resolve().parents[3] / "packages/truestill-cli/src/truestill_cli/cli.py"


def _subcommands() -> set[str]:
    """Every ``sub.add_parser("name", ...)`` in the CLI, parsed rather than matched.

    The same read `test_the_cli_app_parity_table_is_complete.py` does, for the same reason: a
    name in prose is not a declaration of a subcommand, and only the AST tells them apart.
    """
    return {
        node.args[0].value
        for node in ast.walk(ast.parse(_CLI.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_parser"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }


@dataclass(frozen=True, slots=True)
class Decision:
    """What a route does to the drive, and **which CLI surface performs the same work**. `(ahj)`

    ⚠ **`surface` is the column `(ahj)` asked for, and it is on THIS table rather than a fourth
    one.** `PROJECT_STATUS.md` §1b's fourth exit condition - *"no mutating behaviour lives only in
    the app"* - was verified by hand three times in one month and found three surfaces each time.
    This table already held every operation and already failed when one was absent, so the
    condition needed a column here, not a new list to keep in step.

    ⚠ **`deferred` is the other answer, and the register stays its home.** A mutating operation may
    legitimately have no CLI, and then it carries the reason here. The *App-surface deferrals*
    register in `BACKLOG.md` is prose with no key - its row for the one deferred capability today
    reads *"Naming a trip or event is APP-ONLY"* and does not contain any operation string - so
    **no guard can check the register**. What is checkable is that this row declares one or the
    other, and says why.
    """

    #: True when the route writes to the user's drive or their files.
    mutating: bool
    #: The CLI subcommand that performs the same work. **Checked against the parser.**
    surface: str | None = None
    #: Why this mutating operation has no CLI. Mutually exclusive with `surface`.
    deferred: str | None = None


#: What each operation is **decided** to be, with the reason it is not obvious. A route absent
#: here fails rather than defaulting, because a default is the decision nobody made - which is the
#: same argument `jobs.start` makes for having no default on the parameter itself.
_EXPECTED: dict[str, Decision] = {
    # Writes user files on the drive. The four `(aaw)` was measured on.
    "organize": Decision(True, surface="organize"),
    "backup": Decision(True, surface="backup"),
    "migrate": Decision(True, surface="migrate-layout"),
    "undo": Decision(True, surface="migrate-layout"),  # `--undo`
    "undo organize": Decision(True, surface="undo-organize"),
    # Writes a drive's decisions document / dates into the organized copies.
    "set dates": Decision(True, surface="bake"),
    "trip apply": Decision(True, surface="migrate-layout"),
    # Moves every photograph in one trip or event into the folder the new name renders. The same
    # core entry the CLI calls - `migrate.apply_rename` - which is what records the
    # `authored_decisions` lease; a second apply path would silently stop the rename surviving a
    # catalog rebuild. `(aix)` stage 3.
    "rename": Decision(True, surface="rename"),
    # ⚠ Unpacks an archive set into a staging tree ON THE DESTINATION - `(agg)`. It was
    # `"import preview", False` until 2026-08-23, which is what this table exists to make
    # impossible to restate.
    "archive unpack": Decision(True, surface="ingest"),
    # ⚠ Declares through `jobs.claim`, not `_start_drive_job` - `(agu)` gave it the exclusion
    # without the job machinery, because its screen contract is a synchronous result. It was
    # invisible to this table until 2026-08-25 for exactly that reason. It removes empty folders
    # from the user's drive, and `(agu)` calls it "the product's only unserialized DELETE".
    "clean empty": Decision(True, surface="clean-empty"),
    # Reads and reports. A stale preview is not data loss, and refusing one would be new
    # behaviour on a path that works today.
    "organize preview": Decision(False),
    "migrate preview": Decision(False),
    # ⚠ A PREVIEW THAT IS A JOB, and it was written as a plain request first. `plan_rename` reads
    # only the catalog, but rendering the new path needs `_resolve_migration_routes`, which
    # re-reads metadata for ambiguous labels - the same reason `migrate preview` is a job.
    "rename preview": Decision(False),
    "trip preview": Decision(False),
    "undo preview": Decision(False),
    "undo organize preview": Decision(False),
    # Previews an already-extracted folder - the route `"archive unpack"` was confused with.
    "import preview": Decision(False),
    # Re-reads bytes and compares; writes nothing.
    "verify": Decision(False),
}


def test_every_declaration_matches_the_recorded_decision() -> None:
    """⚠ **Checked against a table, never against the operation's wording.**

    The wording check this replaced is the one that enforced `(agg)`: it required
    ``mutating=False`` of anything called a preview, including a route that unpacked archives
    onto the user's drive.
    """
    for operation, mutating in _declared():
        assert operation in _EXPECTED, (
            f"{operation!r} starts a drive job and is not in _EXPECTED. Decide what it does to "
            f"the drive and record it here; a route that answers by default answers by accident."
        )
        assert mutating == _EXPECTED[operation].mutating, (
            f"{operation!r} declares mutating={mutating}, recorded as "
            f"{_EXPECTED[operation].mutating}. "
            f"If the route's behaviour changed, change the record and say why in `(agg)`."
        )


def test_every_mutating_operation_names_a_cli_surface_or_says_why_not() -> None:
    """§1b's fourth exit condition, checked instead of censused. `(ahj)`

    *"No mutating behaviour lives only in the app."* It was verified **by hand three times in one
    month** - P64, P68 and P72 - and found bake, backup and trip apply. Each took its own letter
    to satisfy. Nothing ran it, so nothing stopped the fourth.

    ⚠ **Looped over the DERIVED side**, per `ENGINEERING_STANDARD.md` §4's seventy-second member:
    the iteration is over `_declared()`, read from `server.py`'s AST, and asserts **into**
    `_EXPECTED`. Empty the table and this fails on the first operation rather than passing over an
    empty dict - which is the failure that member exists for, and it needs no floor to notice.

    ⚠ **WHAT THIS PROVES, AND WHAT IT DOES NOT.** It proves every mutating route **declares** a
    CLI subcommand **that exists in the parser** - both ends read from source. It does **not**
    prove the subcommand does the same work: a route could name `verify` and copy files, and this
    would pass. That is a declaration guard, and selling it as a behaviour guard would be the
    lens-that-cannot-resolve-it shape §4 keeps finding.

    ⚠ **And the one genuinely deferred capability is invisible here**, which is worth knowing
    before trusting the green. Naming a trip is app-only by recorded decision, and its route
    (`events_apply`) declares **no operation at all** - checked: zero `operation=`/`mutating=` in
    that handler - so it never reaches `_declared()`. `deferred` is therefore a column for a
    future declared job, not a description of today's one exception. A mutating route that
    declares nothing is `(ahi)`'s and `(ahk)`'s territory, not this guard's.
    """
    subcommands = _subcommands()
    assert len(subcommands) >= 15, f"only {len(subcommands)} subcommands read; the scan is broken"

    for operation, mutating in _declared():
        if not mutating:
            continue
        decision = _EXPECTED[operation]
        assert (decision.surface is None) != (decision.deferred is None), (
            f"{operation!r} must name exactly one of `surface` or `deferred`. A mutating run "
            "either has a CLI or has a recorded reason it does not; both, or neither, is the "
            "decision nobody made."
        )
        if decision.deferred is not None:
            assert len(decision.deferred) > 20, (
                f"{operation!r} is deferred with no reason. The register in BACKLOG.md is the "
                "human home for it, and this row is what points at one existing."
            )
            continue
        assert decision.surface in subcommands, (
            f"{operation!r} names the CLI subcommand {decision.surface!r}, which "
            f"`cli.py` does not define. §1b's fourth exit condition: no mutating behaviour lives "
            "only in the app - so either build the subcommand, or record it as deferred with why."
        )


def test_the_surface_column_is_not_vacuous() -> None:
    """Measured, and the floor sits at the measurement rather than under it.

    ⚠ **`(agu)`'s own floor read `>= 12` against 16 and could never have fired** - it would have
    tolerated a scan that lost a quarter of its subject, which is exactly what happened when
    `jobs.claim` went unread. Measured 2026-08-25: **16** declared operations, **9** of them
    mutating, **19** subcommands. The floors below sit at those numbers, not below them.
    """
    declared = _declared()
    mutating = [operation for operation, is_mutating in declared if is_mutating]

    assert len(declared) >= 16, f"only {len(declared)} operations read; 16 existed at the floor"
    assert len(mutating) >= 9, f"only {len(mutating)} mutating operations; 9 existed at the floor"
    assert all(
        _EXPECTED[operation].surface or _EXPECTED[operation].deferred for operation in mutating
    ), "a mutating operation carries no surface decision"


def test_the_routes_that_write_user_files_all_hold_the_drive() -> None:
    """The cry-wolf half: a table of all-`False` would satisfy the test above and lock nothing."""
    writes = {op for op, mutating in _declared() if mutating}

    # `clean empty` joined this set on 2026-08-25: it removes folders from the user's drive and
    # was absent only because the scan above could not see its call shape.
    assert {"organize", "backup", "migrate", "undo", "archive unpack", "clean empty"} <= writes, (
        f"a route that writes user files does not hold the drive: {sorted(writes)}"
    )


# --- (agu): THE GUARD'S REACH - routes that never start a job were invisible to everything above


def _route_handlers() -> dict[str, tuple[bool, bool, set[str]]]:
    """Every handler in server.py: (starts a job, takes jobs.claim, service functions CALLED).

    ⚠ **This is the reach `(agu)` found missing.** `_declared` above read `_start_drive_job`
    call sites, so a mutating route that never called it - clean-empty apply, which DELETES -
    was invisible to the guard built for exactly that mistake. This walk starts from the other
    end: every route, whatever it calls, and a classification that must exist for each.

    ⚠ **CORRECTED 2026-08-25: `(agu)` recorded that hole and routed around it rather than closing
    it, and it stayed open for a year of commits.** `_declared` matches the **declaration** now -
    any call carrying literal `operation=` and `mutating=` - so clean-empty is visible to both
    walks. This second walk is still worth its cost: it answers a different question (*what does
    each handler CALL*), and it is what catches a route that mutates while declaring nothing at
    all. Two walks, two questions - not one walk done twice.
    """
    tree = ast.parse(_SERVER.read_text(encoding="utf-8"))

    def _calls_jobs_claim(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        return any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "claim"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "jobs"
            for call in ast.walk(fn)
        )

    # One hop, followed rather than named: a handler holds the claim if it calls `jobs.claim`
    # itself OR references a helper whose own body does - the event-loop guard forces the
    # acquisition into a pooled `def`, and this guard promptly failed its own author's hoist
    # until it learned to follow the claim instead of expecting it inline.
    claiming_helpers = {
        fn.name
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef) and _calls_jobs_claim(fn)
    }
    found: dict[str, tuple[bool, bool, set[str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.name == "create_app" or node.name in claiming_helpers:
            continue
        dumped = ast.dump(node)
        starts_job = "_start_drive_job" in dumped
        takes_claim = _calls_jobs_claim(node) or any(
            isinstance(ref, ast.Name) and ref.id in claiming_helpers for ref in ast.walk(node)
        )
        # References, not just Call nodes: most routes hand `service.X` to `run_in_threadpool`
        # UNCALLED, so a Call-only walk saw seventeen handlers where fifty exist (caught by the
        # anti-vacuity floor below on its first run). Exception classes and constants are
        # filtered by case - `BadContentIdError`, `THUMB_CACHE_CONTROL` - because a name that
        # is not snake_case is not a route-invokable service function.
        calls = {
            attr.attr
            for attr in ast.walk(node)
            if isinstance(attr, ast.Attribute)
            and isinstance(attr.value, ast.Name)
            and attr.value.id == "service"
            and attr.attr == attr.attr.lower()
        }
        if calls:
            found[node.name] = (starts_job, takes_claim, calls)
    return found


#: Service calls that DELETE or overwrite files on a drive. A handler calling one must hold the
#: exclusion - `_start_drive_job` or `jobs.claim` - and a new name lands here when the service
#: gains one, which the census below forces to be a decision rather than a default.
_MUST_HOLD_THE_EXCLUSION = {"clean_empty_apply"}

#: Why each service function may be called from a bare route - the recorded decision, same
#: doctrine as `_EXPECTED`. Three classes, each named at its entries: pure reads and payload
#: builders; catalog-ROW writers (serialized by SQLite itself plus the `(agp)` busy handling,
#: and deliberately outside drive locks - the gap `(aaw)` recorded and `(adt)`'s close split
#: into residue letters); and the two deliberate non-catalog exemptions, with their reasons.
_DIRECT_ALLOWED: dict[str, str] = {
    # pure reads / payload builders
    "organize_inventory": "walk and count; writes nothing",
    "backup_preview": "read",
    "clean_empty_preview": "plan_cleanup is pure - reads, never writes",
    "bake_preview": "read",
    "date_tier_files": "read",
    "at_risk": "read",
    "list_drives": "read",
    "event_settings": "read",
    "event_settings_payload": "payload builder",
    "invalid_event_settings_payload": "payload builder",
    "everyday_day_settings": "read",
    "everyday_day_settings_payload": "payload builder",
    "invalid_everyday_day_settings_payload": "payload builder",
    "invalid_event_proposal_payload": "payload builder",
    "propose_events": "reads the drive, proposes; moves nothing",
    "proposed_review_cards_payload": "payload builder",
    "review_cards_payload": "payload builder",
    "merge_event_review_cards": "session-state only",
    "split_event_review_card": "session-state only",
    "fs_dirs": "read",
    "filesystem_relationship": "read",
    "fs_validate": "read",
    "archive_precheck": "read",
    "layout_state": "read",
    "preview_layout": "read",
    "library_stats": "read",
    "library_status": "read",
    "migration_armed_state": "read",
    "organize_mode_state": "read",
    "organize_undo_state": "read",
    "sidebar_state": "read",
    "text_size_state": "read",
    "where": "a query",
    "drive_ref_for": "lock-identity helper; reads a marker",
    # catalog-ROW writers - rows, never files on the drive
    "set_organize_mode": "catalog row",
    "set_sidebar_collapsed": "catalog row",
    "set_text_size": "catalog row",
    "set_library_root": "catalog row",
    "set_layout": "catalog row",
    "set_event_settings": "catalog row",
    "set_everyday_day_settings": "catalog row",
    "confirm_file_date": "catalog row",
    "apply_event_review_names": "catalog rows; its own docstring: 'No files move'",
    # deliberate non-catalog exemptions
    "fs_create": "mkdir parents exist_ok - idempotent, creates only, cannot destroy",
    "thumbnail_bytes": "writes only the app's own cache directory, never the drive",
    "reveal_in_file_manager": "spawns the OS file manager; writes nothing",
}


def test_every_bare_route_call_is_a_recorded_decision() -> None:
    """⚠ **The reach itself.** A service call from a route that neither starts a job nor takes
    the claim must be classified here, or the route fails the build - which is what "the guard
    enumerates mutating routes" means, rather than the guard being told about one case."""
    unclassified = {
        f"{handler}: service.{call}"
        for handler, (starts_job, takes_claim, calls) in _route_handlers().items()
        if not starts_job and not takes_claim
        for call in calls
        if call not in _DIRECT_ALLOWED
    }

    assert not unclassified, (
        "routes calling service functions with no recorded classification:\n  "
        + "\n  ".join(sorted(unclassified))
        + "\nEither the call belongs under _start_drive_job / jobs.claim, or its harmlessness "
        "is a decision - record it in _DIRECT_ALLOWED with the reason."
    )


def test_a_deleting_service_call_only_runs_under_the_exclusion() -> None:
    """⚠ **(agu)'s exact shape, held generally**: whatever handler calls a deleting service
    function must hold the exclusion - a job or the claim - and fails here otherwise."""
    unserialized = {
        f"{handler} calls service.{call} with no job and no claim"
        for handler, (starts_job, takes_claim, calls) in _route_handlers().items()
        for call in calls & _MUST_HOLD_THE_EXCLUSION
        if not (starts_job or takes_claim)
    }

    assert not unserialized, "\n".join(sorted(unserialized))


def test_the_reach_scan_is_not_vacuous() -> None:
    """A collector that silently matches nothing would pass both tests above forever."""
    handlers = _route_handlers()
    direct_calls = {
        call
        for _h, (job, claim, calls) in handlers.items()
        for call in calls
        if not job and not claim
    }

    assert len(handlers) >= 30, f"only {len(handlers)} handlers seen - the walk is broken"
    assert len(direct_calls) >= 25, f"only {len(direct_calls)} direct calls seen"
    assert any(claim for _j, (_job, claim, _c) in handlers.items()), (
        "no handler takes jobs.claim - the clean-empty route lost its exclusion"
    )
