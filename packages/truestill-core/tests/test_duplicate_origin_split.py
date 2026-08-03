"""A skipped duplicate must say *where* its twin is, in the count as well as per file.

**Found on a real organize.** The run reported `2,057  duplicate, skipped` and the preview
reported `EXACT DUPLICATES (2057) - skipped, not organized`. Both are true and neither answers
the only question a person has at that moment: *did Truestill already have these, or did my
source folder contain two copies of each?* Those lead to opposite next actions - the first says
the source copies are redundant and can go, the second says nothing about the library at all.

`duplicate_explain` has answered this **per match** since it was written; `_ORIGINS` calls them
*"already in your library"* and *"earlier in this batch"* and its own comment says the
distinction "is never collapsed into 'a duplicate'". The counts collapsed it anyway. This is a
`IMPLEMENTATION_STANDARDS.md` §9 gap of the same shape as the one that module was built to
close: counted, but not named.

**The split is computed over every match, never over the shown sample.** `DUPLICATE_SAMPLE_LIMIT`
caps the app's named list at 200. A split derived from that list would silently read "200" on a
library with thousands and look entirely plausible.
"""

from __future__ import annotations

import pytest
from truestill_core.duplicate_explain import (
    ORIGIN_HEADLINE,
    DuplicateSplit,
    describe_split,
    origin_phrase,
    split_by_origin,
)
from truestill_core.models import DuplicateKind, DuplicateMatch, DuplicateOrigin


def _exact(origin: DuplicateOrigin | str, path: str = "/library/2014/a.jpg") -> DuplicateMatch:
    return DuplicateMatch(kind=DuplicateKind.EXACT, matched_path=path, origin=origin)


# --- the split itself ----------------------------------------------------------------------


def test_the_two_origins_are_counted_apart() -> None:
    matches = [
        _exact(DuplicateOrigin.CATALOG),
        _exact(DuplicateOrigin.CATALOG),
        _exact(DuplicateOrigin.RUN),
    ]
    split = split_by_origin(matches)
    assert split.already_in_library == 2
    assert split.within_this_batch == 1
    assert split.total == 3


def test_a_bare_string_counts_the_same_as_the_member() -> None:
    """The engine has always written plain tokens; a split that ignored them would read zero."""
    split = split_by_origin([_exact("catalog"), _exact("run")])
    assert split.already_in_library == 1
    assert split.within_this_batch == 1


def test_an_unknown_origin_is_not_silently_dropped() -> None:
    """The count must still add up. A token nobody recognises is the one worth keeping.

    `origin_phrase` deliberately degrades an unknown token to itself rather than raising,
    because it is a display path. A *count* has no such licence: quietly discarding a match
    would make the parts stop summing to the whole, which is the failure this file exists to
    prevent in the first place.
    """
    split = split_by_origin([_exact("somewhere-new"), _exact(DuplicateOrigin.RUN)])
    assert split.total == 2
    assert split.already_in_library + split.within_this_batch + split.unclassified == split.total
    assert split.unclassified == 1


def test_no_matches_is_an_empty_split_not_a_special_case() -> None:
    assert split_by_origin([]) == DuplicateSplit(0, 0, 0)


# --- the words a user reads ------------------------------------------------------------------


def test_the_two_lines_name_where_the_twin_is() -> None:
    """The deliverable. Both phrases come from `_ORIGINS`, so the count and the per-file line
    cannot describe the same match in two vocabularies."""
    lines = describe_split(DuplicateSplit(already_in_library=2, within_this_batch=1))
    joined = "\n".join(lines)
    assert origin_phrase(DuplicateOrigin.CATALOG) in joined  # "already in your library"
    assert origin_phrase(DuplicateOrigin.RUN) in joined  # "earlier in this batch"
    assert "2" in joined
    assert "1" in joined


def test_a_zero_bucket_prints_no_line_at_all() -> None:
    """Never-silent is about what happened, not about what did not.

    "0 already in your library" invites a user to wonder what they did wrong. A run whose
    duplicates were all of one kind should read as one clean statement.
    """
    lines = describe_split(DuplicateSplit(already_in_library=4, within_this_batch=0))
    assert len(lines) == 1
    assert origin_phrase(DuplicateOrigin.CATALOG) in lines[0]
    assert origin_phrase(DuplicateOrigin.RUN) not in lines[0]


def test_nothing_at_all_prints_nothing() -> None:
    assert describe_split(DuplicateSplit(0, 0, 0)) == []


def test_an_unclassified_match_is_named_rather_than_hidden() -> None:
    """If the parts would not sum to the whole, say so instead of printing a smaller truth."""
    lines = describe_split(
        DuplicateSplit(already_in_library=1, within_this_batch=0, unclassified=2)
    )
    assert len(lines) == 2
    assert "somewhere" in lines[1] or "2" in lines[1]


@pytest.mark.parametrize("origin", [DuplicateOrigin.CATALOG, DuplicateOrigin.RUN])
def test_the_headline_never_claims_a_file_was_deleted(origin: DuplicateOrigin) -> None:
    """The fear this whole module was built around. An exact duplicate was *not copied*;
    nothing of the user's was removed, and the wording must not suggest otherwise."""
    text = (ORIGIN_HEADLINE + " " + " ".join(describe_split(DuplicateSplit(1, 1)))).casefold()
    assert "delet" not in text
    assert "remov" not in text
    assert origin_phrase(origin).casefold() in text


# --- the vocabulary has one home ---------------------------------------------------------------


def test_the_origin_tokens_are_the_ones_the_engine_writes() -> None:
    """Anti-drift: the enum's *values* are the strings `DedupIndex` has always produced, so
    adopting it renamed nothing and no stored or compared token changed."""
    assert DuplicateOrigin.RUN == "run"
    assert DuplicateOrigin.CATALOG == "catalog"
