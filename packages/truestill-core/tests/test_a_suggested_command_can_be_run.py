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

⚠ **THE WIDER GUARD WAS REFUSED WITH A MEASUREMENT AND IS NOW BUILT, BECAUSE THE MEASUREMENT WAS
TAKEN AGAINST A WEAKER FILTER.** The refusal recorded here read: *"extract every `truestill …`
string in the tree and assert the parser accepts it - was prototyped and produced 33 'failures'
out of 36 on a clean tree, almost all of them prose."* That was true of a bare `truestill <word>`
sweep. Two filters the prototype did not have cut it to nothing (measured 2026-09-16, `(akz)`):

* **The word after the name must be a real subcommand, asked of the parser.** `truestill is free
  to use`, `truestill will not extract`, `truestill does not start a run` and eighteen more die
  here, because `is`, `will` and `does` are not subcommands. **23 of 60 lines.**
* **A quoted or backticked command is a REFERENCE, not an instruction.** `Run 'truestill rescan'
  to list...` names a command inside a sentence; it is not a line anyone copies. The same
  principle `check_product_name` rule 1 already applies - *"anything a reader sees as code is an
  identifier by presentation"*. **10 more.**

That leaves 27, of which three were still prose because of **where the command ends**, not where
it begins - `tell truestill where it went` (`where` IS a subcommand), and two lines with a command
followed by an explanatory tail. :data:`OFFER` answers that with the product's own typography:
**a suggestion starts at a line start or after a colon, and ends at the end of the line or at the
next run of two or more spaces** - which is how this codebase already lays out
`Reversible:   truestill undo-organize  restores every file...`.

**Result on the tree this landed against: 25 suggestions, 0 false positives, 2 real defects** -
`analyze` offering `truestill organize <folder> --destination <folder>` when `destination` is
positional, and `backup`'s eject note offering a bare `truestill verify` when `path` is required.
The second is shipped to the **browser** as well, through `service/backup.py`'s `eject_note`.

⚠ **AND THE PARSER IS NOW THE RIGHT ORACLE, WHICH IT WAS NOT FOR THE ORIGINAL CASE.** This file's
first rule could not use it: `--init requires --label` is a **runtime** check in `cli._cmd_drives`
and `parse_args` accepts `drives --init X` happily. Both defects found by the wider rule are
parser-level, so both tests stay - one asks the runtime's question, one asks the parser's, and
neither can answer the other's.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import functools
import io
import re
from pathlib import Path

from truestill_cli import cli

import repo_sources

REPO = Path(__file__).resolve().parents[3]

#: The subcommand whose suggestions this guard checks, and the flag its runtime demands.
SUGGESTION = "drives --init"
REQUIRED = "--label"


def _source_files() -> list[Path]:
    files = repo_sources.files("packages/*/src/**/*.py")
    assert files, (
        "`repo_sources.files('packages/*/src/**/*.py')` matched nothing, so this guard has no subject "
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


# ---------------------------------------------------------------- the wider rule, `(akz)`

#: Where a suggestion starts and where it ends, in the product's own typography.
#:
#: **Start**: the beginning of a line, or after a colon and whitespace. **End**: the end of the
#: line, or the next run of two or more spaces. Both halves were needed - see the module
#: docstring for the three lines that survived the first half and not the second.
#:
#: ⚠ **The subcommand list is the PARSER's, never a literal here**, which is the same rule
#: `test_subcommand_list_mirrors_the_parser` exists for one file over. It is also the filter that
#: does most of the work: without it `truestill is free to use` is a suggestion.
_OFFER_TEMPLATE = r"(?:^|:\s)\s*(truestill (?:{subcommands})\b[^\n]*?)(?:\s{{2,}}|$)"

#: A placeholder stands for a path the user fills in. `<...>` first, so `<the drive's folder>` is
#: one token rather than three - an apostrophe inside one also defeats `shlex`, which is why this
#: does not use it.
_ANGLE = re.compile(r"<[^>]*>")
_FILLED = "PLACEHOLDER"
_WORDS = frozenset({"{}", _FILLED, "FOLDER", "DESTINATION", "PATH", "ID", "ROOT", "N"})


@functools.cache
def _parser() -> argparse.ArgumentParser:
    """One parser for the whole file.

    ⚠ **Measured, and this is why it is cached.** `_build_parser` declares 23 subparsers and
    every flag on each; rebuilding it per suggestion took this file from milliseconds to
    **60 s**, against `make check`'s 90 s ceiling for the entire suite. The parser is only ever
    read here, and `parse_args` does not mutate it.
    """
    return cli._build_parser()


@functools.cache
def _pattern() -> re.Pattern[str]:
    return re.compile(_OFFER_TEMPLATE.format(subcommands="|".join(_subcommands())))


@functools.cache
def _subcommands() -> tuple[str, ...]:
    groups = [a for a in _parser()._actions if isinstance(a, argparse._SubParsersAction)]
    assert groups, "the CLI parser has no subparsers; this guard is reading the wrong object"
    # Longest first: `undo-organize` must not be matched as `undo` by an alternation.
    return tuple(sorted(groups[0].choices, key=len, reverse=True))


def _offers(text: str) -> list[str]:
    return [m.group(1).strip() for line in text.splitlines() for m in _pattern().finditer(line)]


def _argv(command: str) -> list[str]:
    """The suggestion as a shell would hand it to argparse, placeholders filled with a path."""
    words = _ANGLE.sub(_FILLED, command).split()[1:]
    return ["/tmp/placeholder" if word in _WORDS else word for word in words]


def _refused(command: str) -> str:
    """argparse's own complaint, or ``""`` when it accepts the suggestion.

    ⚠ **`parse_args` NEVER RUNS THE COMMAND.** It builds a namespace and returns; no handler is
    reached, nothing is read and nothing is written. That is what makes asking the real parser
    about a real path safe here, and it is why the oracle is the parser rather than a subprocess.
    """
    said = io.StringIO()
    try:
        with contextlib.redirect_stderr(said), contextlib.redirect_stdout(said):
            _parser().parse_args(_argv(command))
    except SystemExit:
        return (said.getvalue().strip().splitlines() or ["(no message)"])[-1]
    return ""


def _all_offers() -> list[tuple[Path, int, str]]:
    found: list[tuple[Path, int, str]] = []
    for path in _source_files():
        # ⚠ **A SOURCE FILE CAN VANISH BETWEEN THE LISTING AND THE READ, and it does.**
        # `test_a_census_sees_the_file_being_added` writes `_census_probe.py` into
        # `truestill-core/src` and removes it again; under `-n auto` this guard listed it and
        # then failed to open it. Skipped rather than fatal: a file that is gone offers nothing,
        # and turning another test's fixture into this one's red run is a flake, not a finding.
        try:
            source = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        tree = ast.parse(source, filename=str(path))
        docs = _docstring_nodes(tree)
        inner: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                for part in ast.walk(node):
                    if part is not node:
                        inner.add(id(part))
        for node in ast.walk(tree):
            if id(node) in docs or id(node) in inner:
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            elif isinstance(node, ast.JoinedStr):
                # An f-string's interpolations become `{}`, which `_argv` fills like any other
                # placeholder - the value is a path at run time and its shape cannot change
                # whether argparse accepts the line.
                text = "".join(
                    part.value
                    if isinstance(part, ast.Constant) and isinstance(part.value, str)
                    else "{}"
                    for part in node.values
                )
            else:
                continue
            found.extend((path, node.lineno, offer) for offer in _offers(text))
    return found


def test_the_guard_has_suggestions_to_judge() -> None:
    """Anti-vacuity, and the floor is a MEASUREMENT rather than a round number.

    25 offers stood on the tree this landed against. The floor is 15: comfortably under, and
    loud if the extraction rule stops matching the product's typography - which is the way this
    guard dies quietly, since a regex that matches nothing reports a clean tree.
    """
    offers = _all_offers()
    assert len(offers) >= 15, (
        f"only {len(offers)} suggestions found; is the extraction still right?"
    )
    assert any("rescan" in offer for _, _, offer in offers), "the rescan suggestions vanished"


def test_the_oracle_can_say_no() -> None:
    """⚠ **Written because a mutation survived: `_refused` returning `""` always passed the gate.**

    A check whose failure branch is unreachable is a green run against anything, and the gate
    below cannot tell that from a clean tree. Both shapes the real defects had are asserted - a
    flag that does not exist, and a required positional that is missing.
    """
    assert "--destination" in _refused("truestill organize <folder> --destination <folder>")
    assert "required" in _refused("truestill verify")
    assert _refused("truestill organize <folder> <destination>") == ""


def test_every_command_the_product_suggests_is_one_the_parser_accepts() -> None:
    """The gate. A printed command that exits 2 is the product's own advice failing.

    ⚠ **Found two on a green tree**, and the more embarrassing one was reached from the first
    screen: `analyze` ended with `truestill organize <folder> --destination <folder>`, and
    `destination` is positional.
    """
    offenders = [
        f"{path.relative_to(REPO).as_posix()}:{line}\n      suggests: {offer}\n      argparse: {said}"
        for path, line, offer in _all_offers()
        if (said := _refused(offer))
    ]
    assert not offenders, (
        "the product prints these, and argparse refuses them - a user who copies one gets a "
        "second error from a command the product chose for them:\n  " + "\n  ".join(offenders)
    )


def test_prose_that_merely_names_a_command_is_not_judged() -> None:
    """The cry-wolf half, and the reason the 2026-08-19 refusal was right about its own filter.

    Every line here appears in the tree today and none is an instruction. A guard that failed on
    any of them would be switched off within a week, taking its real coverage with it - which is
    exactly what the wider prototype's 33-of-36 measured.
    """
    prose = [
        "truestill is free to use and every feature works.",
        "Nothing has moved - truestill does not start a run it cannot finish.",
        "{} is an absolute path, which truestill will not extract",
        "Run 'truestill rescan' to list anything on the drive the catalog does not know about.",
        "Run `truestill rescan` on the drive to correct its records.",
        "after moving the folder photos were imported from, tell truestill where it went",
        "Re-check: connect '{}', then run truestill verify on its folder.",
    ]
    for line in prose:
        assert _offers(line) == [], f"prose was read as a suggestion: {line!r}"


def test_a_command_followed_by_prose_is_cut_at_the_column() -> None:
    """The half the subcommand filter could not do, pinned on the shape that needed it.

    `Reversible:   truestill undo-organize  restores every file to where it is now` lays the
    explanation out in a column. Without the two-space rule the tail is argv and the line fails.
    """
    assert _offers(
        "  Reversible:   truestill undo-organize  restores every file to where it is now"
    ) == ["truestill undo-organize"]
    assert _offers("      truestill organize <folder> <destination>") == [
        "truestill organize <folder> <destination>"
    ]
