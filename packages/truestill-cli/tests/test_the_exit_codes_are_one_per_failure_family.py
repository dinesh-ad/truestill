"""Nine exit codes, and the only thing a caller can read is the number.

**An exit code is an API with no room for a message.** A script that runs `truestill` sees one
integer, and the whole reason this CLI allocates *one per failure family* - rather than returning
`1` for everything - is that the families call for opposite actions: `5` and `8` mean wait, `7`
means run `rescan`, `3` means install something, `9` means stop looping and tell a person.

⚠ **So two families sharing a number is not untidiness, it is a caller doing the wrong thing to
somebody's photo library.** A script that retried a `9` because it read as a `5` would spin for
ever; one that treated a `7` as a `9` would give up on a catalog a single command would repair.
Nothing but this file compares the nine values, and they are declared in two modules by design -
`6` lives in core because both surfaces refuse identically - so nothing else *can*.

Added with `9` (`DECISIONS.md` D16 §5), which is the first code allocated since the set grew past
what one person holds in their head.
"""

from __future__ import annotations

from truestill_cli.cli import (
    ALLOWANCE_EXHAUSTED_EXIT,
    CATALOG_BUSY_EXIT,
    CATALOG_UNWRITABLE_EXIT,
    DRIVE_BUSY_EXIT,
)
from truestill_core.catalog_startup import CATALOG_UNUSABLE_EXIT

#: Every allocated code and the family it belongs to. `1` and `2` are here because they are
#: allocated too - the comment on `CATALOG_BUSY_EXIT` reasons against both by name - and leaving
#: them out would let a later family claim one of them without this file objecting.
ALLOCATED: dict[int, str] = {
    1: "the run finished and something is wrong with the library",
    2: "usage or validation - never becomes valid by waiting",
    3: "exiftool is missing - install it, then run the same command again",
    4: "the destination cannot be used - fix the path or its permissions",
    5: "another process holds the catalog - retry",
    6: "the catalog is unusable",
    7: "a catalog write failed in a way retrying cannot fix - run rescan",
    8: "another live process is mutating this drive - retry",
    9: "the free allowance cannot cover this run - it did not start",
}

#: The codes that exist as importable constants, checked against the table above. `3` and `4`
#: are deliberately absent: they are returned as literals by their handlers and have never been
#: named, which this file records rather than fixes - inventing constants for them would be a
#: change to code this test was not asked to touch, and the reader should know the gap is known.
DECLARED: dict[str, int] = {
    "CATALOG_BUSY_EXIT": CATALOG_BUSY_EXIT,
    "CATALOG_UNUSABLE_EXIT": CATALOG_UNUSABLE_EXIT,
    "CATALOG_UNWRITABLE_EXIT": CATALOG_UNWRITABLE_EXIT,
    "DRIVE_BUSY_EXIT": DRIVE_BUSY_EXIT,
    "ALLOWANCE_EXHAUSTED_EXIT": ALLOWANCE_EXHAUSTED_EXIT,
}


def test_no_two_families_share_a_code() -> None:
    """The property the whole file exists for."""
    assert len(set(DECLARED.values())) == len(DECLARED), DECLARED


def test_every_declared_code_is_in_the_allocation_table() -> None:
    """A constant added without a row is a family nobody wrote down.

    This is the half that fires on the *next* code: whoever allocates `10` gets a red run telling
    them to say what it means, in the file where the other nine already do.
    """
    for name, code in DECLARED.items():
        assert code in ALLOCATED, f"{name} = {code} is not in the allocation table"


def test_the_allowance_refusal_is_nine_and_is_not_one_of_the_wait_codes() -> None:
    """**The new allocation, asserted against the two it is most likely to be confused with.**

    `5` and `8` both mean *retry shortly*. `9` means the opposite: the condition will never clear
    on its own, and a caller that keeps trying is a caller in an infinite loop. They are told
    apart by nothing but the integer.
    """
    assert ALLOWANCE_EXHAUSTED_EXIT == 9
    assert ALLOWANCE_EXHAUSTED_EXIT not in {CATALOG_BUSY_EXIT, DRIVE_BUSY_EXIT}


def test_the_table_is_contiguous_so_the_next_code_is_obvious() -> None:
    """Whoever allocates next should not have to search three modules to find a free number.

    A gap would also be a code that *was* allocated and got removed, which is the one situation
    where reusing a number is genuinely dangerous: a script written against the old meaning keeps
    running.
    """
    assert sorted(ALLOCATED) == list(range(1, len(ALLOCATED) + 1))


def test_every_row_says_what_a_caller_should_do_about_it() -> None:
    """Anti-vacuity, and the reason this table is worth having at all.

    A row reading "error" would satisfy every test above while recording nothing. The point of
    one code per family is that the families differ in the *action*, so a row that does not
    describe one is not an allocation, it is a number with a label.
    """
    for code, meaning in ALLOCATED.items():
        assert len(meaning.split()) >= 4, f"{code}: {meaning!r} does not describe a situation"
