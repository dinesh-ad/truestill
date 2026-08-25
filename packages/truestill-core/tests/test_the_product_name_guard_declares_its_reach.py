"""The `product-name` hook must declare the reach it has, not a wider one.

**What was wrong, found 2026-08-25.** The hook read
``types_or: [python, markdown, toml, javascript, html]`` beside ``pass_filenames: false``. Those
two together say nothing about scope: `types_or` decides only WHETHER a hook fires when a file of
that type is staged, and with `pass_filenames: false` the script is handed no paths at all. It
reads its own list - **13** entries in `check_product_name.CHECKED`. So the declaration named five
whole file types and the reach was thirteen files, and the pre-commit output printed the wider
claim above every commit.

⚠ **THE REACH IS RIGHT AND THE DECLARATION WAS WRONG, which is the opposite of the obvious fix.**
Measured before ruling, over today's tree: the full sweep of those five declared types finds
**367 offending lines across 146 files**. Of those, **35 files / 77 lines are records** -
`docs/research/`, the soak records, the audits - which this repo forbids rewriting, so widening
the reach would leave the guard permanently red with no legal repair. A derived glob does not
help either: `docs/*.md` alone pulls in the whole backlog and canon, 149 lines. **"A person
outside this repo reads this" is an editorial distinction, not a structural one**, so the shop
window is a curated list by necessity. `check_product_name`'s own docstring ruled this once
already, at 111 files and 351 lines; this is that ruling re-measured, not a new one.

So the fix is `always_run: true` and a truthful name, matching `no-redirect-artifacts`, which
made the same choice for the same reason. This file is what stops the wider claim coming back.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/check_product_name.py"
CONFIG = ROOT / ".pre-commit-config.yaml"


def _load():
    """The script, imported by path - the house pattern (`test_closed_entries_leave_the_backlog`).

    Imported rather than restated so the guard and this file cannot word the list differently.
    """
    spec = importlib.util.spec_from_file_location("check_product_name", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_guard = _load()


def _hook() -> dict[str, object]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    for repo in config["repos"]:
        for hook in repo.get("hooks", []):
            if hook.get("id") == "product-name":
                return dict(hook)
    missing = "no `product-name` hook in .pre-commit-config.yaml"
    raise AssertionError(missing)


# ------------------------------------------------------------------ the declaration matches


def test_the_hook_does_not_claim_a_file_type_scope_it_does_not_have() -> None:
    """`types_or` beside `pass_filenames: false` reads as scope and is not.

    The regression this refuses is textual: putting the five types back would make the hook's
    printed line claim the whole tree again while the script still reads thirteen files.
    """
    hook = _hook()
    declared = [key for key in ("types_or", "types") if key in hook]
    assert not declared, (
        "the product-name hook declares a file-type scope again. With `pass_filenames: false` "
        "that claims a reach the script does not have - it reads check_product_name.CHECKED, "
        f"which is {len(_guard.CHECKED)} paths. Use `always_run: true` and say so in the "
        f"name. Found: {declared}"
    )
    assert hook.get("always_run") is True, "the guard must run on every commit, not on a type"
    assert hook.get("pass_filenames") is False, "the script chooses its own files"


def test_the_hook_name_says_how_far_it_reaches() -> None:
    """A person reads the hook's name in the pre-commit column and nothing else."""
    name = str(_hook()["name"])
    assert str(len(_guard.CHECKED)) in name, (
        f"the hook name {name!r} does not say how many surfaces it covers; a reader takes the "
        "printed line at face value, which is how the wider claim survived."
    )


# --------------------------------------------------------------------------- the list is real


def test_every_checked_path_resolves() -> None:
    """A moved file is a broken guard, not a skip.

    `main()` already refuses at commit time; this brings it forward to `make check`, which is
    the standing rule before every commit and the only one that runs without the hooks.
    """
    missing = [name for name in _guard.CHECKED if not (ROOT / name).is_file()]
    assert not missing, f"CHECKED names paths that are gone: {missing}"


# ------------------------------------------------------------------------------ anti-vacuity


def test_the_guard_has_a_corpus_to_judge() -> None:
    """A guard reading zero lines makes every assertion about it true.

    **Measured on the tree this landed against**: 13 files, **10,952 lines**, and **443**
    mentions of the name - the subject the guard exists to rule on. The floors are `> 8` files
    and `> 200` mentions: comfortably under today's numbers, and loud if `CHECKED` were emptied
    or the reader stopped finding text.
    """
    assert len(_guard.CHECKED) > 8, f"only {len(_guard.CHECKED)} surfaces listed"
    mentions = sum(
        (ROOT / name).read_text(encoding="utf-8").lower().count("truestill")
        for name in _guard.CHECKED
    )
    assert mentions > 200, f"only {mentions} mentions found; is the guard still reading files?"


def test_the_shop_window_is_clean() -> None:
    """The control run. Every assertion below is worthless if the corpus is already red."""
    dirty = {n: _guard.offences(ROOT / n) for n in _guard.CHECKED}
    assert not any(dirty.values()), f"the guard's own corpus is not clean: {dirty}"


# ---------------------------------------------------------------- cry-wolf, in both directions


def test_it_flags_prose_that_lowercases_the_name(tmp_path: Path) -> None:
    """The mutation half: a real offence, in the shape the guard exists for."""
    page = tmp_path / "page.md"
    page.write_text("Welcome to truestill, the local-first organizer.\n", encoding="utf-8")
    assert _guard.offences(page), "a lowercase name in plain prose was not flagged"


def test_it_flags_nothing_in_a_file_of_identifiers(tmp_path: Path) -> None:
    """The cry-wolf half, and the reason the reach is narrow.

    Every line here is an identifier or an invocation - the vocabulary that fills this repo's
    docstrings, tests and records. A guard that fired on any of them would be switched off
    (`ENGINEERING_STANDARD.md` §4), which is what the 367-line measurement in the module
    docstring is really saying.
    """
    page = tmp_path / "page.md"
    page.write_text(
        "Run `truestill organize` first.\n"
        "The package is truestill_core and the command is truestill-cli.\n"
        "See truestill.app for downloads, or /opt/truestill/bin.\n"
        "TRUESTILL_DATA_DIR points at the library.\n"
        "```\ntruestill is written lowercase inside a fence and does not count\n```\n",
        encoding="utf-8",
    )
    assert _guard.offences(page) == [], "the guard fired on ordinary identifier vocabulary"


@pytest.mark.parametrize("suffix", [".md", ".py", ".toml", ".js", ".html"])
def test_every_declared_file_type_is_actually_readable(tmp_path: Path, suffix: str) -> None:
    """The five types the hook used to name are still the ones the script can parse.

    Dropping `types_or` removed the claim, not the capability - `CHECKED` holds all five, and a
    reader who sees the narrower name should not conclude the others stopped working.
    """
    page = tmp_path / f"page{suffix}"
    page.write_text("a sentence about truestill that a person reads\n", encoding="utf-8")
    assert _guard.offences(page), f"{suffix} files are no longer read at all"
