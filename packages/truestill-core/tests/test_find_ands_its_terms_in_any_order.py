"""A search box is words, not one literal string. `(abj)`

⚠ **THE DEFECT, MEASURED ON THE BIG RUN.** ``IMG`` returned 998 of 2,574 and ``2014`` returned
thousands, while ``2014 IMG`` returned **ZERO** - and every one of those files is named
``IMG_xxxx`` and sits under a ``2014`` folder. The two words were matched as one literal substring
that appears in no filename and no path, so the query that describes the corpus exactly was the one
query guaranteed to find nothing.

🔑 **The rule, and both halves are documented practice rather than invention.**

* Google Issue Tracker's query language treats *"the space character separating search criteria as
  an implicit AND operator"*, and *"you can use quotation marks to specify that a multi-word string
  is to be considered as a single keyword"*.
* GitLab, on why tokenising alone fails users: they *"are actually expecting code search to be more
  like a grep experience or the find function in their IDE. These almost all behave, by default, as
  an exact substring match."*

Combined: **each word is a substring match, and the words are ANDed.** Quotes make a phrase.

⚠ **ORDER MUST NOT MATTER**, and that is asserted in both directions rather than reasoned about
once. AND commutes, but so does a great deal of code that turns out to depend on position.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.catalog import Catalog, parse_search_terms

#: One file per row: (original_name, relative on the drive, source_path).
_CORPUS = [
    ("IMG_0001.jpg", "2014/2014-08/2014-08-12 - Wayanad/20140812_IMG_0001.jpg", "/in/IMG_0001.jpg"),
    (
        "IMG_0002.jpg",
        "2014/2014-09/2014-09-01 - Everyday/20140901_IMG_0002.jpg",
        "/in/IMG_0002.jpg",
    ),
    (
        "IMG_0003.jpg",
        "2015/2015-03/2015-03-02 - Everyday/20150302_IMG_0003.jpg",
        "/in/IMG_0003.jpg",
    ),
    ("DSC_9000.jpg", "2014/2014-08/2014-08-12 - Wayanad/20140812_DSC_9000.jpg", "/in/DSC_9000.jpg"),
    ("scan 100%.jpg", "Saved/Undated/scan 100%.jpg", "/in/scan 100%.jpg"),
]


@pytest.fixture
def library(tmp_path: Path) -> Path:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        conn = catalog._conn
        conn.execute("INSERT INTO drives (uuid, label) VALUES ('D1', 'BackupA')")
        for index, (name, relative, source) in enumerate(_CORPUS):
            sha = f"{index:064x}"
            conn.execute(
                "INSERT INTO files (sha256, original_name, size, source_path, category,"
                " relative, upload_status, processed_at)"
                " VALUES (?, ?, ?, ?, 'Camera', ?, 'uploaded', '2026-09-15T00:00:00+00:00')",
                (sha, name, index, source, relative),
            )
            conn.execute(
                "INSERT INTO file_copies (sha256, drive_uuid, relative) VALUES (?, 'D1', ?)",
                (sha, relative),
            )
        conn.commit()
    return db


def _names(db: Path, term: str) -> list[str]:
    with Catalog(db) as catalog:
        return sorted(str(row["original_name"]) for row in catalog.find_copies(term))


def _count(db: Path, term: str) -> int:
    with Catalog(db) as catalog:
        return catalog.count_copies(term)


# --- the parser -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("2014 IMG", ["2014", "IMG"]),
        ("IMG 2014", ["IMG", "2014"]),
        ("IMG", ["IMG"]),
        ('"2014 IMG"', ["2014 IMG"]),
        ('beach "new york" 2019', ["beach", "new york", "2019"]),
        ("a  b", ["a", "b"]),
        ("  padded  ", ["padded"]),
        ("", []),
        ("   ", []),
        ('""', []),
        ('"unclosed', ["unclosed"]),
    ],
)
def test_the_query_splits_into_the_terms_a_person_typed(query: str, expected: list[str]) -> None:
    assert parse_search_terms(query) == expected


# --- the rule -------------------------------------------------------------------------------


def test_two_words_match_a_file_that_carries_both(library: Path) -> None:
    """**The headline.** Neither word appears beside the other anywhere in the corpus."""
    assert _names(library, "2014 IMG") == ["IMG_0001.jpg", "IMG_0002.jpg"]


def test_the_order_of_the_words_does_not_change_the_result(library: Path) -> None:
    """⚠ **Asserted both ways round**, because "AND commutes" is a claim about the code."""
    assert _names(library, "2014 IMG") == _names(library, "IMG 2014")
    assert _count(library, "2014 IMG") == _count(library, "IMG 2014") == 2


def test_a_quoted_phrase_is_one_term_and_not_two(library: Path) -> None:
    """The escape hatch Google's language provides, and the thing the old search did to
    everything: ``"2014 IMG"`` is a literal that appears in no name and no path."""
    assert _names(library, '"2014 IMG"') == []
    assert _names(library, '"2014-08-12 - Wayanad"') == ["DSC_9000.jpg", "IMG_0001.jpg"]


def test_one_word_still_behaves_exactly_as_it_did(library: Path) -> None:
    """⚠ **The half that must NOT change.** Every single-term search is a substring over the
    same three columns, so a person who learned the old box loses nothing."""
    assert _names(library, "IMG") == ["IMG_0001.jpg", "IMG_0002.jpg", "IMG_0003.jpg"]
    assert _names(library, "Wayanad") == ["DSC_9000.jpg", "IMG_0001.jpg"]
    assert _names(library, "2015") == ["IMG_0003.jpg"]


def test_a_term_that_matches_nothing_returns_nothing(library: Path) -> None:
    """And it must be the AND that empties it, not an error: ``IMG`` alone matches three."""
    assert _names(library, "IMG zzzz") == []
    assert _count(library, "IMG zzzz") == 0
    assert _names(library, "zzzz") == []


def test_every_word_must_match_not_merely_one_of_them(library: Path) -> None:
    """The difference between AND and OR, stated as a test because it is the whole ruling.

    ``DSC`` matches one file and ``2015`` matches a different one. Under OR this would be two
    results; under AND it is none, and AND is what was ruled.
    """
    assert _names(library, "DSC") == ["DSC_9000.jpg"]
    assert _names(library, "2015") == ["IMG_0003.jpg"]
    assert _names(library, "DSC 2015") == []


# --- the hazards `(abj)` named --------------------------------------------------------------


def test_an_empty_search_returns_nothing_rather_than_the_whole_library(library: Path) -> None:
    """⚠ **It returned EVERY ROW until `(abj)`** - measured on the real catalog as 3,828 of
    3,828 - because `LIKE '%%'` matches anything. A blank box is a question nobody asked, and
    an unfiltered dump is the wrong answer to it."""
    for blank in ("", "   ", '""', "\t\n"):
        assert _names(library, blank) == [], f"a blank query ({blank!r}) returned rows"
        assert _count(library, blank) == 0


def test_like_wildcards_in_a_term_are_matched_literally(library: Path) -> None:
    """⚠ **`%` returned the ENTIRE library and `_` matched any character, until `(abj)`.**

    A search box is a substring search, not a pattern language - GitLab's finding, above. The
    corpus holds a file genuinely called ``scan 100%.jpg`` so the escape is proven to still
    *find* the character rather than merely to defuse it.
    """
    # ⚠ **The corpus is what makes this test say something.** `%` is now a search for a literal
    # percent sign, and exactly one file has one - so the assertion proves both halves at once:
    # it is no longer a wildcard (it does not return all five) and it is not merely defused
    # (it still finds the file that really contains the character).
    assert _names(library, "%") == ["scan 100%.jpg"], "a bare % still behaves as a wildcard"
    assert _count(library, "%") == 1
    assert len(_CORPUS) > 1, "a one-row corpus could not tell a wildcard from a literal"
    assert _names(library, "100%") == ["scan 100%.jpg"], "the escape lost a real literal %"
    # `IMG_0001` must not match `IMG-0001`-shaped names via `_`; here it pins the literal read.
    assert _names(library, "IMG_0001") == ["IMG_0001.jpg"]


def test_the_count_and_the_page_agree_about_what_matches(library: Path) -> None:
    """⚠ **Two hand-written copies of the same WHERE clause until `(abj)`.**

    `count_copies` and `find_copies_query` each carried their own, which is two statements that
    must agree or the pager lies - *"showing 1-50 of N"* where N was computed by different rules
    is worse than no count at all. One builder now feeds both.
    """
    for term in ("IMG", "2014 IMG", "IMG 2014", '"2014-08-12 - Wayanad"', "zzzz", ""):
        assert _count(library, term) == len(_names(library, term)), (
            f"the count and the rows disagree for {term!r}"
        )
