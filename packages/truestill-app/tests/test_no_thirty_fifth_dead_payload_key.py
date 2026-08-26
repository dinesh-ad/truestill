"""A field a route computes and no surface reads. **34 today, and no thirty-fifth.** `(ahl)`

`PROJECT_STATUS.md`'s third exit condition - *"no route computes a field no consumer reads"* - was
kept by hand and named **two** instances. Derived from source it is **34** of **289** distinct
payload key names, and the hand census had counted its one named instance three different ways.

⚠ **WHAT THIS PROVES, AND WHAT IT CANNOT.** Two halves, and only the first is mechanical:

* **Mechanical**: a key appears in the derived inventory and in :data:`DEAD`. Both ends are read
  from source, so a **new** field that ships unread fails this file. That is the failure that
  actually happens.
* **NOT mechanical**: whether a reason in :data:`DEAD` is *true*. Those are prose. P69 measured
  exactly this on `MUTATING_RUNS` - a mutation that rewrites a row's stated policy without touching
  behaviour **survives** - so the reasons are documentation and are labelled as such rather than
  read as assertions.

⚠ **IT CLAIMS NO LIVENESS, and no ecosystem offers one statically.** GraphQL is the only one that
answers *"is this field still used"* at all, and it does so at **runtime**: Apollo GraphOS Insights
reports which clients still query a deprecated field; Hive's `deprecatedSchema(period:)` attaches
usage over a window. REST has no equivalent. `apollo-kotlin#991`, open since 2018, is the same
limit in another language - generated accessors mean code analysis cannot tell whether a client
USES what it asked for. So this is a **declaration with a floor**, never a proof.

⚠ **IT IS A STOPGAP WITH A KNOWN END DATE, AND THAT IS SAID HERE RATHER THAN ONLY IN THE ENTRY.**
Its consumed end is a text search over `static/app.js`, and `app.js` is being **deleted** by the
React migration. **Retire this file with it.** What replaces it is `(ahn)`: the backend emits an
OpenAPI spec, `openapi-typescript` generates the types, the frontend imports them - mechanical at
*both* ends, which is the end this file cannot reach. A guard nobody retires is how a dead check
outlives the thing it checked, keeps passing, and gets quoted as coverage.

**Cost, declared rather than suppressed** (`ENGINEERING_STANDARD.md` §4): one `ast.parse` per file
under `truestill_app/` (**117** TypedDicts across them), then one compiled regex per distinct key
over three concatenated texts - O(files + keys x text). The whole module runs in well under a
second and is in `make check`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "packages/truestill-app/src/truestill_app"
APP_JS = APP / "static/app.js"
REACT = ROOT / "packages/truestill-app/frontend/src"
CLI = ROOT / "packages/truestill-cli/src/truestill_cli/cli.py"

#: The measured inventory on 2026-08-25, used as anti-vacuity floors. ⚠ **They sit just under the
#: MEASURED figures, not far under.** `(agu)`'s floor read `>= 12` against a real 16 and could
#: never have fired; a floor with that much slack is a comment. These allow ordinary growth and
#: catch a collector that silently stops seeing a declaration form or a directory.
MEASURED_TYPEDDICTS = 117
MEASURED_SLOTS = 579
MEASURED_KEYS = 289

#: Keys that no consumer reads, each with **why**. ⚠ The list is derived; the reasons are a human
#: read of the surrounding code and nothing here checks them - see the module docstring.
#:
#: ⚠ **`BakeSummary.absent` IS ABSENT FROM THIS LIST AND IS DEAD.** A key-name census cannot see a
#: collided field: `BakePreview.absent` is rendered at `app.js:4158`, so the NAME is read and never
#: reaches the derived set, while `BakeSummary.absent` (`service/bake.py:166`) is not read by
#: `bakeCompletion` at all. **34 is a floor, not a count.** Closing that needs payload granularity
#: - knowing which JavaScript variable holds which route's response - which is `(ahn)`, not this.
DEAD: dict[str, str] = {
    # Identity the browser was handed and never needs back.
    "run_id": "the client posts back the handle it was given; the server resolves the run",
    "uuid": "screens key on the label; `app.js:2999` says the server resolves the uuid",
    "event_id": "selection is echoed by position, not id",
    "trip_id": "as `event_id`",
    # A path the client already knows, because it sent it.
    "dest_root": "the browser holds the path it submitted",
    "target_path": "as `dest_root`",
    "parent": "the browser derives the parent from the path it asked for",
    # Preflight facts computed and never surfaced.
    "claimed_bytes": "the precheck refuses or proceeds; the arithmetic is not shown",
    "free_bytes": "as `claimed_bytes`. 36 test hits and no renderer",
    "oversized": "the destination limit is reported as a refusal, not as a list",
    "occupied": "the preview names folders it will not remove, not why",
    "readable": "unreadable is expressed by the absence of a result",
    "can_register": "three payloads carry it; the screens branch on the error code",
    # A count a headline replaced.
    "dates_exif": "the ingest preview shows one total",
    "dates_upload_approx": "as `dates_exif`",
    "exact_duplicates_found": "completeness is rendered as a percentage",
    "redundancy_floor": "its own comment says it exists to make a sentence safe to write; the "
    "sentence is written from `files_one_copy`",
    "catalog_presence": "the custody strip renders a tier, not this string",
    "unplaced": "its comment says a zero here is a fact and not an omission - and no surface "
    "states the fact",
    "resumed": "the completion says how many moved, not how many were recovered",
    "day_totals": "the proposal renders groups, not per-day counts",
    "pending_drives": "the preview warns per drive in prose",
    # A mechanism or echo the UI derives another way.
    "modes": "the mode list is rendered from the radio group's own markup",
    "uses_rename": "the screen branches on the mode name",
    "requires_destination": "as `uses_rename`",
    "still_armed": "the screen re-fetches state instead of reading the echo",
    "named_events": "the apply result is rendered as one count",
    "named_trips": "as `named_events`",
    "existing_names": "collision avoidance happens server-side",
    "source_hints": "the suggestion is shown, not its provenance",
    "missing_sidecar": "the ingest summary does not distinguish this cause",
    "distance": "the duplicate sample shows the match, not how near",
    "matched_path": "`app.js:2643` explains in a comment that this field could never answer the "
    "question the screen asks",
    "operation": "the busy banner names the drive, not the job",
}


def _declared(root: Path) -> dict[str, list[str]]:
    """Every payload key under `root`, mapped to the TypedDicts declaring it.

    ⚠ **BOTH DECLARATION FORMS, and the second is not a nicety.** `service/backup.py` writes
    `BackupPreviewOk = TypedDict("BackupPreviewOk", {...})` because it carries the reserved word
    `from` as a key, which the class body cannot express. A collector reading only `class X(
    TypedDict)` is `(agu)`'s defect exactly - one call shape checked, the other invisible - and it
    would miss that payload entirely.

    ⚠ **AST rather than runtime introspection, and the repo has already paid for that.**
    `test_migrate_reports_its_stop.py:149` records a first draft asserting on `__required_keys__`
    that was **vacuous**: under `from __future__ import annotations` the annotations are strings,
    so `TypedDict` cannot see through `NotRequired[...]` and every key reads as required.
    """
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                "TypedDict" in ast.unparse(base) for base in node.bases
            ):
                for statement in node.body:
                    if isinstance(statement, ast.AnnAssign) and isinstance(
                        statement.target, ast.Name
                    ):
                        found.setdefault(statement.target.id, []).append(node.name)
            elif (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and getattr(node.value.func, "id", "") == "TypedDict"
                and len(node.value.args) > 1
                and isinstance(node.value.args[1], ast.Dict)
            ):
                name = ast.unparse(node.value.args[0]).strip("'\"")
                for key in node.value.args[1].keys:
                    if isinstance(key, ast.Constant):
                        found.setdefault(str(key.value), []).append(name)
    return found


def _code_only(javascript: str) -> str:
    """`javascript` with `/* */` and `//` comments removed. **Load-bearing, not hygiene.**

    A key named in a comment is not a key anybody reads, and this corpus is full of comments that
    name fields in order to say something ABOUT them - `app.js:2643` mentions `matched_path`
    precisely to explain that it could never answer the question. `test_comment_stripping_is_load_bearing`
    measures what this is worth rather than asserting that it matters.
    """
    without_blocks = re.sub(r"/\*.*?\*/", "", javascript, flags=re.S)
    return "\n".join(re.sub(r"//.*$", "", line) for line in without_blocks.splitlines())


def _consumers() -> tuple[str, str]:
    """`(app.js code, React source)` - **the two surfaces a browser payload can reach.**

    ⚠ **React is read even though it consumes ZERO payload keys today**, measured: `main.tsx`
    contains no `fetch` and no `/api/`, and types its payload `Record<string, unknown>`. Including
    it is not decoration. `(adi)` migrates by ISLAND, so the first migrated screen makes React the
    only reader of some field, and a guard blind to the new consumer would go red on a key the
    instant it became live - failing on the migration it exists to protect.

    `cli.py` is deliberately NOT here. It does not consume route payloads; it calls core directly,
    which is why `cli.py:4059` prints `outcome.absent` off the core dataclass while the app's
    `BakeSummary.absent` reaches nothing.
    """
    react = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(REACT.rglob("*"))
        if path.suffix in {".ts", ".tsx"}
    )
    return _code_only(APP_JS.read_text(encoding="utf-8")), react


def _unread(keys: list[str], *, app_js: str, react: str) -> set[str]:
    """Those of `keys` that appear in neither surface, on a word boundary."""
    return {
        key
        for key in keys
        if not re.search(rf"\b{re.escape(key)}\b", app_js)
        and not re.search(rf"\b{re.escape(key)}\b", react)
    }


def test_no_thirty_fifth_dead_payload_key() -> None:
    """**The guard.** Loop the DERIVED inventory; assert into the DECLARATION.

    `ENGINEERING_STANDARD.md`'s seventy-second member: iterating `DEAD` instead would pass
    perfectly against an emptied table. Iterating the derived side cannot go vacuous by
    construction - `test_a_declaration_that_lost_its_keys_still_fails` proves it.
    """
    app_js, react = _consumers()
    dead = _unread(list(_declared(APP)), app_js=app_js, react=react)
    undeclared = sorted(dead - DEAD.keys())

    assert not undeclared, (
        "these payload keys are computed and no surface reads them, and they are not in `DEAD`:\n"
        + "\n".join(f"  {key}" for key in undeclared)
        + "\n\nEither a consumer should read it, or add it to `DEAD` WITH THE REASON. Adding it "
        "without one turns this file into a list of names, which is what it replaced."
    )


def test_a_declared_key_that_became_live_is_removed() -> None:
    """⚠ **CRY-WOLF HALF, and the one that keeps the list honest as screens are built.**

    When a field finally gets rendered, `DEAD` must shrink. Without this the declaration only ever
    grows and slowly becomes a list of keys that ARE read - the census equivalent of a suppression
    file, and unfalsifiable in the direction that matters during a UI rewrite.
    """
    app_js, react = _consumers()
    dead = _unread(list(_declared(APP)), app_js=app_js, react=react)
    now_read = sorted(DEAD.keys() - dead)

    assert not now_read, (
        "these keys are declared dead and a surface now reads them:\n"
        + "\n".join(f"  {key}" for key in now_read)
        + "\n\nDelete the row. This is the good direction - a field became live."
    )


def test_the_derived_inventory_is_the_measured_size() -> None:
    """Anti-vacuity, floored just under the MEASURED figures rather than far under.

    A collector that stopped seeing one declaration form, or that was pointed at a directory that
    moved, would return a smaller inventory and every assertion above would pass on it.
    """
    declared = _declared(APP)
    slots = sum(len(names) for names in declared.values())
    typeddicts = len({name for names in declared.values() for name in names})

    assert len(declared) >= MEASURED_KEYS - 10, f"only {len(declared)} distinct keys"
    assert slots >= MEASURED_SLOTS - 20, f"only {slots} key slots"
    assert typeddicts >= MEASURED_TYPEDDICTS - 5, f"only {typeddicts} TypedDicts"
    assert len(DEAD) >= 30, f"the declaration holds {len(DEAD)}"


def test_it_reads_both_typeddict_forms(tmp_path: Path) -> None:
    """⚠ **`(agu)`'s defect, refused in advance.** That guard read one call shape and was blind to
    the other for as long as it existed. The functional form is not hypothetical here: it is how
    `service/backup.py` declares `BackupPreviewOk`, because `from` is a reserved word.

    Driven against a written-here source tree rather than the real one, so the proof does not
    depend on the corpus continuing to contain an example.
    """
    (tmp_path / "class_form.py").write_text(
        "from typing import TypedDict\n\nclass A(TypedDict):\n    from_the_class: int\n",
        encoding="utf-8",
    )
    (tmp_path / "functional_form.py").write_text(
        'from typing import TypedDict\n\nB = TypedDict("B", {"from": str, "from_the_call": int})\n',
        encoding="utf-8",
    )
    declared = _declared(tmp_path)

    assert declared.get("from_the_class") == ["A"], "the class form was not read"
    assert declared.get("from_the_call") == ["B"], "the FUNCTIONAL form was not read"
    assert "from" in declared, "a reserved word as a key is the reason the functional form exists"


def test_comment_stripping_is_load_bearing() -> None:
    """⚠ **What the naive grep costs, MEASURED rather than asserted - and it is the guard's own
    calibration.**

    ⚠ **THIS NUMBER WAS PUBLISHED WRONG AND IS CORRECTED HERE.** `(ahl)` said comment stripping
    *"moved the answer from 20 to 34"*, i.e. fourteen keys. Those two figures came from two
    DIFFERENT measurements - 20 counts keys unread by app.js, React **and `cli.py`**, while 34
    counts the two browser surfaces this guard actually uses. Two variables moved at once. Holding
    the surfaces fixed, the real effect is **five**: `matched_path`, `modes`, `operation`,
    `redundancy_floor`, `uuid`. Smaller than claimed, and still decisive - each is a field a naive
    grep would certify as live on the strength of a comment that names it.
    """
    raw = APP_JS.read_text(encoding="utf-8")
    _, react = _consumers()
    keys = list(_declared(APP))

    stripped_dead = _unread(keys, app_js=_code_only(raw), react=react)
    naive_dead = _unread(keys, app_js=raw, react=react)
    hidden = stripped_dead - naive_dead

    assert hidden, (
        "comment stripping changed nothing; either the corpus changed or it is not needed"
    )
    assert hidden <= DEAD.keys(), (
        f"{sorted(hidden - DEAD.keys())} hidden by a comment and undeclared"
    )


def test_a_key_read_only_by_the_react_source_is_not_dead() -> None:
    """⚠ **The migration case, handled now rather than discovered during it.**

    `(adi)` migrates by island, so the first React screen will be the ONLY reader of some field.
    A guard that looked at `app.js` alone would go red the moment a key became live - failing on
    exactly the work it exists to protect. Proved with injected surfaces rather than by waiting.
    """
    keys = ["only_in_react", "in_neither"]

    assert _unread(keys, app_js="", react="const x = payload.only_in_react;") == {"in_neither"}
