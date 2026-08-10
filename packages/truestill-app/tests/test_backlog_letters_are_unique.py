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
