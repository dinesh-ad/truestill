"""A guard that enumerates the INDEX cannot see the file being added. `repo_sources` is the fix.

⚠ **THE FUSE WENT OFF, WHICH IS WHY THIS EXISTS RATHER THAN BEING RECORDED.** `git ls-files`
alone lists the index, so a brand-new file is invisible until it is added - which is after the
`make check` that was supposed to gate it. Stage 1 of the restore arc shipped
`truestill_core.carried` suggesting `truestill drives --init` without `--label`, a command the
runtime refuses, straight past `test_a_suggested_command_can_be_run`. The gate was green and
blind, and the turn's own record said it was green.

**Two instances is the evidence `(ago)` asks for before a guard earns itself**:
`test_no_incidental_naming` found the shape first and fixed only itself, writing down *"a false
green with a delay fuse"*; the census behind this commit found **twelve** more call sites. A
practice would have to be remembered by whoever writes the thirteenth.

⚠ **SCOPED TO TESTS, and the exemptions are real rather than convenient.** A mutating tool must
NOT see untracked files: `scripts/normalize_dashes.py` says so in its own words - *"Uses git so
untracked scratch files are never rewritten"* - and rewriting somebody's scratch would be a worse
defect than the one this closes. Tools are therefore out of scope; guards are in it.
"""

from __future__ import annotations

import re
from pathlib import Path

import repo_sources

#: An enumeration that stops at the index. `--others` is what widens it; `--untracked` is
#: `git grep`'s spelling of the same thing.
_INDEX_ONLY = re.compile(r'"ls-files"(?![^)]*--others)|"grep"(?![^)]*--untracked)')

#: Files the pattern must not police: the shared helper, and **this file**, which necessarily
#: spells both shapes - once to define the pattern, and twice more as the fixtures that prove it
#: catches them. It is covered instead by the two tests below, which is the honest trade: a guard
#: cannot be its own subject without either exempting itself or being written in a way that
#: hides what it looks for.
_EXEMPT = frozenset(
    {
        "repo_sources.py",
        Path(__file__).name,
        # ⚠ **The one test that MUST ask the index**: it proves the widened listing differs from
        # it, which cannot be shown without querying both. Exempted by name rather than by a
        # comment marker, so adding one is a visible decision rather than a line somebody types.
        "test_a_census_sees_the_file_being_added.py",
        # ⚠ **The second, and tracked-ness IS its subject** (`(akv)`). The release lane runs
        # `packaging/truestill.spec`; `.gitignore` matched that name at any depth, so `git add -A`
        # skipped it silently and the lane failed with "Spec file not found" on a commit green
        # everywhere else. A widened listing would report the file present - it IS present, in the
        # working tree - and pass while a fresh clone has nothing. The index is precisely the
        # question, and the failure this exemption permits is a false RED before staging, which is
        # the safe direction: a source file the lane needs belongs in the commit.
        "test_the_package_ships_every_binary_it_promises.py",
    }
)


def _guard_files() -> list[Path]:
    files = [p for p in repo_sources.files("packages/*/tests/*.py") if p.name not in _EXEMPT]
    assert files, (
        "`repo_sources.files('packages/*/tests/*.py')` matched nothing, so this guard has no "
        "subject and would find zero index-only censuses in zero files. "
        "ENGINEERING_STANDARD.md 4, the fifty-second member."
    )
    return files


def test_no_guard_enumerates_only_the_index() -> None:
    """The gate. A census that stops at the index is blind to the commit it is gating."""
    offenders: list[str] = []
    for path in _guard_files():
        text = path.read_text(encoding="utf-8")
        for match in _INDEX_ONLY.finditer(text):
            line = text[: match.start()].count("\n") + 1
            offenders.append(f"{path.name}:{line}")

    assert not offenders, (
        "these enumerate the index, so they cannot see a file being added by the very commit "
        "`make check` is gating. Use `repo_sources.paths()` / `.files()`, or pass "
        "`--untracked` to `git grep`:\n  " + "\n  ".join(offenders)
    )


def test_the_pattern_catches_the_shape_it_is_named_for() -> None:
    """⚠ **The anti-vacuity half.** Without it, a pattern that matched nothing would pass
    for ever and the guard above would be a green that means nothing."""
    assert _INDEX_ONLY.search('subprocess.run(["git", "ls-files", "*.py"], cwd=REPO)')
    assert _INDEX_ONLY.search('subprocess.run(["git", "grep", "-n", "needle", "--", "packages"])')


def test_the_pattern_spares_the_widened_forms() -> None:
    """The cry-wolf half. A guard that failed on the remedy would be worse than the hole."""
    assert not _INDEX_ONLY.search(
        'subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"])'
    )
    assert not _INDEX_ONLY.search(
        'subprocess.run(["git", "grep", "-n", "--untracked", "needle", "--", "packages"])'
    )
