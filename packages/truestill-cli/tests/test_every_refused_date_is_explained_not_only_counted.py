"""A date the resolver found and threw away is explained, in every report that counts it. `(akx)`

**The defect, exactly.** A photograph carrying `1899:06:15` is refused and filed under `Undated/`.
The organize summary printed::

    date sources (organized files):
        rejected_early               1
        rejected_future              1
    1 file(s) claimed a capture date in the future; it was refused and they went to Undated/ ...

- a token for the 1899 file and no sentence, beside a sibling with both. The token is already on
screen, so this was never a silence that rarity could excuse: it is a word a user cannot act on.

⚠ **THE CENSUS, AND WHY IT IS DERIVED RATHER THAN LISTED.** The class is *every `DateSource` that
means a date was found and refused* - `REJECTED_*` - and the tests below read that off the enum.
A hand-written list would be a list nobody prunes, which is `test_subcommand_list_mirrors_the_parser`'s
subject; worse, the next refusal added to the enum is exactly the one that would be left off it.

**What the census found besides the 1899 case**, recorded here because a census reported as a
single fix is not a census:

* `date_explain._EXPLANATIONS` covers all ten `DateSource` members today, and **nothing pinned
  that** - `REJECTED_FUTURE` had no entry once and silently fell back to *"Not recorded"*, which
  told the user their date was never noted about a date the product had refused. Pinned below.
* `drive_unwritable._DRIVE_WORDS` and `_FOLDER_WORDS` each cover five of six `Unwritable`
  members. `OTHER` is absent **deliberately** and is not a gap: both readers are
  ``.get(...) or error.strerror``, so an unclassified errno falls through to the operating
  system's own message, which says more than a generic sentence could. Not asserted here; named
  so the next reader does not "fix" it.
* Every other enum-to-prose table in core is complete: `_STATUS_LABELS` 10/10,
  `_UNREADABLE_LABELS` and `_UNREADABLE_REMEDIES` 5/5, `_FOLDER_SKIP_*` 2/2, `_UNCOMPARED_*` 2/2,
  `selfcheck._SEVERITY` and `_MARKS` 5/5.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import _print_date_quality, _print_ingest_report
from truestill_core.date_explain import NOT_RECORDED, explain
from truestill_core.models import (
    CategoryMatch,
    Confidence,
    DateQuality,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
    date_quality,
)
from truestill_core.takeout import TakeoutScan

#: The class, read off the enum. A member whose name says a date was **found and refused** - as
#: opposed to never found (`NONE`) or found and used (everything else).
REFUSALS = tuple(source for source in DateSource if source.name.startswith("REJECTED_"))


def _resolution(source: DateSource, name: str = "a.jpg") -> Resolution:
    decision = Decision(
        source=Path(name),
        category=CategoryMatch(
            label="Saved", confidence=Confidence.LOW, rule="fallback", reason="-"
        ),
        captured_at=None,
        date_source=source,
        date_tag=None,
        relative=Path(f"Saved/Undated/{name}"),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256="0" * 64, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def test_the_class_is_not_empty_and_holds_the_three_it_should() -> None:
    """Without this, every parametrized test below is satisfied by a census that found nothing.

    Named members rather than a count, because the interesting failure is a **renamed** one: a
    `REJECTED_EARLY` that became `TOO_OLD` would leave the prefix search returning two and every
    other test here green about a refusal nobody discloses.
    """
    assert set(REFUSALS) == {
        DateSource.REJECTED_SENTINEL,
        DateSource.REJECTED_FUTURE,
        DateSource.REJECTED_EARLY,
    }


# ------------------------------------------------------------------- counted, one field for each


@pytest.mark.parametrize("source", REFUSALS, ids=lambda s: s.value)
def test_every_refusal_has_its_own_counter(source: DateSource) -> None:
    """Folded together, the tally would say how many files lack a date and hide why.

    One resolution of the refused kind, and exactly one field of `DateQuality` moves - so a
    counter wired to the wrong member fails here rather than reporting a plausible total.
    """
    quality = date_quality([_resolution(source)])
    moved = [field for field in DateQuality._fields if getattr(quality, field) == 1]

    assert len(moved) == 1, f"{source.value} moved {moved} rather than exactly one counter"
    assert date_quality([])._asdict()[moved[0]] == 0, "the counter is not zero for no files"


def test_a_refusal_never_lands_in_the_plain_undated_count() -> None:
    """`still undated` counts `DateSource.NONE` alone, and that is the whole reason these exist."""
    quality = date_quality([_resolution(source) for source in REFUSALS])

    assert quality.sentinel_rejected == 1
    assert quality.future_rejected == 1
    assert quality.early_rejected == 1
    assert quality.suspect_default == 0


# --------------------------------------------------------------------- explained, in both reports


@pytest.mark.parametrize("source", REFUSALS, ids=lambda s: s.value)
def test_every_refusal_gets_a_sentence_in_the_organize_summary(
    source: DateSource, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sentence, named as *a date was found and refused* and *where the file went*.

    ⚠ **Asserted on meaning rather than on wording**, because pinning the exact string would
    make this a change-detector for prose and it would be deleted the first time somebody
    improved a sentence. What must hold is that the user is told a date was refused, and where
    the file is now - which is the pair the token alone cannot give them.
    """
    _print_date_quality([_resolution(source)])
    out = capsys.readouterr().out

    assert out.strip(), f"{source.value} is counted and never described"
    assert "refused" in out
    assert "Undated/" in out


def test_the_organize_summary_says_nothing_when_nothing_was_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The cry-wolf half: each line prints only when non-zero, so a clean run stays clean.

    Without this, a `_print_date_quality` that printed all three sentences unconditionally would
    satisfy every assertion above while telling a user with perfect dates that dates were refused.
    """
    _print_date_quality([_resolution(DateSource.EXIF)])
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("source", REFUSALS, ids=lambda s: s.value)
def test_the_import_report_accounts_for_every_refusal_as_its_own_row(
    source: DateSource, capsys: pytest.CaptureFixture[str]
) -> None:
    """`TAKEOUT RESCUE REPORT` is read as an account of every kept file, and it was not one.

    ⚠ **This is worse than the organize case and was found by the same census.** That report's
    date rows are unconditional and `still undated` counts `NONE` alone, so a file refused for a
    pre-1900 date appeared in `kept` and in **no** date row at all - absent rather than merely
    unexplained. The assertion is arithmetic: the date rows must sum to what was kept.
    """
    _print_ingest_report([_resolution(source)], TakeoutScan())
    rows = {
        line.split(":")[0].strip(): int(line.split(":")[1].strip().split()[0])
        for line in capsys.readouterr().out.splitlines()
        if ":" in line and line.startswith("  ") and line.split(":")[1].strip()[:1].isdigit()
    }

    assert rows["kept (unique + look-alikes)"] == 1
    dated = sum(
        count
        for label, count in rows.items()
        if label.startswith("dates ") or label.endswith("refused") or label == "still undated"
    )
    assert dated == 1, f"{source.value} is kept and appears in no date row: {rows}"


# ----------------------------------------------- and the table that fell back silently once before


@pytest.mark.parametrize("source", list(DateSource), ids=lambda s: s.value)
def test_every_date_source_has_its_own_explanation_in_the_library_view(
    source: DateSource,
) -> None:
    """`explain` falls back to *"Not recorded"* for anything it does not know, and says nothing.

    ⚠ **That fallback is right for a catalog written by a NEWER build** - a display path must not
    break the screen describing it - and it is exactly wrong for a member of the enum this build
    already has. `REJECTED_FUTURE` sat in that hole once: the product refused a date and then told
    the user their date had simply never been noted. Nothing pinned it until now.
    """
    found = explain(source.value)

    assert found is not NOT_RECORDED, f"{source.value} falls back to the unknown-source sentence"
    assert found.label
    assert found.detail


# ------------------------------------------------------------------- and the app's half of it


def test_the_app_discloses_every_refusal_the_cli_does() -> None:
    """⚠ **The anti-drift assertion**, the shape `(aku)` set and `(akw)` reused.

    A refusal disclosed in the terminal and silent in the browser is a catalog that means
    different things depending on which window the user had open. The app's preview island is
    TypeScript, so nothing in `make check` type-checks it and no browser test renders a 1899
    file - which is precisely why the pairing is asserted from the source rather than assumed.

    Derived from `DateQuality`'s own fields, so the next refusal added there fails here until
    the island learns to say it.
    """
    root = Path(__file__).resolve().parents[3]
    island = (root / "packages/truestill-app/frontend/src/preview.tsx").read_text(encoding="utf-8")
    payload = (root / "packages/truestill-app/src/truestill_app/service/organize.py").read_text(
        encoding="utf-8"
    )

    counters = [f for f in DateQuality._fields if f.endswith("_rejected")]
    assert len(counters) == len(REFUSALS), "a refusal has no counter, or a counter has no refusal"
    for field in counters:
        assert f'"{field}": quality.{field},' in payload, f"{field} never reaches the wire"
        # ⚠ **The BRANCH, not a mention of the field.** A first draft asserted `s.<field>`
        # appeared anywhere, and a mutation that changed the guard to `if (false)` survived it -
        # the count was still interpolated inside a block that no longer ran.
        assert f"if (s.{field}) {{" in island, f"{field} is counted, sent, and never drawn"


def test_an_unknown_stored_source_still_falls_back_rather_than_raising() -> None:
    """The other half of the same table: a catalog from a newer build must not break the screen."""
    assert explain("a_source_this_build_has_never_heard_of") is NOT_RECORDED
    assert explain(None) is NOT_RECORDED
