"""Every route that starts a job says whether it writes files on the drive. `(aaw)`

`jobs.start`'s ``mutating`` is keyword-only and has **no default**, so mypy already fails a call
site that says nothing. This adds the half mypy cannot see: that the answers are *right*, checked
against what the route is called, and that nobody reintroduces a default.

⚠ **Why not derive it from ``operation``.** `"organize"` and `"organize preview"` differ by one
word, and a control derived from a display string is one rename away from a lock that stops
firing. `(afm)` renamed report wording twice in a week; this must not be that fragile.
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


def test_a_preview_never_holds_the_drive_and_an_apply_always_does() -> None:
    """⚠ **The exemption, pinned so it cannot quietly close - and its opposite.**

    A preview writes nothing, and a stale preview is not data loss. Making previews refuse would
    be new behaviour on a path that works today.
    """
    for operation, mutating in _declared():
        if "preview" in operation:
            assert not mutating, (
                f"{operation!r} declares it writes files; a preview that writes is either "
                "mislabelled or is not a preview"
            )

    writes = {op for op, mutating in _declared() if mutating}
    assert {"organize", "backup", "migrate", "undo"} <= writes, (
        f"a route that writes user files does not hold the drive: {sorted(writes)}"
    )
