"""The migrate screens report a stop. `(ahc)`

⚠ **THE THIRD SURFACE OF `(agm)` D1, and it was left unbuilt on purpose** - that commit scoped
itself *"no app.js"*. So `MigrationOutcome.stopped` reached the CLI and the app **service**, and
stopped there. `service/migrate.py` flattened it faithfully into the payload and
`static/app.js` read neither it nor `refused`.

**What that looked like to a person.** Only a *user cancel* sets the job's cancel flag, so a
`GROUND_MOVED` or `COULD_NOT_CONTINUE` stop - the disk filling, a device changing under the run, a
destination that does not store what it is handed - arrived with job status `"done"` and was
painted by the forward success branch as **`Moved N files.`** On the one screen that rewrites
every byte of the library. The forward `refused` list was dropped entirely, while **undo has
named its refusals since it was written** - the forward path was the outlier against its own undo,
exactly as `MigrationOutcome.refused`'s own comment says of the engine.

`(afa)`/`(abm)`'s shape: the payload is computed, and the surface drops it.

⚠ **ONE WORDING HOME, and that is the design rather than a tidy-up.** `truestill_core.migrate`
`STOP_WORDING` maps each kind to its headline and whether it is a fault. The CLI reads it (it used
to derive `kind is CANCELLED` inline); the app service puts `headline` and `fault` **in the
payload**, so `app.js` renders text it was handed. A third derivation in JavaScript would have
been a second vocabulary in a second language - `test_the_rearrange_card_name.py` records what one
name retyped in four places cost. This file pins that no such mapping appears in the script.

**Read as text, per that same precedent**, because the browser lane is not part of the routine
loop (`CLAUDE.md`). What a text read can prove is that the handlers consult the field and that the
script maps no kinds of its own; what it cannot prove is that the banner is visible, which is the
browser lane's question and is stated here rather than implied.
"""

from __future__ import annotations

import re
from pathlib import Path

from truestill_core.migrate import STOP_WORDING, MigrationStopKind

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "packages/truestill-app/src/truestill_app/static/app.js"
CLI = ROOT / "packages/truestill-cli/src/truestill_cli/cli.py"

#: The four handlers that receive a finished migrate job: forward apply and undo apply, each with
#: a cancelled and a success arm. A **preview** is deliberately not among them - `run_migration`
#: returns before a stop can be set (`migrate.py`), so its summary never carries one.
OUTCOME_HANDLERS = 4


def _script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_every_migrate_outcome_handler_consults_the_stop() -> None:
    """The regression. Before `(ahc)` this was **zero** - no handler read the field at all."""
    calls = _script().count("${migrationStopNote(")
    assert calls >= OUTCOME_HANDLERS, (
        f"only {calls} migrate outcome handlers render the stop; {OUTCOME_HANDLERS} receive one. "
        "A run that stopped arrives with job status 'done' - only a user cancel sets the flag - "
        "so a handler that paints `migrated` alone reports a failing drive as a finished run."
    )


def test_the_forward_run_no_longer_paints_a_stop_as_a_finished_move() -> None:
    """The exact defective shape, pinned by absence.

    It read `card(\\`<div class="headline">Moved ${plural(d.summary.migrated || 0, "file")}.</div>\\`)`
    with nothing else in the card - no stop, no refusals.
    """
    script = _script()
    defective = (
        'card(`<div class="headline">Moved ${plural(d.summary.migrated || 0, "file")}.</div>`)'
    )
    assert defective not in script, (
        "the forward success branch paints `migrated` and nothing else again; a stopped run "
        "reads as a completed one"
    )


def test_the_forward_run_names_its_refusals_as_undo_already_did() -> None:
    """`refused` was dropped on the forward path only, and the payload shape is identical.

    So the renderer is **reused, not rewritten** - it was called `undoRefusalList` and is called
    `refusalList` now, because it was never undo's.
    """
    script = _script()
    assert "function refusalList(" in script, "the shared refusal renderer is gone"
    assert "undoRefusalList" not in script, "the old direction-specific name is back"
    assert script.count("${refusalList(") >= OUTCOME_HANDLERS, (
        "not every migrate outcome handler names its refusals"
    )


def test_the_screen_maps_no_stop_kind_of_its_own() -> None:
    """⚠ **The one-vocabulary rule, and the reason `headline` is in the payload.**

    A `kind` string appearing in the script would mean the words were being decided twice, in two
    languages, with nothing to make them agree. Values rather than names, because JavaScript would
    carry the value.

    ⚠ **`CANCELLED` IS EXCLUDED, and it is a collision rather than an exemption.** The first draft
    checked all three and went red on `app.js`'s `d.status === "cancelled"` - the **job status**
    vocabulary set by `jobs.py`, a different namespace that happens to share the word. That is
    §4's 69th member turned on this guard: a true hit about the wrong subject. The two kinds
    below are unambiguous, and they are the two that matter here - a cancel already had a screen
    path, and what had none was a stop that is a **fault**.
    """
    script = _script()
    checkable = [k for k in MigrationStopKind if k is not MigrationStopKind.CANCELLED]
    assert checkable, "the enum lost every non-cancel kind; this guard now checks nothing"
    found = [kind.value for kind in checkable if f'"{kind.value}"' in script]
    assert not found, (
        f"app.js maps stop kinds itself: {found}. The words come from STOP_WORDING through the "
        "payload's `headline` and `fault`; mapping them here is a second vocabulary."
    )


def test_the_cli_reads_the_same_table_rather_than_deriving_it() -> None:
    """One home means the CLI stopped deriving it too, or there are still two."""
    cli = CLI.read_text(encoding="utf-8")
    assert "STOP_WORDING[stopped.kind]" in cli, "the CLI no longer reads the shared table"
    assert "MigrationStopKind.CANCELLED" not in cli, (
        "the CLI derives the cancel/fault split inline again, beside a table that already says it"
    )


# ------------------------------------------------------------------ cry-wolf, in both directions


def test_a_completed_migration_still_reads_as_completed() -> None:
    """A run with no stop must keep its plain sentence, not gain a banner about nothing.

    `migrationStopNote` returns `""` on a missing `stopped`, and the headline falls back.
    """
    script = _script()
    assert 'const s = (summary || {}).stopped;\n  if (!s) return "";' in script, (
        "the stop note no longer returns nothing for a run that did not stop"
    )
    assert '`Moved ${plural(s.migrated || 0, "file")}.`' in script, (
        "the completed-run headline is gone; a finished migration must still say what it did"
    )


def test_a_cancel_says_you_stopped_it_and_a_stop_does_not() -> None:
    """⚠ **A NEAR-MISS, pinned so it stays fixed.** `(ahc)`

    The first draft reworded both arms to *"before it stopped"*. That is right for a stop nobody
    asked for and **wrong for a cancel**, which is the user's own act - and three `tests/e2e/`
    files assert the old sentence directly (`test_cancel_renders_cancelled.py`), so the browser
    lane would have gone red on a change made for tidiness. `(aer)` is that exact shape: a wording
    collision the affected files assert, reachable in the first two minutes and found in the
    twenty-eighth.

    The two arms are different sentences because they are different facts. `onCancelled` is
    reached only when the job's cancel flag is set; `onSuccess` with a `stopped` payload is
    reached when nobody asked it to stop.
    """
    script = _script()
    assert script.count("before you stopped it") >= 2, (
        "the cancel arms stopped saying the user stopped it; tests/e2e assert this sentence"
    )
    assert script.count("before it stopped") >= 2, (
        "the stopped arms blame the user for a stop nobody asked for"
    )


def test_a_cancel_is_not_painted_as_a_fault() -> None:
    """⚠ **The user's own act must never read as a failure**, which is why `fault` is a field.

    Both halves: the table says a cancel is not a fault, and the script styles the banner from
    that field rather than from the headline text.
    """
    assert STOP_WORDING[MigrationStopKind.CANCELLED].fault is False
    assert STOP_WORDING[MigrationStopKind.GROUND_MOVED].fault is True
    assert STOP_WORDING[MigrationStopKind.COULD_NOT_CONTINUE].fault is True
    assert '${s.fault ? " warn" : ""}' in _script(), (
        "the banner no longer takes its warning styling from `fault`"
    )


def test_every_stop_kind_is_worded() -> None:
    """Anti-vacuity, aimed at an ADDED member - the shape `_WORDING` guards for the CLI.

    Indexing `STOP_WORDING` raises `KeyError` on a new member rather than wording it by an `else`,
    but only if something reaches it. This asserts the table covers the enum directly.
    """
    unworded = [kind for kind in MigrationStopKind if kind not in STOP_WORDING]
    assert not unworded, f"these stop kinds have no words for any surface: {unworded}"
    assert len(STOP_WORDING) == len(list(MigrationStopKind)) >= 3


def test_the_script_was_actually_read() -> None:
    """A file read that returned nothing would make every assertion above true."""
    script = _script()
    assert len(script) > 100_000, f"app.js read as {len(script)} bytes; is the path still right?"
    assert re.search(r"function migrationStopNote\(", script), "the stop renderer is gone"
