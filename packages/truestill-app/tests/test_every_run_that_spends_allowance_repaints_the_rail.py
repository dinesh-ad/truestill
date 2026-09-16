"""Both doors that spend allowance repaint the rail, and the server side is derived. `(akx)`

**The defect.** `loadAccount` had exactly one call site - the boot list - so the rail's allowance
line described the allowance as it stood when the page was opened. Organize 100 files through the
app and it still read "700 of 1,000 left" while the server said 600. D16 §5 permits that one
number to exist at all, and justified the Apply-time refusal precisely on the grounds that *"the
number was never hidden, it was simply never pushed"*.

⚠ **THE BROWSER TEST IS `tests/e2e/test_the_rail_repaints_after_a_run_that_spent_allowance.py`,
and this file is the half it cannot do.** That one proves the number is right in a page nobody
reloaded; it drives ONE door, organize, because a Takeout import is a minute of browser time for
the same assertion. This file is what stops the other door drifting - the shape `(aku)` set and
`test_the_app_records_a_move_too.py` already uses, for the same reason.

⚠ **WHICH DOORS ARE READ OFF THE SERVER, not listed here.** The set is "routes that reach
`record_files_written`", and it is derived by walking the service module: a third one added
tomorrow fails this file rather than shipping a stale rail.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATIC = ROOT / "packages/truestill-app/src/truestill_app/static/app.js"
ORGANIZE = ROOT / "packages/truestill-app/src/truestill_app/service/organize.py"
SERVER = ROOT / "packages/truestill-app/src/truestill_app/server.py"

#: The one function that charges the cap. Named rather than the routes, because the routes are
#: what this test derives.
CHARGES = "record_files_written"


def _charging_services() -> set[str]:
    """Service functions that spend allowance: the one that charges, and whatever calls it.

    Parsed rather than grepped. A substring search over this module matches the comments that
    explain the charge as readily as the charge itself, and `ingest_run` reaches it only by
    calling `organize_run` - a hop a text search cannot follow without also following prose.
    """
    tree = ast.parse(ORGANIZE.read_text(encoding="utf-8"))
    functions = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    charging = {
        name
        for name, node in functions.items()
        if any(
            isinstance(c.func, ast.Name) and c.func.id == CHARGES
            for c in ast.walk(node)
            if isinstance(c, ast.Call)
        )
    }
    assert charging, "nothing in this module charges the cap; the guard reads the wrong file"
    # One hop is enough and is asserted as such: `ingest_run` -> `organize_run` is the only
    # indirection today, and a deeper chain would fail the census test below rather than pass
    # quietly with a door missing.
    return charging | {
        name
        for name, node in functions.items()
        if any(
            isinstance(c.func, ast.Name) and c.func.id in charging
            for c in ast.walk(node)
            if isinstance(c, ast.Call)
        )
    }


def _spending_routes() -> set[str]:
    """Every `/api/...` route whose handler reaches one of those services."""
    server = SERVER.read_text(encoding="utf-8")
    charging = _charging_services()
    tree = ast.parse(server)
    handlers = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)}
    reaching = {
        name
        for name, node in handlers.items()
        if any(
            isinstance(a, ast.Attribute) and a.attr in charging
            for a in ast.walk(node)
            if isinstance(a, ast.Attribute)
        )
    }
    return {
        path
        for path, handler in re.findall(r'Route\("(/api/[^"]+)", (\w+)', server)
        if handler in reaching
    }


def test_the_two_doors_are_the_two_this_guard_knows_about() -> None:
    """Anti-vacuity, and the trigger for the next one.

    A derivation that found nothing would make every assertion below true. Naming the routes
    here means a third spending door - a new import format, a rescue that writes - fails this
    line first, which is where somebody will read why.
    """
    assert _spending_routes() == {"/api/organize/run", "/api/ingest/run"}


def test_every_spending_route_repaints_the_account_rail() -> None:
    """The anti-drift assertion: read the source rather than trusting a reviewer noticed.

    Each door's `runJob` block must end with a `loadAccount` call, and the block is found by the
    route it posts to - so a repaint added to the wrong handler does not satisfy this.
    """
    app = STATIC.read_text(encoding="utf-8")
    for route in sorted(_spending_routes()):
        assert f'api("{route}"' in app, f"{route} has no caller in app.js"
        block = app.split(f'api("{route}"', 1)[1].split("\n  });", 1)[0]
        assert "loadAccount()" in block, (
            f"a run through {route} spends allowance and leaves the rail describing the "
            "allowance as it stood when the page was opened"
        )


def test_nothing_repaints_it_on_a_timer() -> None:
    """D6 §3 forbids a countdown, so the repaint is an END and never a stream.

    The browser test asserts the number does not move mid-run; this refuses the mechanism that
    would make it move, which is the one a later change is most likely to reach for.
    """
    app = STATIC.read_text(encoding="utf-8")
    # ⚠ **A FIXED WINDOW, not a balanced-paren match**, and the first draft got this wrong: a
    # `[^)]*` window over `setInterval(() => loadAccount(), 500)` stops at the arrow function's
    # own `()` and never reaches the call. The mutation that put a timer in survived because of
    # it, which is what the vacuity check is for.
    for offender in ("setInterval", "setTimeout"):
        for match in re.finditer(re.escape(offender) + r"\(", app):
            window = app[match.start() : match.start() + 160]
            assert "loadAccount" not in window, f"the rail is repainted by {offender}: {window!r}"
