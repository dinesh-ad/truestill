"""A command the product tells you to run must work when you copy it. `(aij)`.

**The defect.** `backup` onto an unregistered folder refuses - correctly - and offered
`truestill drives --init <path>`. Running exactly that answers `error: --init requires --label`.
The refusal was right and its remedy was wrong, so a user who copied the line the product printed
got a second error from the command the product chose for them.

⚠ **This guard exists because a SECOND instance was found, and `(aij)`'s body set that as the
condition.** It recorded: *"A guard is buildable and NOT decided: one instance is not yet the
evidence `(ago)` requires, so this is recorded so a second is recognised as the second."*
`drive.py`'s second-location note suggested `truestill drives --init <other> --force-new-identity`
- also without `--label`, and `cli._cmd_drives` has no exemption for `--force-new-identity`. Two
instances of one shape is the evidence that ruling asked for.

⚠ **Scoped to `drives --init`, deliberately, and the wider guard is REFUSED with a measurement.**
The obvious version - extract every `truestill …` string in the tree and assert the parser accepts
it - was prototyped and produced **33 "failures" out of 36** on a clean tree, almost all of them
prose: comments reading *"`truestill verify` takes"*, docstrings naming a command mid-sentence,
and f-strings whose placeholder arguments cannot be filled. **Separating "a command to run" from
"a sentence mentioning a command" is not a regex or a parser job**, and a guard that cries wolf 33
times is one somebody switches off - `ENGINEERING_STANDARD.md` §4's standing argument. So this
asserts the one shape whose failure mode is proven, and says why it stops there.

⚠ **And it must not use the argument parser.** `--init requires --label` is a **runtime** check in
`cli._cmd_drives`, not a parser rule: `parse_args` accepts `drives --init X` happily. A guard
built on the parser would pass while the defect stood.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

#: The subcommand whose suggestions this guard checks, and the flag its runtime demands.
SUGGESTION = "drives --init"
REQUIRED = "--label"


def _source_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "packages/*/src/**/*.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = [REPO / line for line in out.splitlines() if line]
    assert files, (
        "`git ls-files packages/*/src/**/*.py` matched nothing, so this guard has no subject "
        "and would report zero bad suggestions over zero files. See ENGINEERING_STANDARD.md 4, "
        "the fifty-second member: zero violations over zero files is the same green as zero "
        "over a clean tree."
    )
    return files


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Every docstring expression, by identity, so prose about a command is not a suggestion."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            if ast.get_docstring(node, clean=False) is None:
                continue
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr):
                found.add(id(first.value))
    return found


def _suggestions(path: Path) -> list[tuple[int, str]]:
    """`(line, text)` for every non-docstring literal that tells a user to run the subcommand.

    Comments are invisible to `ast` and docstrings are excluded by identity, which together are
    what keep prose out - the distinction the wider guard could not make.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docs = _docstring_nodes(tree)

    # ⚠ **A JoinedStr's own fragments must not be judged separately.** `ast.walk` visits an
    # f-string AND each `Constant` inside it, so a message split across adjacent literals -
    # `f"... register it: " f"truestill drives --init {p} --label <name>"` - offers a fragment
    # holding the subcommand and not the flag. Judging that fragment fails a message that is
    # correct as printed. Caught by this guard failing on its own fix.
    inner: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for part in ast.walk(node):
                if part is not node:
                    inner.add(id(part))

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if id(node) in docs or id(node) in inner:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        elif isinstance(node, ast.JoinedStr):
            text = "".join(
                part.value
                for part in node.values
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
        else:
            continue
        if SUGGESTION in text:
            found.append((node.lineno, text))
    return found


def test_every_suggested_drives_init_carries_the_flag_it_needs() -> None:
    """The gate. A suggestion the runtime would refuse is a promise the product cannot keep."""
    offenders: list[str] = []
    checked = 0
    for path in _source_files():
        for line, text in _suggestions(path):
            checked += 1
            if REQUIRED not in text:
                offenders.append(f"{path.relative_to(REPO).as_posix()}:{line}")

    assert checked, (
        "no `drives --init` suggestion was found anywhere, so this guard is vacuous - the "
        "wording moved and the guard did not follow it"
    )
    assert not offenders, (
        "these suggest `truestill drives --init` without `--label`, which "
        "`cli._cmd_drives` refuses at runtime with `error: --init requires --label`:\n  "
        + "\n  ".join(offenders)
    )
