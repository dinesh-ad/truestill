"""Bare `truestill` answers with a first screen, and every command on it is real. `(akx)`

⚠ **WHAT THIS REPLACED.** The first thing a new user met was argparse's *"the following
arguments are required: command"*, printed above 23 subcommands wrapped onto one line - a list of
what may be typed that says nothing about what to type, while `README.md` has always said *"Start
with `analyze`"*.

**The assertion with teeth is not that the screen exists.** A first screen is a promise made in
prose, and prose is where this repo's defects live: a screen that recommended a command that had
been renamed, or described one that does something else now, would read perfectly and be a lie.
So every invocation on the screen is taken apart and **run** - the verb against the parser, the
example against a real folder - rather than reviewed.

Kept out of `test_cli.py` deliberately: this is the one file that has to fail when somebody
rewords the screen without re-checking it, and that is easier to see when it is the whole file.
"""

from __future__ import annotations

import argparse
import shutil
import tomllib
from pathlib import Path

import pytest
from truestill_cli import cli
from truestill_cli.cli import (
    FIRST_SCREEN_APP,
    FIRST_SCREEN_LEAD,
    FIRST_SCREEN_STEPS,
    NO_COMMAND_EXIT,
    first_screen,
    main,
)

REPO = Path(__file__).resolve().parents[3]


def _subcommands() -> set[str]:
    """Every subcommand argparse knows about, read from the parser - never a list here.

    The same derivation `test_subcommand_list_mirrors_the_parser` uses, for the same reason: a
    hand-kept mirror of the parser is a list nobody prunes.
    """
    groups = [a for a in cli._build_parser()._actions if isinstance(a, argparse._SubParsersAction)]
    assert groups, "the CLI parser has no subparsers; this guard is reading the wrong object"
    return set(groups[0].choices)


# ------------------------------------------------------------------ what a bare invocation does


def test_a_bare_invocation_prints_the_screen_to_stdout_and_says_nothing_on_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """stdout, because it is what the person asked to see and not a complaint about their typing.

    Measured 2026-09-16: bare `git` and `npm` both put their concise help on stdout. The
    stderr assertion is the half with teeth - argparse's usage error went there, and a screen
    that merely joined it would still be invisible to `truestill > first-screen.txt`.
    """
    code = main([])
    captured = capsys.readouterr()

    assert code == NO_COMMAND_EXIT
    assert captured.err == ""
    assert captured.out.strip() == first_screen().strip()


def test_the_exit_code_is_still_non_zero_so_a_script_is_not_told_it_succeeded() -> None:
    """A script that ran the command with no arguments has done nothing.

    Pinned as a value rather than a spelling: `truestill && echo done` must not print `done`,
    whatever code is chosen. `0` here would be the quiet kind of wrong.
    """
    assert NO_COMMAND_EXIT != 0


def test_every_other_argparse_path_is_untouched(capsys: pytest.CaptureFixture[str]) -> None:
    """The gate is `if not argv_list`, and this is what says so.

    A first screen implemented by making the subparsers optional would swallow a **mistyped**
    command into the same friendly page - which is the failure mode worth guarding, because it
    turns a typo into silence.
    """
    with pytest.raises(SystemExit) as version:
        main(["--version"])
    assert version.value.code == 0
    assert "truestill" in capsys.readouterr().out

    with pytest.raises(SystemExit) as typo:
        main(["organzie"])
    assert typo.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_the_screen_fits_a_narrow_terminal() -> None:
    """80 columns, because the machine a new user is sitting at is the one that wraps.

    The descriptions are on their own lines rather than in an aligned column for exactly this:
    the widest invocation is 44 characters, and a column would have left 32 for the sentence.
    """
    widest = max(len(line) for line in first_screen().splitlines())
    assert widest <= 80, f"the first screen is {widest} columns wide"


# ------------------------------------------------------- every command it names, proved to exist


def test_every_invocation_on_the_screen_names_a_real_subcommand() -> None:
    """The verb after the program name is a subcommand the parser has.

    ⚠ **This is the assertion that catches a RENAME**, which is the way a first screen goes
    wrong without anybody touching it: `analyze` becoming `scan` would leave this text reading
    perfectly and recommending a command that no longer answers.
    """
    known = _subcommands()
    for invocation, _ in FIRST_SCREEN_STEPS:
        program, verb, *_ = invocation.split()
        assert program == "truestill", invocation
        assert verb in known, f"{verb!r} is on the first screen and is not a subcommand"


def test_the_screen_names_the_app_by_the_entry_point_that_installs_it() -> None:
    """`truestill-app` is a second executable, not a subcommand, so the parser cannot vouch for it.

    Its `[project.scripts]` entry can, and that is what an install actually puts on `PATH` - so
    this reads the same declaration the packaging does rather than trusting the sentence.
    """
    manifest = tomllib.loads(
        (REPO / "packages/truestill-app/pyproject.toml").read_text(encoding="utf-8")
    )
    scripts = manifest["project"]["scripts"]
    assert "truestill-app" in scripts, "the screen offers a command the app does not install"
    assert "truestill-app" in FIRST_SCREEN_APP


def test_the_command_count_is_the_parsers_and_not_a_number_someone_typed() -> None:
    """A literal here would be wrong the first time anybody added a subcommand, and wrong quietly.

    Proved by asking the parser and by a parser that has one more command than the real one -
    the second half is what fails if the count is ever hard-coded back in.
    """
    assert f"all {len(_subcommands())} commands" in first_screen()

    extra = cli._build_parser()
    groups = [a for a in extra._actions if isinstance(a, argparse._SubParsersAction)]
    groups[0].add_parser("invented-for-this-test")
    assert f"all {len(_subcommands()) + 1} commands" in first_screen(extra)


# ---------------------------------------------- every invocation on the screen, actually executed


@pytest.fixture
def photos(tmp_path: Path) -> Path:
    """Three files whose names and bytes differ, so a count can only be right for one reason."""
    root = tmp_path / "Pictures"
    root.mkdir()
    for index, size in enumerate((101, 103, 107)):
        (root / f"IMG_{index:04d}.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"x" * size)
    return root


def _example(index: int, *replacements: tuple[str, str]) -> list[str]:
    """One screen line, turned into argv with the placeholders filled in."""
    argv = FIRST_SCREEN_STEPS[index][0].split()[1:]
    for placeholder, value in replacements:
        argv = [value if word == placeholder else word for word in argv]
    return argv


def test_the_first_example_reads_the_folder_and_changes_nothing(
    photos: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """*"Reads your files and changes none of them"* - both halves, run rather than believed.

    The sentence is the reason `analyze` is first: somebody who has just installed this has no
    reason yet to trust it with a library. A before/after of the whole tree is what makes that
    claim a measurement instead of a hope.
    """
    before = {p: p.read_bytes() for p in sorted(photos.rglob("*")) if p.is_file()}

    assert main(_example(0, ("FOLDER", str(photos)))) == 0

    assert "3" in capsys.readouterr().out
    after = {p: p.read_bytes() for p in sorted(photos.rglob("*")) if p.is_file()}
    assert after == before, "analyze modified the folder it was pointed at"


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_the_second_example_is_a_dry_run_that_writes_nothing(
    photos: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """*"A dry run: says where every file would go"* - so the destination must not exist after it.

    ⚠ **The assertion is the DESTINATION, not the exit code.** A run that wrote the library and
    exited 0 would satisfy a code check while making the screen's promise false, and that promise
    is the one a person relies on when they try this against real photographs for the first time.
    """
    destination = tmp_path / "Library"

    assert main(_example(1, ("FOLDER", str(photos)), ("DESTINATION", str(destination)))) == 0

    assert not destination.exists(), "the dry run created its destination"
    assert "SUMMARY" in capsys.readouterr().out, "the dry run said nothing about what it would do"


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_the_third_example_writes_the_library_and_leaves_the_originals(
    photos: Path, tmp_path: Path
) -> None:
    """*"Do it. Copies by default, so the originals stay where they are"* - both halves.

    The second half is the load-bearing one: `--apply` with `--move` would also fill the
    destination, and a screen that said "copies" over a command that moved would be the worst
    sentence in the product.
    """
    destination = tmp_path / "Library"
    before = {p.name: p.read_bytes() for p in photos.rglob("*") if p.is_file()}

    assert main(_example(2, ("FOLDER", str(photos)), ("DESTINATION", str(destination)))) == 0

    assert len(list(destination.rglob("*.jpg"))) == len(before)
    after = {p.name: p.read_bytes() for p in photos.rglob("*") if p.is_file()}
    assert after == before, "--apply removed or rewrote the originals"


def test_the_lead_says_what_the_program_is_before_it_says_what_to_type() -> None:
    """clig.dev's concise help is *a description, then examples* - in that order.

    A screen that opens with commands answers "what do I type" for somebody who does not yet know
    what they are typing it into. Asserted as position, which is the only part of "it explains
    itself" a test can actually hold.
    """
    screen = first_screen()
    assert screen.startswith(FIRST_SCREEN_LEAD)
    assert screen.index(FIRST_SCREEN_LEAD) < screen.index(FIRST_SCREEN_STEPS[0][0])
