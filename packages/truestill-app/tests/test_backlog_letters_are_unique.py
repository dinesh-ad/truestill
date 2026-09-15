"""One letter, one item. `BACKLOG.md` and `SHIPPED.md` share a single namespace.

**Why this exists.** Between 2026-08-08 and 2026-08-10, five letters were each assigned twice -
`(abv)`, `(abw)`, `(abx)`, `(aby)`, `(abz)` - and citations stopped resolving: three were cited
by name in `decisions-on-drive-research.md` and one in `SHIPPED.md`. `BACKLOG.md`'s *Item
letters* section already carried the rule, an allocation line recording the next free letter, and
a warning that `(u)` and `(v)` had been taken twice before. All of it was there. None of it ran.

The fifth collision was invisible for two days because the two entries sat in **different
files**, and surfaced only when one was moved. That is the argument for checking both files as
one namespace rather than each on its own.

**What counts as a declaration, and why the obvious wider patterns were refused.** A letter is
declared when it is the FIRST thing in a top-level entry's title - `- **(abc) Title.**`. Two
wider rules were measured against the real documents and both fail:

* *A letter anywhere after `- **`* (the pattern `test_backlog_references.py` uses for its own,
  more forgiving purpose) reports **4 duplicates, all false** - the Converged-programs bullets
  cite letters after their titles, and the pattern cannot tell a citation from a declaration.
* *A letter anywhere inside the bold title* reports **3 duplicates, all false** - an entry may
  legitimately cite another inside its own title, and one does: `(acg)`'s title reads
  *"the same class as `(ack)`, waiting"*.

**The residual gap, measured rather than waved at.** Seven letters are declared mid-title instead
- `(l)`, `(aav)`, `(aah)`, `(aaj)`, and `(rr)`/`(zz)`/`(eee)` sharing one provenance entry - and
this guard does not see them, so it would not catch a line-initial entry reusing one of those.
That is 7 of 106. The alternative was three or four false positives on day one, and
`ENGINEERING_STANDARD.md` §4 is explicit that a check firing on ordinary work gets switched off
and takes its real signal with it. A narrow guard that runs beats a broad one that gets disabled.

**The other half of the obvious design was refused outright: "every cited letter has an entry".**
It sounds like the natural sibling and it is not viable. Measured on the real documents, **8
cited letters resolve to no line-initial entry and all 8 are legitimate**: `(e)` and `(h)` are
named in *Item letters* as retired-not-free, `(rr)` and `(zz)` are recorded in `SHIPPED.md` as
*"closed as this - do not treat as separate open work"*, and `(aah)`, `(aaj)`, `(aav)`, `(o)` are
cited in prose or declared mid-title. Shipping it would mean eight false positives immediately.
Making it viable needs a curated retired-letters list, which is a second thing to remember to
update - the exact failure this guard exists to remove. **It was refused on measurement, not
forgotten; do not add it without re-running those numbers.**
"""

from __future__ import annotations

import collections
import re
import string
from pathlib import Path

_DOCS = Path(__file__).resolve().parents[3] / "docs"
_SOURCES = (_DOCS / "BACKLOG.md", _DOCS / "SHIPPED.md")

#: A top-level entry declaring its letter first. `~~` allows the struck-through form
#: `SHIPPED.md` uses for delivered items.
_DECLARATION = re.compile(r"^- (?:~~)?\*\*\((aa[a-z]|[a-z]{1,3})\)")


def _declarations(sources: tuple[Path, ...] = _SOURCES) -> dict[str, list[str]]:
    """Every letter declared, and where. Both files, because they are one namespace."""
    found: dict[str, list[str]] = collections.defaultdict(list)
    for path in sources:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = _DECLARATION.match(line)
            if match:
                found[match.group(1)].append(f"{path.name}:{number}")
    return found


def test_no_letter_names_two_items() -> None:
    """The rule. It would have failed on 2026-08-08, four days and five collisions before a
    human noticed, and the citations it protects had already broken by then."""
    duplicates = {letter: places for letter, places in _declarations().items() if len(places) > 1}
    assert not duplicates, (
        f"these letters each name more than one item: {duplicates}. A letter is a permanent "
        f"identifier - the EARLIER entry keeps it and the later one is reallocated from "
        f"BACKLOG.md's 'Next free'. Update every citation, and check which item each one meant."
    )


def test_the_guard_sees_a_planted_duplicate(tmp_path: Path) -> None:
    """The cry-wolf half. Without it, a matcher that silently matches nothing reports a healthy
    namespace forever - and it would have done exactly that all through the week the collisions
    were being introduced.
    """
    planted = tmp_path / "planted.md"
    planted.write_text(
        "- **(zzz) One item.**\n"
        "  - a sub-bullet mentioning `(zzz)` which must not count\n"
        "- **(zzz) A different item with the same letter.**\n",
        encoding="utf-8",
    )
    assert _declarations((planted,))["zzz"] == ["planted.md:1", "planted.md:3"]


def test_the_guard_does_not_count_a_citation_as_a_declaration(tmp_path: Path) -> None:
    """The false positives that decided this guard's shape, as a fixture.

    Both wider patterns considered would fail here, and both were measured failing on the real
    documents. Line 2 is a Converged-programs bullet citing two letters; line 3 is an entry whose
    own title cites another item, which `(acg)`'s really does.
    """
    fixture = tmp_path / "citations.md"
    fixture.write_text(
        "- **(abc) A real entry.**\n"
        "- **A program bundling several items.** `(abc)` and `(def)` are built; the rest is not.\n"
        "- **(ghi) An entry that cites `(abc)` inside its own title.** Body.\n",
        encoding="utf-8",
    )
    found = _declarations((fixture,))
    assert sorted(found) == ["abc", "ghi"]
    assert found["abc"] == ["citations.md:1"], "a citation was counted as a declaration"


def test_both_files_contribute() -> None:
    """One namespace across two files, and the fifth collision spanned them - a per-file check
    would have reported a clean namespace while `(abv)` named two different items."""
    per_file = collections.Counter(
        place.split(":")[0] for places in _declarations().values() for place in places
    )
    assert per_file["BACKLOG.md"] > 10
    assert per_file["SHIPPED.md"] > 10


def test_the_allocation_line_does_not_point_at_a_taken_letter() -> None:
    """*Item letters* records the next free letter by hand, and a stale line hands the next
    person a letter already spoken for - one of the ways this went wrong.

    The check is deliberately narrow: **is the letter it offers already declared?** A stronger
    "is it ahead of everything taken" was written first and thrown away, because it assumed one
    ordered sequence and the namespace has two - `(aaa)`, `(bbb)`-`(fff)` alongside
    `(aab)`-`(ack)` - so `fff > acl` lexicographically while meaning nothing. A guard encoding a
    model of the data that is not true is a guard that fails on correct work.
    """
    text = (_DOCS / "BACKLOG.md").read_text(encoding="utf-8")
    match = re.search(r"Next free: \((\w+)\)", text)
    assert match, "the allocation line is gone - Item letters no longer records a next free letter"

    free = match.group(1)
    declared = _declarations()
    assert free not in declared, (
        f"'Next free: ({free})' points at a letter already declared at {declared[free]}. "
        f"Advance the allocation line before assigning."
    )


# ---------------------------------------------------- the allocation line's OTHER half, `(akv)`

#: `Used: (e)-(z), (aa)-(zz), (aaa), (bbb)-(fff), (aab)-(aku).` - a single letter, or a range.
#: The separator is a hyphen or an en dash, because the line has been written with both.
_SPAN = re.compile("\\((\\w+)\\)(?:\\s*[-\u2013]\\s*\\((\\w+)\\))?")

#: The sequence letters are currently being drawn from. Held as a constant so that rolling past
#: it fails `test_the_frontier_is_still_the_sequence_this_guard_models` loudly, rather than
#: leaving these checks silently measuring a sequence nobody uses any more.
_FRONTIER = "a"


def _used_spans(text: str) -> list[tuple[str, str]]:
    """The `Used:` line, as (first, last) pairs. A bare `(aaa)` is a span of one."""
    line = re.search(r"\*\*Used: (.+?)\. Next free", text)
    assert line, "the allocation line no longer states what is used"
    return [(a, b or a) for a, b in _SPAN.findall(line.group(1))]


def _covered(letter: str, spans: list[tuple[str, str]]) -> bool:
    """A span covers a letter of its own width, between its ends inclusive.

    ⚠ **Width is part of the test, and that is what makes this safe.** Comparing `fff` with `akv`
    as strings is the mistake that got the first version of this guard thrown away - it assumed
    one ordered sequence where the namespace has several. Within a width the order is real.
    """
    return any(len(letter) == len(first) and first <= letter <= last for first, last in spans)


def test_every_letter_in_use_falls_inside_the_used_line() -> None:
    """⚠ **THE HALF THAT WAS STRUCTURALLY BLIND, AND IT HAS NOW FIRED TWICE IDENTICALLY.**

    `test_the_allocation_line_does_not_point_at_a_taken_letter` asks only whether the offered
    letter is spoken for. Both real failures were in the OTHER half of the same sentence: the
    `Used:` range went stale while the pointer stayed honest.

    * `(akk)` stood as next free while `(akl)`-`(akp)` were filed past it - five entries.
    * `(akq)` stood as next free while `(akr)`-`(aku)` were filed past it - four entries, and
      the second one wrote into the paragraph that recorded the first.

    Nothing reported either. The range is a claim about the whole namespace, so it is the half a
    reader trusts when deciding what is already taken, and it is checkable in one line: **no
    declared letter may sit outside it.** `(ago)`'s bar is two instances; this is the second.
    """
    spans = _used_spans((_DOCS / "BACKLOG.md").read_text(encoding="utf-8"))
    outside = {
        letter: places
        for letter, places in sorted(_declarations().items())
        if not _covered(letter, spans)
    }
    assert not outside, (
        f"the 'Used:' range does not cover these declared letters: {outside}. Extend it in the "
        f"same commit that declares them - the range is what the next person reads to decide "
        f"what is taken, and a range four letters behind the tree reads exactly like a current one."
    )


def test_the_next_free_letter_is_the_lowest_one_the_used_line_leaves() -> None:
    """**The pointer, strengthened from *not taken* to *the lowest not taken*.**

    ⚠ **IT IS COMPUTED FROM THE RANGES, NEVER FROM THE DECLARATIONS, and that is not a shortcut.**
    Measured on the real documents: eight letters inside the `a??` range have no visible
    declaration, and **every one of them is legitimately unavailable** - `(aah)`, `(aaj)` and
    `(aav)` are declared mid-title where this file's parser cannot see them, and `(abh)`,
    `(abp)`, `(abz)`, `(aco)` and `(ags)` are **retired**, which *Item letters* is explicit about:
    *"a retired letter is not a free one."* A lowest-free check reading declarations would offer
    `(abh)` on its first run. The `Used:` line is the document's own claim and already accounts
    for both kinds, which is why it is the thing to measure against - and why the test above,
    which keeps that claim honest, is the one this one rests on.
    """
    text = (_DOCS / "BACKLOG.md").read_text(encoding="utf-8")
    spans = _used_spans(text)
    match = re.search(r"Next free: \((\w+)\)", text)
    assert match, "the allocation line is gone - Item letters no longer records a next free letter"

    width = max(len(first) for first, _ in spans)
    lowest = next(
        candidate
        for candidate in (
            _FRONTIER + a + b for a in string.ascii_lowercase for b in string.ascii_lowercase
        )
        if not _covered(candidate, spans)
    )
    assert len(lowest) == width, "the frontier sequence and the widest span disagree"
    assert match.group(1) == lowest, (
        f"'Next free: ({match.group(1)})' is not the lowest letter the 'Used:' line leaves free, "
        f"which is ({lowest}). Advancing the range without advancing the pointer leaves it "
        f"offering a letter the same sentence has just claimed is taken."
    )


def test_the_frontier_is_still_the_sequence_this_guard_models() -> None:
    """⚠ **THE MODEL CHECKING ITSELF**, which is the guard the thrown-away first attempt lacked.

    Both tests above assume letters are currently drawn from `a??`. That is true today and will
    stop being true at `(azz)`. When it does, this fails and names its own assumption, rather than
    the two above quietly measuring a sequence nobody is allocating from.

    ⚠ **The frontier is the LAST span, never the highest letter**, and writing it the other way
    is how this test failed on its first run: `fff` sorts above `aku`, so "the highest declared
    letter" picks the historical `(bbb)`-`(fff)` family rather than the one allocation advances.
    That is the same wrong model that got the first attempt at this guard thrown away, met again
    four lines into rebuilding it.
    """
    first, last = _used_spans((_DOCS / "BACKLOG.md").read_text(encoding="utf-8"))[-1]
    moved = f"allocation has moved on to ({first})-({last}), outside the ({_FRONTIER}??) sequence"
    hint = "these checks model. Move _FRONTIER on, and re-read what 'lowest free' means there."
    assert first.startswith(_FRONTIER), f"{moved} {hint}"
    assert last.startswith(_FRONTIER), f"{moved} {hint}"


def test_the_used_line_guard_sees_a_letter_filed_past_it() -> None:
    """The cry-wolf half, and it reproduces the real failure rather than a synthetic one: a
    pointer that is still honest beside a range that is four letters behind."""
    stale = "**Used: (aab)-(akp). Next free: (akq).**"
    spans = _used_spans(stale)

    assert _covered("akp", spans)
    assert not _covered("aku", spans), "the stale range wrongly covers a letter filed past it"
    assert not _covered("akq", spans), "the pointer would have passed the old guard, and did"


def test_the_lowest_free_guard_sees_a_pointer_left_behind() -> None:
    """The other real shape: someone extends the range and forgets the pointer, so the sentence
    claims `(aku)` is used and offers `(akq)` in the same breath."""
    spans = _used_spans("**Used: (aab)-(aku). Next free: (akq).**")

    assert _covered("akq", spans), "a pointer inside the range is exactly the contradiction"
    assert not _covered("akv", spans)
