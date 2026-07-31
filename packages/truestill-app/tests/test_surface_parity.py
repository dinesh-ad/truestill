"""A fix that reaches one surface must reach its twin (audit F0/F38/cli.py:513 class).

**This guard protects the REPAIR, not the contract. Read that twice before trusting it green.**

Measured against the real defect, at three points in history:

===========================================  ======================
state                                        divergent expressions
===========================================  ======================
before the fix - both surfaces wrong          **0**
after the fix reached the app but not the CLI **1**
after it reached both                         **0**
===========================================  ======================

The pre-fix row is the important one. `cli.py` and `service/verify.py` were in *perfect
agreement and perfectly wrong* - both fell back to the source hash - and this guard scored
zero. It cannot tell you a shared contract is incorrect. It tells you a **repair** landed on one
copy and not the other, which is the shape of every instance so far: F0 (migrate-undo fixed,
organize-undo not), F38 (twelve job sites updated, one missed), and `cli.py:513` (the app's
verify fallback removed, the CLI's left).

Reading a green run here as "the contract is correct" is exactly the false confidence the audit
was full of, so it is said in the module docstring rather than a comment someone can skip.

**Why it is scoped this narrowly**, measured on a clean tree:

* comparing *any* argument of *any* shared callable flags **60 of 94** - unusable;
* narrowing to row-field expressions across all callables flags **9**, every one a builtin
  (``Path``, ``int``, ``print``, ``str``) - all false;
* narrowing to the **62 symbols both surfaces import from ``truestill_core``** flags **0** on a
  clean tree and **1** on the commit where the CLI still had its fallback.

Zero false, one true. A guard that fires on ordinary work gets switched off, taking its real
coverage with it (`ENGINEERING_STANDARD.md` §4), so the scope is the measurement rather than a
preference. Legitimate divergence is why the wide forms fail: the CLI genuinely passes
``pool``/``workers`` knobs the app does not, and that is not drift.

**Measured again after ``CopyToVerify.from_row`` landed: the compared population is now empty.**
``CopyToVerify`` was the only symbol both surfaces called with catalog-row fields, and giving the
mapping one home removed it. That is the *intended* end state, not a disarmed guard - the rule
this file exists to protect is better served by there being nothing to compare - but it changes
what each test below is for, and each says so rather than being left to imply otherwise.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CLI_SRC = REPO / "packages/truestill-cli/src"
APP_SRC = REPO / "packages/truestill-app/src"


def _core_imports(root: Path) -> set[str]:
    """Names this surface imports from ``truestill_core`` - its half of the shared contract."""
    names: set[str] = set()
    for file in root.rglob("*.py"):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "truestill_core"
            ):
                names |= {alias.name for alias in node.names}
    return names


def _row_field_arguments(root: Path, wanted: set[str]) -> dict[str, set[str]]:
    """Per shared symbol, the catalog-row field expressions passed to it.

    Restricted to subscripts of a string constant - ``row["copy_sha256"]`` and the shapes built
    around it. That is where a dual-hash-style rule gets written down at a call site, and
    excluding everything else is what keeps the false-positive count at zero.
    """
    found: dict[str, set[str]] = defaultdict(set)
    for file in root.rglob("*.py"):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name not in wanted:
                continue
            values = [ast.dump(a, annotate_fields=False) for a in node.args]
            values += [ast.dump(k.value, annotate_fields=False) for k in node.keywords]
            found[name] |= {v for v in values if "Subscript" in v and "Constant(" in v}
    return found


def _divergent() -> dict[str, set[str]]:
    """Shared symbols whose row-field arguments differ between the two surfaces."""
    shared = _core_imports(CLI_SRC) & _core_imports(APP_SRC)
    cli, app = _row_field_arguments(CLI_SRC, shared), _row_field_arguments(APP_SRC, shared)
    # Only where BOTH surfaces pass row fields: a symbol one surface calls with a row and the
    # other with locals is a different usage, not a drifted copy of one rule.
    return {
        name: cli[name] ^ app[name]
        for name in shared
        if cli[name] and app[name] and cli[name] ^ app[name]
    }


def test_the_two_surfaces_have_not_drifted_on_a_shared_contract() -> None:
    divergent = _divergent()
    assert not divergent, (
        "a rule written at a call site on one surface but not its twin - a repair that reached "
        "one copy and not the other:\n"
        + "\n".join(f"  {name}: {sorted(exprs)}" for name, exprs in sorted(divergent.items()))
        + "\n\nThe remedy is usually a shared home rather than a second copy of the rule; see "
        "ENGINEERING_STANDARD.md §4."
    )


def test_the_guard_can_still_resolve_the_two_surfaces() -> None:
    """The scope must stay resolvable: 62 shared core symbols today, and it must not collapse.

    This asserts the guard can still *see* both surfaces - that the paths are right and the
    imports still parse. It deliberately does **not** claim the compared population is non-empty:
    since ``from_row``, no symbol is called with row fields on both sides, and that is the goal
    state rather than a fault. What proves the mechanism can still fire is the planted test
    below, which supplies its own sources and so cannot go vacuous with the tree.
    """
    shared = _core_imports(CLI_SRC) & _core_imports(APP_SRC)
    assert len(shared) > 20, f"only {len(shared)} shared core symbols; is the scope still right?"


def test_the_row_mapping_has_exactly_one_home() -> None:
    """The copy stays deleted: no surface may rebuild a ``CopyToVerify`` from raw row fields.

    ``_divergent`` cannot catch a mapping re-inlined *identically* on both surfaces - by its own
    docstring it sees repairs that land on one copy, never a shared contract that is wrong. That
    is precisely the state the codebase was in before ``cli.py:513`` was found. So the thing
    actually worth pinning is not that the two copies agree, but that there is only one.
    """
    inlined: dict[str, set[str]] = {}
    for surface, root in (("cli", CLI_SRC), ("app", APP_SRC)):
        exprs = _row_field_arguments(root, {"CopyToVerify"})["CopyToVerify"]
        if exprs:
            inlined[surface] = exprs
    assert not inlined, (
        "a catalog row is being unpacked into CopyToVerify at a call site again:\n"
        + "\n".join(f"  {name}: {sorted(exprs)}" for name, exprs in sorted(inlined.items()))
        + "\n\nUse CopyToVerify.from_row(row) - the mapping has one home so a correction to it "
        "cannot reach one surface and miss the other."
    )


def test_the_guard_sees_a_planted_divergence(tmp_path: Path) -> None:
    """Both halves: it must catch the real shape and stay silent on legitimate difference.

    The caught case is `cli.py:513`'s literally: one surface keeps ``or row["sha256"]``. The
    spared case is the CLI's extra ``pool``/``workers`` knobs, which are a real difference in
    what the two surfaces offer and must never be reported as drift.
    """
    drifted = tmp_path / "cli_like"
    twin = tmp_path / "app_like"
    for directory in (drifted, twin):
        directory.mkdir()
    (drifted / "a.py").write_text(
        "from truestill_core.verify import CopyToVerify\n"
        'CopyToVerify(r["sha256"], r["relative"], r["copy_sha256"] or r["sha256"])\n',
        encoding="utf-8",
    )
    (twin / "b.py").write_text(
        "from truestill_core.verify import CopyToVerify\n"
        'CopyToVerify(r["sha256"], r["relative"], r["copy_sha256"])\n',
        encoding="utf-8",
    )
    shared = _core_imports(drifted) & _core_imports(twin)
    left, right = _row_field_arguments(drifted, shared), _row_field_arguments(twin, shared)
    assert left["CopyToVerify"] ^ right["CopyToVerify"], "the guard missed the real defect shape"

    # Cry-wolf half: an extra keyword that is not a row field is not drift.
    (drifted / "a.py").write_text(
        "from truestill_core.verify import CopyToVerify\n"
        'CopyToVerify(r["sha256"], r["relative"], r["copy_sha256"], pool="thread", workers=4)\n',
        encoding="utf-8",
    )
    left = _row_field_arguments(drifted, shared)
    assert not (left["CopyToVerify"] ^ right["CopyToVerify"]), "flagged a legitimate difference"
