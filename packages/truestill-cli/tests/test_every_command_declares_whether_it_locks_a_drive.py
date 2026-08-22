"""Every subcommand says whether it holds its drive, and none of them defaults. `(aaw)`

⚠ **Neither default is safe, which is why there is no default.** Unlocked would mean the next
mutating command added silently skips the cross-process lock - the defect `(aaw)` measured, back
again and quieter. Locked would mean a read-only command starts refusing with nobody deciding.

**Not derived from the command name, and not from a string.** A control derived from `"organize"`
vs `"organize preview"` is one rename away from a lock that stops firing.
"""

from __future__ import annotations

import ast
from pathlib import Path

from truestill_cli.cli import _LOCKED_IN_HANDLER, _LOCKS_DRIVE_AT

_CLI = Path(__file__).resolve().parents[1] / "src/truestill_cli/cli.py"


def _dispatch_commands() -> set[str]:
    """The dispatch table's keys, read from the source so the two cannot drift."""
    tree = ast.parse(_CLI.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "dispatch":
            assert isinstance(node.value, ast.Dict)
            return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    missing = "no `dispatch` table found in cli.py"
    raise AssertionError(missing)


def test_every_command_declares_whether_it_locks_a_drive() -> None:
    """⚠ **The guard the ruling asked for: a new command that declares nothing FAILS.**"""
    commands = _dispatch_commands()

    undeclared = commands - set(_LOCKS_DRIVE_AT)
    assert not undeclared, (
        f"these subcommands do not say whether they lock a drive: {sorted(undeclared)}. "
        "Add each to `_LOCKS_DRIVE_AT` - `None` if it writes no files on a drive, otherwise the "
        "`args` attribute naming the drive. There is deliberately no default: unlocked would "
        "silently skip the lock, locked would refuse a read-only command."
    )
    stale = set(_LOCKS_DRIVE_AT) - commands
    assert not stale, f"these declarations name no subcommand: {sorted(stale)}"


def test_the_declared_attribute_is_one_the_parser_actually_produces() -> None:
    """A declaration naming an attribute that does not exist is a lock that raises, not one that
    holds - and it would only be found by the user who ran that command."""
    source = _CLI.read_text(encoding="utf-8")
    for command, where in _LOCKS_DRIVE_AT.items():
        if where is None or where == _LOCKED_IN_HANDLER:
            continue
        assert f'"{where}"' in source, (
            f"{command!r} says its drive is `args.{where}`, which no parser argument produces"
        )


def test_the_in_handler_command_actually_takes_the_lock() -> None:
    """`undo-organize` declares that it locks itself. This is what holds it to that.

    Its drive comes out of the run's record rather than from `args`, so `_run_holding_the_drive`
    cannot take it - and a declaration nothing enforces is how the lock quietly stops being taken.
    """
    in_handler = [c for c, w in _LOCKS_DRIVE_AT.items() if w == _LOCKED_IN_HANDLER]
    assert in_handler == ["undo-organize"], (
        "a new command claims it locks itself; this test names them one by one on purpose"
    )
    tree = ast.parse(_CLI.read_text(encoding="utf-8"))
    handler = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_cmd_undo_organize"
    )
    calls = {
        node.func.id
        for node in ast.walk(handler)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "lock_for" in calls, (
        "_cmd_undo_organize declares `_LOCKED_IN_HANDLER` and never calls `lock_for`"
    )
