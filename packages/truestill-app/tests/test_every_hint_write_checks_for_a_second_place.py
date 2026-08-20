"""Every site that binds a drive uuid to a path first asks whether that uuid answers elsewhere.

`(adx)` gap 1. A drive's remembered path is its ONLY uuid-to-path memory - `drives` has no path
column - and it is overwritten in place. So the moment a second location could be observed is the
moment before it is destroyed, at each site that writes `path_hint.drive.<uuid>`.

**Why a guard and not a convention.** Six sites write that hint today. A seventh added later would
bind an identity to a path with nothing asking the question, and **nothing would fail** - the
custody count would simply be short by one again, silently, which is the direction that gets a
user to delete a copy they still needed.

⚠ **BOTH LISTS ARE CHECKED FOR EXHAUSTIVENESS, and that is the half that matters.** A list of what
is covered is satisfiable by forgetting: a new site that appears in neither list would pass a guard
that only verified the covered ones. Here a site in neither fails, so adding one forces a decision
rather than allowing an omission.

Follows `test_every_entry_point_refuses_an_unusable_catalog.py` (function-level, two named dicts,
an anti-rot test) and takes the idle-guard test from
`test_catalog_opens_go_through_the_session.py`.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]

_SURFACES = (
    _REPO / "packages/truestill-cli/src/truestill_cli",
    _REPO / "packages/truestill-app/src/truestill_app",
)

#: `module::function -> how it tells the user`. Each must call `second_location_note`.
_DISCLOSES: dict[str, str] = {
    "truestill_cli/cli.py::_cmd_verify": (
        "stderr, via `_say_if_two_places`, before `upsert_drive` and the hint write - which sit "
        "five lines apart and destroy the two halves of the evidence between them"
    ),
    "truestill_cli/cli.py::_init_drive": "stderr, via `_say_if_two_places`",
    "truestill_cli/cli.py::_register_destination": (
        "stderr, via `_say_if_two_places`. **Structurally silent today**: this site mints a fresh "
        "uuid, so there is never a remembered path to disagree with. Listed and called anyway so "
        "a future change that reuses an existing identity here cannot bypass the check"
    ),
    "truestill_app/service/verify.py::target": (
        "`VerifyJobSummary.second_location`, rendered as a banner on the Check screen"
    ),
}

#: `module::function -> what a user LOSES by it being here`. Not why it is hard - what is owed.
_NOT_YET_SURFACED: dict[str, str] = {
    "truestill_app/service/drives.py::attach_drive": (
        "**A user attaching a drive whose identity already answers at another live path is told "
        "nothing, and the custody count stays short by one.** No carrier exists: `DriveAttachment` "
        "is never serialised, and the `write=True` path - the one that writes the hint - has its "
        "return value discarded outright by `service/backup.py`. Surfacing it needs a channel "
        "that does not exist yet, which is why this is owed rather than merely undone"
    ),
    "truestill_app/service/organize.py::_register_destination": (
        "**An organize run whose destination is a clone of a drive Truestill already knows "
        "discloses nothing**, so the run's own copies are recorded against an identity that "
        "answers in two places. ⚠ This said the carrier was a wider change because "
        "`CompletionBase` is 'a 17-key payload pinned by two e2e tests' - CORRECTED 2026-08-20, "
        "that was folklore: 19 keys, the Python guard is a superset check, and no e2e test "
        "asserts the key set. `(aem)` added no key at all. The disclosure is still owed; the "
        "payload was never what stood in its way"
    ),
}


#: Names that count as asking the question. The CLI's three sites go through one shared emitter
#: rather than calling core directly - that is the point of it, since the message and the
#: read-before-the-writes ordering must not exist in three copies. The wrapper is verified to
#: actually ask by `test_the_shared_emitter_really_asks`, so this stays one hop and not a hole.
_ASKS = {"second_location_for", "_say_if_two_places"}


def _writes_and_calls(module: Path) -> dict[str, tuple[bool, set[str]]]:
    """`function -> (writes the hint?, names it calls)`, attributing each call to its OWN function.

    Two things this has to get right, and the first attempt got both wrong:

    * **A write, not a mention.** `drive_path_hint` is called by eleven READERS as well - every
      `get_setting(drive_path_hint(...))` and `drive_reach` call site. Matching the name alone
      reported all of them. The write is `set_setting(drive_path_hint(...), ...)`, so the match is
      on the *method* with the hint as its first argument.
    * **The innermost function owns the call.** `ast.walk` from an outer function descends into
      nested ones, so `verify_run` and `organize_run` both claimed their `target` closure's write.
      Nodes are assigned to the nearest enclosing function instead.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    owner: dict[ast.AST, str] = {}
    functions: dict[str, tuple[bool, set[str]]] = {}

    def visit(node: ast.AST, enclosing: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                functions.setdefault(child.name, (False, set()))
                visit(child, child.name)
                continue
            if enclosing is not None:
                owner[child] = enclosing
            visit(child, enclosing)

    visit(tree, None)
    for node, name in owner.items():
        if not isinstance(node, ast.Call):
            continue
        writes, called = functions.get(name, (False, set()))
        if isinstance(node.func, ast.Name):
            called = called | {node.func.id}
        is_write = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "set_setting"
            and bool(node.args)
            and isinstance(node.args[0], ast.Call)
            and isinstance(node.args[0].func, ast.Name)
            and node.args[0].func.id == "drive_path_hint"
        )
        functions[name] = (writes or is_write, called)
    return functions


def _hint_writers() -> dict[str, set[str]]:
    """`package/path.py::function -> the names it calls`, for every function writing the hint.

    Keyed against each surface ROOT's parent, never `parents[1]`: `service/verify.py` sits a
    directory deeper than `cli.py`, so the shallower key would give two different depths and no
    list below could be right for both. Recorded because the sibling guard caught exactly this on
    its first run.
    """
    writers: dict[str, set[str]] = {}
    for root in _SURFACES:
        for module in sorted(root.rglob("*.py")):
            relative = module.relative_to(root.parent).as_posix()
            for name, (writes, called) in _writes_and_calls(module).items():
                if writes:
                    writers[f"{relative}::{name}"] = called
    return writers


def test_every_hint_writer_is_classified_and_the_disclosing_ones_actually_ask() -> None:
    writers = _hint_writers()

    unclassified = sorted(set(writers) - set(_DISCLOSES) - set(_NOT_YET_SURFACED))
    assert not unclassified, (
        f"{unclassified} binds a drive uuid to a path and is in neither list. Decide which it is: "
        "call `second_location_note` before the write and join _DISCLOSES, or join "
        "_NOT_YET_SURFACED saying what a user loses by the silence. `(adx)`."
    )

    silent = sorted(
        site for site, called in writers.items() if site in _DISCLOSES and not (called & _ASKS)
    )
    assert not silent, (
        f"{silent} is listed as disclosing but never calls `second_location_note`, so a drive "
        "whose identity answers in two places is recorded silently and the custody count stays "
        "short by one."
    )


def test_neither_list_outlives_the_call_sites_it_describes() -> None:
    """A list nobody prunes becomes a list of places the rule stopped applying."""
    writers = _hint_writers()
    stale = sorted(site for site in (_DISCLOSES | _NOT_YET_SURFACED) if site not in writers)
    assert not stale, (
        f"{stale} no longer writes a drive path hint. Remove the entry in the same commit that "
        "removed the write."
    )


def test_the_guard_is_not_idle() -> None:
    """Cry-wolf check. If the call-name match broke, every assertion above would pass vacuously."""
    writers = _hint_writers()
    assert len(writers) >= 6, (
        f"only {len(writers)} hint writers found; there were six when this was written, so the "
        "`drive_path_hint` match has stopped working and this file is guarding nothing."
    )


def test_the_shared_emitter_really_asks() -> None:
    """Closes the one hop `_ASKS` allows.

    Without this, renaming or gutting `_say_if_two_places` would leave three sites listed as
    disclosing, calling something that no longer asks anything, and the guard green.
    """
    cli = _REPO / "packages/truestill-cli/src/truestill_cli/cli.py"
    emitter = _writes_and_calls(cli).get("_say_if_two_places")
    assert emitter is not None, "`_say_if_two_places` is gone; three sites route through it"
    assert "second_location_for" in emitter[1], (
        "`_say_if_two_places` no longer calls `second_location_for`, so the three CLI sites that "
        "route through it ask nothing while still being listed as disclosing."
    )
