"""Every `CategoryMatch(rule=...)` written as a literal must name a real `RuleName`.

**The defect this closes.** Six fixtures passed `rule="d"` and `rule="test"` - strings that are
not members of `RuleName`. `RuleName` is a `StrEnum`, so nothing objected: not the dataclass, not
the runtime, and not mypy. `organizer.py:734` and `:797` gate on ``category.rule in
TIMELINE_RULES``, so each of those fixtures silently pinned its test to the branch it was not
about. Measured before repair: substituting the real member changed no outcome in any of the six,
so nothing was hiding behind them yet - a latent wrong, not a live one.

⚠ **THE TYPE ANNOTATION DOES NOT CLOSE THIS, and that is checked rather than assumed.**
`CategoryMatch.rule` is already annotated `RuleName`. mypy accepts a bare string literal against a
`StrEnum`-typed parameter without checking membership (python/mypy#14230), and the two obvious
repairs are both dead ends: `Literal[RuleName.DEVICE]` is rejected as *"not valid as a type"*
(python/typing#18), and `Literal["device", ...]` reintroduces the raw strings this is about.

**So the control is a census, and the reasons are cost and location.** A runtime check in
`CategoryMatch.__post_init__` would run once per organized file - the hot path - to guard a
mistake that has never appeared in shipped code: measured over the tree, every `rule` argument in
`packages/*/src/` is a `RuleName` member, and all six defects were literals in test fixtures. A
census pays nothing at runtime and looks exactly where the defect lives. It is also the house
pattern - `test_every_command_declares_whether_it_locks_a_drive.py` and
`test_patch_targets_stay_aimed.py` both read the tree with `ast` rather than importing it.

**What it cannot see, stated rather than implied.** A rule passed as a variable, an f-string or a
value read at runtime is invisible here: only literals are resolvable without executing anything.
Measured on the tree this landed against, that leaves **28** literal sites checked and **15**
already written as `RuleName.MEMBER`, which need no checking. A fixture that computes its rule
would slip through, and the answer to that is to write the member.

**Cost.** One `ast.parse` of each tracked `.py` file, **543** today: linear in files and in their
bytes, no second pass, well under a second.
"""

from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path

from truestill_core.models import RuleName

ROOT = Path(__file__).resolve().parents[3]

#: The constructor whose fourth argument is a rule. Named rather than imported: this reads source,
#: and a call is spelled the same whether or not the name resolves to the real class.
CONSTRUCTOR = "CategoryMatch"

#: `CategoryMatch(label, reason, confidence, rule)` - the position a bare fourth argument takes.
RULE_POSITION = 3


@dataclass(frozen=True)
class RuleLiteral:
    """One place a rule is written as a plain string, and what it says there."""

    where: str
    value: str


def _tracked_python() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return out.stdout.split()


def _rule_argument(call: ast.Call) -> ast.expr | None:
    """The `rule` argument of a `CategoryMatch` call, by keyword or by position."""
    for keyword in call.keywords:
        if keyword.arg == "rule":
            return keyword.value
    if len(call.args) > RULE_POSITION:
        return call.args[RULE_POSITION]
    return None


def rule_literals() -> list[RuleLiteral]:
    """Every rule written as a string literal, across the tracked tree. Pure over the files."""
    found: list[RuleLiteral] = []
    for name in _tracked_python():
        try:
            tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a file that does not parse is ruff's question
            continue
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == CONSTRUCTOR
            ):
                continue
            argument = _rule_argument(node)
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                found.append(RuleLiteral(f"{name}:{node.lineno}", argument.value))
    return found


def strangers(literals: list[RuleLiteral]) -> list[str]:
    """The literals that name no `RuleName` member. Pure: the census goes in as an argument."""
    real = {member.value for member in RuleName}
    return [f"{item.where}  rule={item.value!r}" for item in literals if item.value not in real]


def test_no_rule_is_written_as_a_string_that_names_nothing() -> None:
    wrong = strangers(rule_literals())
    assert not wrong, (
        "a rule is written as a string that is not a RuleName member:\n  "
        + "\n  ".join(wrong)
        + f"\n\nThe members are {sorted(m.value for m in RuleName)}. Prefer `RuleName.DEVICE` "
        'over `"device"`: a typo in the member is an AttributeError at import, while a typo '
        "in the string is silent - `StrEnum` accepts it and mypy does not check membership."
    )


def test_the_census_has_something_to_read() -> None:
    """Anti-vacuity: a walk that parses nothing makes the assertion above true.

    **Measured on the tree this landed against**: 543 tracked `.py` files, **28** literal rules.
    The floors are `> 300` files and `> 15` literals - clear of today's numbers, and loud if
    `git ls-files` stopped answering or the constructor were renamed out from under this file,
    which are the two ways it goes quietly vacuous.
    """
    assert len(_tracked_python()) > 300, "git ls-files returned almost nothing"
    literals = rule_literals()
    assert len(literals) > 15, f"only {len(literals)} literal rules found; is {CONSTRUCTOR} named?"


def test_it_catches_a_planted_stranger_and_leaves_real_members_alone() -> None:
    """Both directions, without touching the tree.

    The cry-wolf half matters as much as the other: every real member must pass, or the guard
    fires on correct code the day someone adds a rule.
    """
    planted = [RuleLiteral("somewhere.py:1", "d"), RuleLiteral("elsewhere.py:2", "test")]
    assert len(strangers(planted)) == 2, "a string naming no rule was not caught"

    every_real = [RuleLiteral(f"f.py:{i}", m.value) for i, m in enumerate(RuleName)]
    assert strangers(every_real) == [], "the guard fired on genuine RuleName members"
