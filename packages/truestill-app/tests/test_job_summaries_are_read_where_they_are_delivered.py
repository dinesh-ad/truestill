"""A job summary's keys, checked against what its own screen reads. `(ahn)` stage 3

`(ahl)`'s census works at key-NAME granularity and is blind to a collided field:
`BakePreview.absent` is rendered at `app.js:4131`, so the name reads as live and
**`BakeSummary.absent` never enters the dead set** - the one field `(abm)` and `(ahl)` both named
and neither could see. Stages 1 and 2 made the declared end exact, which makes a narrower and
stronger question askable: *for this payload, delivered to this screen, which of its keys does that
screen read?*

⚠ **THIS IS DELIBERATELY NOT A GENERAL JAVASCRIPT SCOPE ANALYSER, and that is a ruling.** Measured
on the route channel: `/api/library/status` yields **69** scoped key reads against a type declaring
**25** - a variable escapes the block a regex can bound, and over-collection reports a dead field as
live. So the scope here is the one place the binding is unambiguous: a `runJob({...})` block, where
`d.summary` **is** the payload and the route its `start` calls names the type.

⚠ **BOTH DIRECTIONS OF ERROR ARE REAL AND WERE BOTH MET WHILE WRITING THIS**, which is why
:data:`UNREAD` is asserted as an **exact set** rather than as a floor:

* **under-collection** marks a LIVE field dead. The first draft followed one level from
  `d.summary` and reported `BackupRunSummary.photos/videos/audio` unread; they are read by
  `mediaCount(r)`, which `backupCompletion(r)` calls - a **second** level. Cry-wolf, and it would
  have been shipped as a finding.
* **over-collection** marks a DEAD field live, which is the whole defect this exists to catch.

**Set equality catches both, and a third**: a binding that silently breaks reports *zero* reads and
would otherwise pass as a clean sweep declaring every key dead. `test_a_payload_that_reads_nothing_is_a_broken_binding`
holds that case by name because it is the one that would quietly destroy the guard's meaning.

⚠ **THIS FILE HAS AN END DATE, and it is the same one `test_no_thirty_fifth_dead_payload_key.py`
has.** Both are text searches over `app.js`, and both die at `(ahn)` **stage 5**, when a read
becomes a **type reference** the TypeScript compiler resolves and neither the chaser nor the
key-name census has anything left to do. ⚠ **This one dies first**: its subject is 7 `runJob`
blocks, so the first migrated island that owns a job screen retires its rows one at a time, while
P83's guard covers all 289 key names and survives until the last screen moves. Retire them, do not
inherit them.

**Cost, declared rather than suppressed** (`ENGINEERING_STANDARD.md` §4): one `ast` pass over the
app package for declarations, one comment-stripped read of `app.js`, then a brace-matched walk per
bound block with function following to a bounded depth. Well under a second.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "packages/truestill-app/src/truestill_app"
APP_JS = APP / "static/app.js"

#: Route → the summary TypedDict its job delivers. **The control, and it is declared rather than
#: discovered**: a chaser that fails to bind reports nothing, so a subset built from "whatever
#: bound today" would shrink silently. 7 of the 16 `runJob` blocks; the other 9 are below.
BOUND: dict[str, str] = {
    "/api/backup/run": "BackupRunSummary",
    "/api/dates/bake/run": "BakeSummary",
    "/api/migrate/preview": "MigrationPreviewOk",
    "/api/migrate/undo/preview": "UndoJobSummary",
    "/api/organize/undo/apply": "OrganizeUndoJobSummary",
    "/api/organize/undo/preview": "OrganizeUndoJobSummary",
    "/api/verify/run": "VerifyJobSummary",
}

#: The nine blocks deliberately outside :data:`BOUND`, each with why. ⚠ **Listed rather than
#: omitted**: a subset whose exclusions are invisible reads as full coverage.
UNBOUND: dict[str, str] = {
    "runJob itself": "the helper's own definition, not a caller - it has no route",
    "/api/migrate/undo/apply": "renders through a path the chaser does not follow; reports zero "
    "reads, and zero is exactly the answer this file refuses to trust",
    "/api/migrate/run": "as above",
    "/api/ingest/archives/run": "zero reads, and its factory returns a UNION of three payloads",
    "/api/ingest/preview": "zero reads, and a union of two",
    "/api/organize/preview": "the factory returns `OrganizePreviewEmpty | OrganizePreviewSummary`; "
    "a read set cannot be attributed to one arm of a union",
    "/api/organize/run": "as above, `CompletionBase | OrganizeDoneSummary`",
    "/api/events/{session}/preview": "the path is built by template, so `(ahn)` stage 2's "
    "resolver - which keys on a literal - names no type for it",
    "/api/events/{session}/apply-to-disk": "as above",
}

#: Per payload, the keys its own screen does **not** read. ⚠ **An exact set, not a floor** - see
#: the module docstring. Each row says what the field is, not merely that it is unread.
UNREAD: dict[str, dict[str, str]] = {
    "BakeSummary": {
        "absent": "⚠ THE FIELD `(abm)` AND `(ahl)` BOTH NAMED AND NEITHER COULD SEE. A bake run "
        "reports what failed and stays silent about files the catalog expected and could not "
        "find. A candidate for RENDERING, not deletion - `bakeCompletion` is where it belongs",
        "drive_label": "redundant rather than missing: the `completeness` sentence this screen "
        "does render already carries the label. A candidate for DELETION",
        "elapsed_seconds": "injected for every dict summary by `jobs.py`; this screen shows no "
        "duration. Dead HERE and live on `/api/backup/run`, which is payload granularity earning "
        "its name - the same key, opposite answers",
    },
    "BackupRunSummary": {
        "copied": "the headline counts with `mediaCount(r)` - photos + videos + audio - so the "
        "total is computed twice and this copy is unused. A candidate for DELETION",
        "failed": "⚠ a run that could not copy a file says so nowhere on this screen, though "
        "`(afw)` Stage 4 exists to count it. A candidate for RENDERING",
        "target_path": "the screen already names the drive by label (`to`)",
    },
    "MigrationPreviewOk": {
        "elapsed_seconds": "a preview shows no duration",
        "label": "the drive is named by `drive_label` on the same payload",
        "pending_drives": "in `(ahl)`'s key-name dead list already; this confirms it per payload",
        "template": "the layout string; the screen renders `moves` instead",
    },
    "OrganizeUndoJobSummary": {
        "applied": "the screen branches on which handler fired, not on the flag",
        "dest_root": "the browser holds the path it submitted",
        "elapsed_seconds": "no duration on this screen",
        "record_error": "⚠ a run record that failed to write is reported nowhere. A candidate "
        "for RENDERING",
        "run_id": "server-side identity; the client posts back the handle it was given",
        "source_root": "as `dest_root` - the browser submitted both paths and still holds them",
        "still_armed": "the screen re-fetches state through `/api/organize/undo` instead",
        "stopped": "⚠ `(ahc)` fixed exactly this class on the migrate screens. A candidate for "
        "RENDERING",
    },
    "UndoJobSummary": {
        "applied": "as `OrganizeUndoJobSummary.applied`",
        "elapsed_seconds": "no duration on this screen",
        "label": "the drive is named elsewhere on the card",
        "run_id": "server-side identity; the client posts back the handle it was given",
        "stopped": "⚠ read on the migrate-undo screen through a different path; unread from the "
        "summary itself",
    },
    "VerifyJobSummary": {"elapsed_seconds": "this screen shows no duration"},
}


def _code(javascript: str) -> str:
    """`javascript` with `/* */` and `//` comments removed - `(ahl)` measured this as worth five
    key names, and a key named only in a comment is read by nobody."""
    blocks = re.sub(r"/\*.*?\*/", "", javascript, flags=re.S)
    return "\n".join(re.sub(r"//.*$", "", line) for line in blocks.splitlines())


def _matching_brace(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(text)


def _function_body(text: str, name: str) -> tuple[str, str] | None:
    """``(first parameter, body)`` for a top-level ``function name(...)``."""
    found = re.search(rf"function {re.escape(name)}\(([^)]*)\)\s*\{{", text)
    if found is None:
        return None
    opening = found.end() - 1
    return found.group(1).split(",")[0].strip(), text[opening : _matching_brace(text, opening) + 1]


def _reads(
    text: str, scope: str, expression: str, depth: int = 0, seen: frozenset[str] = frozenset()
) -> set[str]:
    """Keys read off `expression` within `scope`, following rebindings and calls.

    ⚠ **Transitive, with a depth bound, and the transitivity is not optional.** `backupCompletion`
    hands the whole payload to `mediaCount`, so a one-level follow reported three live fields as
    dead. The bound stops a cycle; `seen` stops re-entering a function.
    """
    if depth > 4:
        return set()
    keys = set(re.findall(rf"{re.escape(expression)}\.(\w+)", scope))
    for rebound in re.findall(rf"const\s+(\w+)\s*=\s*{re.escape(expression)}\s*;", scope):
        keys |= _reads(text, scope, rebound, depth + 1, seen)
    for called in set(re.findall(rf"(\w+)\(\s*(?:\{{\s*\.\.\.)?{re.escape(expression)}\b", scope)):
        if called in seen:
            continue
        body = _function_body(text, called)
        if body is not None:
            keys |= _reads(text, body[1], body[0], depth + 1, seen | {called})
    return keys


def _declared_keys() -> dict[str, list[str]]:
    keys: dict[str, list[str]] = {}
    for path in sorted(APP.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and any(
                "TypedDict" in ast.unparse(base) for base in node.bases
            ):
                keys[node.name] = [
                    s.target.id
                    for s in node.body
                    if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
                ]
    return keys


def _reads_by_payload() -> dict[str, set[str]]:
    """``summary type -> every key its bound `runJob` blocks read``, unioned.

    Two routes share `OrganizeUndoJobSummary`; a key either screen reads is read.
    """
    text = _code(APP_JS.read_text(encoding="utf-8"))
    found: dict[str, set[str]] = defaultdict(set)
    for opening in [m.end() - 1 for m in re.finditer(r"runJob\(\{", text)]:
        block = text[opening : _matching_brace(text, opening) + 1]
        route = re.search(r"""(?:api|get|post)\(\s*[`"']([^`"'?]+)""", block)
        if route is not None and route.group(1) in BOUND:
            found[BOUND[route.group(1)]] |= _reads(text, block, "d.summary")
    return found


def test_every_bound_payload_reads_exactly_what_is_declared_unread() -> None:
    """**The guard.** Loop the DERIVED payloads; assert into the DECLARATION.

    Set equality in both directions, because both errors are real: a key that stops being read
    must be declared, and one that starts being read must leave the table.
    """
    declared, reads = _declared_keys(), _reads_by_payload()
    wrong: list[str] = []
    for payload in sorted(BOUND.values()):
        keys = set(declared.get(payload, []))
        assert keys, f"{payload} declares no keys; the AST pass is looking at the wrong tree"
        derived = keys - reads[payload]
        listed = UNREAD.get(payload, {}).keys()
        if derived - listed:
            wrong.append(
                f"  {payload}: no longer read and undeclared -> {sorted(derived - listed)}"
            )
        if listed - derived:
            wrong.append(f"  {payload}: declared unread and now read -> {sorted(listed - derived)}")

    assert not wrong, (
        "a job summary's keys and its screen have moved apart:\n"
        + "\n".join(wrong)
        + "\n\nIf a field became unread, render it or declare it WITH what it is. If it became "
        "read, delete the row - that is the good direction."
    )


def test_a_payload_that_reads_nothing_is_a_broken_binding() -> None:
    """⚠ **THE INVERTED CRY-WOLF, and the case that decides whether this file is safe to keep.**

    A chaser that silently stops binding returns an empty read set, every declared key falls into
    *unread*, and the guard reports a clean sweep of dead fields about a screen that renders them
    all. Zero is never the right answer for a payload listed in :data:`BOUND` - each of the seven
    was confirmed by reading its renderer.
    """
    reads = _reads_by_payload()
    silent = sorted(payload for payload in set(BOUND.values()) if not reads[payload])

    assert not silent, (
        f"these bound payloads read nothing at all: {silent}\n"
        "That is a broken binding, not a dead payload. Fix the chaser or move the row to "
        "`UNBOUND` with the reason - never leave it here reporting every key dead."
    )


def test_the_subset_and_its_exclusions_are_both_declared() -> None:
    """Anti-vacuity, and the exclusions carry it as much as the inclusions.

    Every `runJob` block is either bound or excluded by name. A block that is neither would be
    invisible, which is the hand-list blind spot `(ahi)` and `cli-app-parity.md` both record.
    """
    text = _code(APP_JS.read_text(encoding="utf-8"))
    blocks = [m.end() - 1 for m in re.finditer(r"runJob\(\{", text)]

    assert len(blocks) >= 14, f"only {len(blocks)} runJob blocks found; the pattern moved"
    assert len(BOUND) == 7, "the bound subset changed size without a ruling"
    assert len(set(BOUND.values())) == 6, (
        "seven routes over six types - `/api/organize/undo/preview` and `.../apply` share "
        "`OrganizeUndoJobSummary`, and a key either screen reads is read"
    )
    assert len(BOUND) + len(UNBOUND) == len(blocks), (
        f"{len(BOUND)} bound + {len(UNBOUND)} excluded != {len(blocks)} blocks; a block is "
        "neither, which is the hand-list blind spot this assertion exists for"
    )
    assert all(reason.strip() for reason in UNBOUND.values()), "an exclusion with no reason"
    for payload, rows in UNREAD.items():
        for key, why in rows.items():
            assert len(why) > 20, f"{payload}.{key} is listed unread with no reason"


def test_comment_stripping_and_transitive_following_are_both_load_bearing() -> None:
    """Two rules this file cannot work without, measured rather than asserted.

    `mediaCount` is the transitive case: `backupCompletion(r)` hands it the whole payload, so
    without following twice three live fields read as dead.
    """
    text = _code(APP_JS.read_text(encoding="utf-8"))
    block = "onSuccess: (d) => { backupCompletion(d.summary); }"

    deep = _reads(text, block, "d.summary")
    shallow = _reads(text, block, "d.summary", depth=4)

    assert {"photos", "videos", "audio"} <= deep, "the second level of following was lost"
    assert not shallow, "the depth bound is not being applied"
    assert "//" not in _code("const x = 1; // absent\n"), "comments survive the stripper"
