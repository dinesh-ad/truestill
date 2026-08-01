"""``--source`` and its permanent ``--takeout`` alias resolve to the same behaviour.

**Why the rename.** `--takeout` named the *motivating case* rather than the feature: archive
ingestion reads any `.zip`, `.tar`, `.tgz` or `.tar.gz` from any source, and every major photo
service hands a user a `.zip`. `--source` is format-neutral and matches `organize`'s existing
`source`, so the two commands stop disagreeing about what the input is called.

**Why the alias is permanent rather than deprecated.** It shipped, so scripts use it. Keeping it
costs one line, resolves to the same ``dest`` - so there is no second code path to keep correct -
and a removal window would break those scripts on a schedule in exchange for nothing.

**These assert equivalent BEHAVIOUR, not that both spellings parse.** A parse test would pass
against an alias wired to its own separate `dest`, which is exactly the bug worth catching: two
spellings that both work and mean different things.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from truestill_cli.cli import _build_parser, main


def _parse(argv: list[str]) -> argparse.Namespace:
    return _build_parser().parse_args(argv)


def test_both_spellings_land_on_the_same_attribute(tmp_path: Path) -> None:
    """The equivalence that matters: one `dest`, so there is only ever one value to read."""
    new = _parse(["ingest", str(tmp_path / "out"), "--source", str(tmp_path / "in")])
    old = _parse(["ingest", str(tmp_path / "out"), "--takeout", str(tmp_path / "in")])

    assert new.source == old.source == tmp_path / "in"


def test_the_alias_has_no_attribute_of_its_own(tmp_path: Path) -> None:
    """Guards the bug a parse-only test would miss: two spellings that mean different things.

    If ``--takeout`` had its own ``dest``, both would parse, both would look fine, and the code
    reading ``args.source`` would silently ignore anything passed the old way.
    """
    parsed = _parse(["ingest", str(tmp_path / "out"), "--takeout", str(tmp_path / "in")])

    assert not hasattr(parsed, "takeout")


def test_the_alias_is_hidden_from_help_but_still_works() -> None:
    """Hidden so new users are shown one name; present so old scripts keep running."""
    help_text = _build_parser().format_help()
    ingest_help = _ingest_help()

    assert "--source" in ingest_help
    assert "--takeout" not in ingest_help, "the alias is advertised, so there are two names"
    assert "--takeout" not in help_text


def _ingest_help() -> str:
    for action in _build_parser()._subparsers._group_actions:
        choices = getattr(action, "choices", None)
        if choices and "ingest" in choices:
            return str(choices["ingest"].format_help())
    message = "the ingest subcommand is gone"
    raise AssertionError(message)


@pytest.mark.parametrize("spelling", ["--source", "--takeout"])
def test_either_spelling_is_accepted_as_required(tmp_path: Path, spelling: str) -> None:
    """Neither is optional: `ingest` without a source must still fail rather than guess."""
    parsed = _parse(["ingest", str(tmp_path / "out"), spelling, str(tmp_path / "in")])

    assert parsed.source == tmp_path / "in"


def test_ingest_without_any_source_still_fails(tmp_path: Path) -> None:
    """The requirement moved out of argparse, so it is asserted where it now lives.

    `--source` cannot be `required=True`: argparse counts the two spellings as separate
    arguments, so a script passing only `--takeout` would be told `--source` is missing - the
    alias would parse and then fail, which is worse than having no alias at all.
    """
    assert _parse(["ingest", str(tmp_path / "out")]).source is None

    code = main(["ingest", str(tmp_path / "out")])

    assert code == 2
