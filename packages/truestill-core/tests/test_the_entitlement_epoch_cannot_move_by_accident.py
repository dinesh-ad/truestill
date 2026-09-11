"""Bumping `BUILD_EPOCH` is a commercial act, and a one-character diff does not look like one.

**What it costs when it moves.** Every token whose ``covers_through`` is below the new value
stops covering *new* builds the moment it changes. Nobody loses anything they installed - D16 §2
and §5 - but everyone who has not renewed stops receiving updates, and that is a decision with a
price, taken by editing a single digit in a source file.

⚠ **So the integer is not the record; the TABLE is.** :data:`~truestill_core.licence.EPOCH_OPENED_AT`
maps each epoch to the release that opened it, which makes opening one a row a reviewer sees in a
diff rather than a character they scroll past. The three properties below are what make the table
binding instead of decorative, and the second is the one the ruling actually asked for: **an
epoch may not be opened by a patch release.**

**Why a test rather than a CI step:** `make check` runs before every commit and cannot be skipped
by dispatching a workflow with the wrong inputs, so the rule is met by whoever moves the number
rather than by whoever remembers to look. The artifact half - that a *built* binary carries the
epoch its checkout declared - is `packaging/compare_selfcheck.py`, which already compares an
artifact's self-check against the tree it was built from.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from truestill_core.licence import BUILD_EPOCH, EPOCH_OPENED_AT

_ROOT = Path(__file__).resolve().parents[3]


def _version_of(package: str) -> tuple[int, int, int]:
    manifest = tomllib.loads((_ROOT / "packages" / package / "pyproject.toml").read_text())
    major, minor, patch = manifest["project"]["version"].split(".")[:3]
    return int(major), int(minor), int(patch)


def _parts(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")[:3]
    return int(major), int(minor), int(patch)


def test_the_running_epoch_is_the_newest_row_in_the_table() -> None:
    """The integer and the record cannot disagree.

    Without this, bumping `BUILD_EPOCH` alone would leave the table describing an epoch the
    product no longer runs in - the record saying one thing and the behaviour another, which is
    the drift this repo has a census of in its own documents.
    """
    assert EPOCH_OPENED_AT, "the table is the record; an empty one records nothing"
    assert max(EPOCH_OPENED_AT) == BUILD_EPOCH


def test_the_epochs_are_consecutive_from_one() -> None:
    """A gap would mean a token carrying `covers_through` for an epoch that never existed, and
    nothing downstream would notice - it would simply compare as lapsed for ever."""
    assert sorted(EPOCH_OPENED_AT) == list(range(1, max(EPOCH_OPENED_AT) + 1))


def opening_problems(table: dict[int, str]) -> list[str]:
    """Every way ``table`` breaks the opening rule. **The rule itself, in one place.**

    Extracted rather than inlined into a loop over the live table, and that is a vacuity fix
    rather than tidiness: the live table has **one row**, so a loop skipping the first entry -
    which any such loop must, since epoch 1 has no predecessor - executes zero times and asserts
    nothing. It would have gone on asserting nothing until the day the rule first mattered, which
    is the dead-assertion shape this repo already has a census of. The synthetic cases below
    exercise it today; the live table is checked with the same function.
    """
    problems: list[str] = []
    for epoch in sorted(table)[1:]:
        previous, opened = _parts(table[epoch - 1]), _parts(table[epoch])
        if opened <= previous:
            problems.append(f"epoch {epoch} opens at or before epoch {epoch - 1}")
        elif opened[:2] == previous[:2]:
            problems.append(
                f"epoch {epoch} opens at {table[epoch]}, a PATCH bump from {table[epoch - 1]}. "
                "An entitlement period is a commercial change and must be announced by a minor "
                "or major version, not slipped into a bug-fix release."
            )
    return problems


def test_the_live_table_opens_every_epoch_legitimately() -> None:
    """The rule, applied to what actually ships."""
    assert opening_problems(EPOCH_OPENED_AT) == []


def test_an_epoch_opened_by_a_patch_release_is_refused() -> None:
    """**The ruling itself, exercised against a table that breaks it.**

    A patch is where a bug fix goes out, which is exactly the release nobody reads the diff of
    twice. Requiring a minor or major bump means the version number itself announces that
    something commercial happened, to every customer, without anyone having to write a note.

    ⚠ This is the scenario a mutation found could not be reached through the live table: bumping
    `BUILD_EPOCH` to 2 and adding `2: "0.1.1"` is a two-line diff that looks like housekeeping
    and silently ends every unrenewed customer's updates one release early.
    """
    refused = opening_problems({1: "0.1.0", 2: "0.1.1"})

    assert len(refused) == 1
    assert "PATCH bump" in refused[0]


def test_an_epoch_opened_by_a_minor_or_major_release_is_allowed() -> None:
    """The cry-wolf half. A checker that refused everything would satisfy the test above while
    making the rule impossible to comply with."""
    assert opening_problems({1: "0.1.0", 2: "0.2.0"}) == []
    assert opening_problems({1: "0.1.0", 2: "0.2.0", 3: "1.0.0"}) == []


def test_an_epoch_that_opens_before_its_predecessor_is_refused() -> None:
    """Out of order, which is what a hand-edited table produces when two releases are in flight."""
    refused = opening_problems({1: "0.2.0", 2: "0.1.0"})

    assert len(refused) == 1
    assert "at or before" in refused[0]


def test_the_shipped_version_has_reached_the_epoch_it_claims_to_run_in() -> None:
    """A build cannot run in an epoch its own version has not got to yet.

    This is what catches the half-done bump: a table row added for the next release, and the
    version left where it was, so a build that is still 0.1.x behaves as though it is 0.2.x and
    lapses every existing token a release early.
    """
    opened = _parts(EPOCH_OPENED_AT[BUILD_EPOCH])

    for package in ("truestill-core", "truestill-cli", "truestill-app"):
        assert _version_of(package) >= opened, (
            f"{package} is at {_version_of(package)} but epoch {BUILD_EPOCH} opens at {opened}"
        )


def test_the_three_packages_ship_one_version() -> None:
    """Anti-vacuity for the test above, and a real property in its own right.

    The epoch check compares against each package's own version, so three packages drifting apart
    would make "has the version reached the epoch" three different questions with three different
    answers, and the weakest one would be the one that mattered.
    """
    versions = {
        package: _version_of(package)
        for package in ("truestill-core", "truestill-cli", "truestill-app")
    }

    assert len(set(versions.values())) == 1, versions
