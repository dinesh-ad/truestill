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
    """Every `_start_drive_job` call in the server, as (operation, mutating)."""
    tree = ast.parse(_SERVER.read_text(encoding="utf-8"))
    found: list[tuple[str, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Two shapes, and missing the second is how this scan goes quietly vacuous: most routes
        # hand `_start_drive_job` to `run_in_threadpool` as an argument, so the keywords belong
        # to THAT call. Four are direct.
        direct = isinstance(node.func, ast.Name) and node.func.id == "_start_drive_job"
        handed_off = any(
            isinstance(arg, ast.Name) and arg.id == "_start_drive_job" for arg in node.args
        )
        if not (direct or handed_off):
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


#: What each operation is **decided** to be, with the reason it is not obvious. A route absent
#: here fails rather than defaulting, because a default is the decision nobody made - which is the
#: same argument `jobs.start` makes for having no default on the parameter itself.
_EXPECTED: dict[str, bool] = {
    # Writes user files on the drive. The four `(aaw)` was measured on.
    "organize": True,
    "backup": True,
    "migrate": True,
    "undo": True,
    "undo organize": True,
    # Writes a drive's decisions document / dates into the organized copies.
    "set dates": True,
    "trip apply": True,
    # ⚠ Unpacks an archive set into a staging tree ON THE DESTINATION - `(agg)`. It was
    # `"import preview", False` until 2026-08-23, which is what this table exists to make
    # impossible to restate.
    "archive unpack": True,
    # Reads and reports. A stale preview is not data loss, and refusing one would be new
    # behaviour on a path that works today.
    "organize preview": False,
    "migrate preview": False,
    "trip preview": False,
    "undo preview": False,
    "undo organize preview": False,
    # Previews an already-extracted folder - the route `"archive unpack"` was confused with.
    "import preview": False,
    # Re-reads bytes and compares; writes nothing.
    "verify": False,
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
        assert mutating == _EXPECTED[operation], (
            f"{operation!r} declares mutating={mutating}, recorded as {_EXPECTED[operation]}. "
            f"If the route's behaviour changed, change the record and say why in `(agg)`."
        )


def test_the_routes_that_write_user_files_all_hold_the_drive() -> None:
    """The cry-wolf half: a table of all-`False` would satisfy the test above and lock nothing."""
    writes = {op for op, mutating in _declared() if mutating}

    assert {"organize", "backup", "migrate", "undo", "archive unpack"} <= writes, (
        f"a route that writes user files does not hold the drive: {sorted(writes)}"
    )
