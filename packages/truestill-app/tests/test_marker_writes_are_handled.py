"""(aek) Every site that mints a drive marker must handle the drive refusing it.

**Why a guard rather than a note.** `write_marker` never raises - it returns a `MarkerWrite`, the
contract `decisions.write_decisions` has had all along. `create_marker` and `upgrade_marker` are
the other end, for callers that cannot continue without an identity, and they raise
`DriveWriteError`. That end is where `(aek)` can come back: a **sixth** call site that forgets to
catch is a traceback again, which is the exact defect this closes.

`ENGINEERING_STANDARD.md` §4's twenty-seventh member rules that *"a rule that depends on somebody
remembering to read it is not a control"*, and names the third instance - a rule with the best
placement available, broken anyway, because consulting it was voluntary. So this reads the live
source tree: a call site added tomorrow is covered the day it is added, not the day someone
remembers this file exists.

**The subject is proved non-empty first** (§4, fifty-second member). Zero violations over a corpus
this guard failed to find is the same green as zero violations over a clean one, and a guard that
can pass on an empty scan is worth nothing.
"""

from __future__ import annotations

import ast
from pathlib import Path

#: The functions that mint or rewrite a marker, and therefore can raise `DriveWriteError`.
_RAISING_CALLS = frozenset({"create_marker", "upgrade_marker"})

#: Handling means catching this, or something it derives from.
_HANDLERS = frozenset({"DriveWriteError", "Exception", "BaseException"})

_REPO = Path(__file__).resolve().parents[3]
_SOURCE_ROOTS = (
    _REPO / "packages" / "truestill-core" / "src",
    _REPO / "packages" / "truestill-cli" / "src",
    _REPO / "packages" / "truestill-app" / "src",
)


#: A function may also PROPAGATE, if it says so. Handling and declaring are the two acceptable
#: answers; the third - not having thought about it - is what `(aek)` was.
_DECLARES = ":raises DriveWriteError:"


class _Visitor(ast.NodeVisitor):
    """Record every mint call, and whether the refusal is handled or declared.

    **Two acceptable answers, because propagating is legitimate and silence is not.**
    `cli._register_destination` deliberately lets the refusal reach `_registered_or_refused`, which
    turns it into exit 4 - a lexical-`try` rule alone would flag that and push the handler down to
    where it reads worse. So a call is covered when it sits inside a `try` that catches, **or**
    when its enclosing function documents `:raises DriveWriteError:`.

    That keeps the check mechanical while making propagation a decision somebody wrote down, which
    is the whole point: the defect was never a missing `try`, it was nobody asking the question.

    Handler depth is tracked rather than matched textually, and is deliberately generous about
    *which* `try` - a handler two frames up is still a handler - and strict about there being one.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.unhandled: list[tuple[str, int]] = []
        self.found: list[tuple[str, int]] = []
        self._covered = 0

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        declares = _DECLARES in (ast.get_docstring(node) or "")
        self._covered += 1 if declares else 0
        self.generic_visit(node)
        self._covered -= 1 if declares else 0

    visit_FunctionDef = _visit_function  # noqa: N815 - ast visitor naming
    visit_AsyncFunctionDef = _visit_function  # noqa: N815 - ast visitor naming

    def visit_Try(self, node: ast.Try) -> None:
        covers = any(self._catches(handler) for handler in node.handlers)
        self._covered += 1 if covers else 0
        for child in node.body:
            self.visit(child)
        self._covered -= 1 if covers else 0
        for other in (*node.handlers, *node.orelse, *node.finalbody):
            self.visit(other)

    @staticmethod
    def _catches(handler: ast.ExceptHandler) -> bool:
        names = handler.type
        if names is None:  # a bare `except:` catches everything, including this
            return True
        candidates = names.elts if isinstance(names, ast.Tuple) else [names]
        return any(
            isinstance(entry, ast.Name) and entry.id in _HANDLERS for entry in candidates
        ) or any(
            isinstance(entry, ast.Attribute) and entry.attr in _HANDLERS for entry in candidates
        )

    def visit_Call(self, node: ast.Call) -> None:
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if name in _RAISING_CALLS:
            self.found.append((name or "", node.lineno))
            if not self._covered:
                self.unhandled.append((name or "", node.lineno))
        self.generic_visit(node)


def _scan() -> tuple[list[str], list[str]]:
    found: list[str] = []
    unhandled: list[str] = []
    for root in _SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            visitor = _Visitor(path)
            visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
            rel = path.relative_to(_REPO).as_posix()
            found.extend(f"{rel}:{line} {name}" for name, line in visitor.found)
            unhandled.extend(f"{rel}:{line} {name}" for name, line in visitor.unhandled)
    return found, unhandled


def test_the_scan_actually_finds_the_mint_sites() -> None:
    """Non-emptiness first: a guard aimed at nothing reports the same green as a clean tree.

    `drive.py` itself is deliberately excluded from the requirement below - it *defines* these -
    but it still contains calls, so the corpus can never legitimately be empty.
    """
    found, _ = _scan()

    assert found, "no create_marker/upgrade_marker call found; the scan is aimed at nothing"
    assert len(found) >= 4, f"expected the known mint sites, found only: {found}"


def test_every_mint_site_handles_a_drive_that_refuses_the_marker() -> None:
    """The rule itself. `write_marker` never raises; these two do, and every caller answers for it.

    A failure here is not a style complaint - it is `(aek)` returning: an unhandled
    `DriveWriteError` reaches the user as a traceback on the CLI, and as a bare errno in the app.
    """
    _, unhandled = _scan()
    # `drive.py` owns the raise; `_write_marker_or_raise` is where it comes from.
    offenders = [site for site in unhandled if "truestill_core/drive.py" not in site]

    assert not offenders, (
        "these mint a drive marker without handling DriveWriteError, so a read-only or full "
        f"drive reaches the user as a traceback: {offenders}"
    )
