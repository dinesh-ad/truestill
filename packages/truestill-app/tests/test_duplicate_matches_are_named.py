"""A skipped duplicate is named, not just counted (§9), on both surfaces.

**The app was the drifted twin.** The engine has always computed
:class:`~truestill_core.models.DuplicateMatch` - matched path, tier, origin, perceptual distance -
and the CLI has always printed it (`_format_exact`, `_format_new`). The app dropped every field
at the payload boundary and rendered *"2,057 duplicates - identical to a kept file"*, with no way
to learn which kept file. `IMPLEMENTATION_STANDARDS.md` §9 requires a skipped outcome to be
counted **and named**; the app counted.

So the tests below assert the *same facts* on both surfaces from one fixture, and the wording has
a single home (`truestill_core.duplicate_explain`) rather than two copies with a guard watching
them - the remedy `ENGINEERING_STANDARD.md` §4 asks for.

**Truncation is disclosed in the payload, not only on screen.** A 2,057-duplicate run cannot ship
2,057 rows, so the report carries ``total`` beside a capped ``shown`` and the UI renders "first
200 of 2,057 ... and 1,857 more" (the F46 shape). An API that returned 200 of 2,057 with no total
would be the same silent truncation one layer down.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_app.service.organize import DUPLICATE_SAMPLE_LIMIT, _duplicate_report

# Both surfaces are exercised from one fixture on purpose: the app drifted from the CLI on this
# exact contract, and a test that only ever sees one of them cannot notice that happening again.
from truestill_cli.cli import _format_exact, _format_new
from truestill_core.duplicate_explain import explain_duplicate, origin_phrase
from truestill_core.models import (
    CategoryMatch,
    Confidence,
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    FileHashes,
    Resolution,
)

_MATCHED = "Camera/2014/08/IMG_1234.jpg"


def _resolution(
    name: str, *, exact: DuplicateMatch | None = None, near: DuplicateMatch | None = None
) -> Resolution:
    decision = Decision(
        source=Path(f"/src/{name}"),
        category=CategoryMatch(
            label="Camera", reason="test", confidence=Confidence.MEDIUM, rule="device"
        ),
        captured_at=None,
        date_source=DateSource.NONE,
        date_tag=None,
        relative=Path(f"Camera/{name}"),
    )
    return Resolution(decision, FileHashes("a" * 64, None), exact, near)


def _exact(origin: str = "catalog") -> DuplicateMatch:
    return DuplicateMatch(kind=DuplicateKind.EXACT, matched_path=_MATCHED, origin=origin)


def _near(distance: int = 3, origin: str = "catalog") -> DuplicateMatch:
    return DuplicateMatch(
        kind=DuplicateKind.PERCEPTUAL, matched_path=_MATCHED, origin=origin, distance=distance
    )


# --- the payload names the match ------------------------------------------------------------


def test_an_exact_duplicate_payload_names_what_it_matched() -> None:
    """The defect, as an assertion: the count was there, the identity was not."""
    report = _duplicate_report([_resolution("a.jpg", exact=_exact())], near=False)

    assert report["total"] == 1
    (sample,) = report["shown"]
    assert sample["matched_path"] == _MATCHED, "the app dropped the one field that matters"
    assert sample["name"] == "a.jpg"
    assert sample["kept"] is False
    assert _MATCHED in sample["detail"]


def test_a_near_duplicate_payload_carries_the_distance_and_says_it_was_kept() -> None:
    """A near-duplicate is *kept*. Saying so answers the fear the complaint is really about."""
    report = _duplicate_report([_resolution("b.jpg", near=_near(distance=5))], near=True)

    (sample,) = report["shown"]
    assert sample["distance"] == 5
    assert sample["kept"] is True
    assert "Kept" in sample["detail"]


def test_the_two_origins_are_not_collapsed() -> None:
    """ "Already in your library" and "earlier in this batch" are different facts to a user."""
    from_catalog = _duplicate_report([_resolution("a.jpg", exact=_exact("catalog"))], near=False)
    from_run = _duplicate_report([_resolution("b.jpg", exact=_exact("run"))], near=False)

    assert from_catalog["shown"][0]["origin"] != from_run["shown"][0]["origin"]
    assert from_catalog["shown"][0]["origin"] == "already in your library"
    assert from_run["shown"][0]["origin"] == "earlier in this batch"


def test_no_backend_vocabulary_reaches_the_payload() -> None:
    """(ccc): plain language. "SHA-256 match, origin=catalog" is a sentence for a developer."""
    report = _duplicate_report([_resolution("a.jpg", exact=_exact())], near=False)

    detail = report["shown"][0]["detail"].lower()
    for jargon in ("sha-256", "sha256", "perceptual", "dhash", "origin=", "catalog"):
        assert jargon not in detail, f"backend vocabulary reached the user: {jargon!r}"


# --- truncation is disclosed, never silent --------------------------------------------------


def test_a_long_run_reports_the_total_it_sampled_from() -> None:
    """F46 applied to a payload: a capped list must carry the number it was capped from."""
    many = [_resolution(f"f{i}.jpg", exact=_exact()) for i in range(DUPLICATE_SAMPLE_LIMIT + 57)]

    report = _duplicate_report(many, near=False)

    assert len(report["shown"]) == DUPLICATE_SAMPLE_LIMIT
    assert report["total"] == DUPLICATE_SAMPLE_LIMIT + 57, "the hidden matches were not counted"


def test_a_short_run_is_not_described_as_truncated() -> None:
    """Cry-wolf half: a complete list must read as complete - no "and 0 more" upstream."""
    few = [_resolution(f"f{i}.jpg", exact=_exact()) for i in range(3)]

    report = _duplicate_report(few, near=False)

    assert report["total"] == len(report["shown"]) == 3


def test_a_run_exactly_at_the_limit_is_not_truncated() -> None:
    """The off-by-one the F46 sweep pinned, at the payload layer."""
    exact_limit = [_resolution(f"f{i}.jpg", exact=_exact()) for i in range(DUPLICATE_SAMPLE_LIMIT)]

    report = _duplicate_report(exact_limit, near=False)

    assert report["total"] == len(report["shown"]) == DUPLICATE_SAMPLE_LIMIT


# --- the two surfaces cannot drift again ----------------------------------------------------


@pytest.mark.parametrize("origin", ["run", "catalog"])
def test_both_surfaces_word_the_origin_identically(origin: str) -> None:
    """The CLI report and the app payload take this phrase from the same function.

    Before, each surface wrote its own: the CLI said "seen this catalog", the app said nothing
    at all. A shared home is what makes a second copy impossible rather than merely watched.
    """
    payload = _duplicate_report([_resolution("a.jpg", exact=_exact(origin))], near=False)

    assert payload["shown"][0]["origin"] == origin_phrase(origin)


def test_the_cli_report_still_names_the_match() -> None:
    """The surface that was already correct must stay correct - this fix must not level down."""
    exact_line = _format_exact(_resolution("a.jpg", exact=_exact()))
    assert _MATCHED in exact_line
    assert origin_phrase("catalog") in exact_line

    near_line = _format_new(_resolution("b.jpg", near=_near(distance=4)), "Library")
    assert _MATCHED in near_line
    assert "distance=4" in near_line


def test_the_shared_wording_is_the_only_home() -> None:
    """Anti-vacuity: if `explain_duplicate` stops being used, these tests prove nothing."""
    explanation = explain_duplicate(_exact())
    payload = _duplicate_report([_resolution("a.jpg", exact=_exact())], near=False)

    assert payload["shown"][0]["detail"] == explanation.detail, (
        "the payload is wording matches itself rather than through the shared home"
    )
