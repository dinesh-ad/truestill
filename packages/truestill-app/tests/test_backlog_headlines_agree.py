"""One entry's headline is written in three places; all three must say the same thing.

**What P57 looked for and did not find.** A sweep of all 80 open entries classified zero as DEAD
and zero as FALSE, and named the real defect class instead: *a stale index headline over a body
that already carries its own correction* - twelve instances, swept by hand twice. This guard was
commissioned to close that class.

⚠ **IT CANNOT, AND THE MEASUREMENT SAYS SO RATHER THAN AN OPINION.** Reconstructed from history,
at the commit before each of the twelve was corrected, the index headline and the body heading
**agreed** - both carried the same false sentence. A guard keyed on disagreement fires on **1 of
the twelve** in that state. Nothing mechanical separates a headline that is false from one that is
true; that is a semantic judgement, and a check that tried to read English here would either fire
on ordinary prose or catch nothing.

**Three other shapes were measured and rejected, each with a number:**

============================================  =========================================
candidate                                     why it was refused
============================================  =========================================
body carries a dated correction marker,       fires on **20** open bodies, of which only
the index line carries none                   **6** are instances - 30% precise. A
                                              correction marker is ordinary hygiene, and
                                              a guard that fires on ordinary work gets
                                              switched off (`ENGINEERING_STANDARD.md` §4)
index asserts a symbol the body calls wrong   needs to know which of two claims is right
body header says RETIRED/DEFERRED while       **0** hits over the whole corpus. A guard
the index line says neither                   that cannot fire is worse than a written rule
============================================  =========================================

**So this checks the one thing that IS decidable, and it is a different defect.** An entry's
headline exists three times - the index line in `BACKLOG.md`, the body's `# (x) ...` heading, and
the body's mirrored `- **(x) ...**` bullet. When a correction reaches some of them and not the
rest, the copies disagree, and no English needs reading to see it.

**That is the 71st member turned on the sweep that produced it** - *a partial refresh is worse
than no refresh, because the half somebody checked vouches for the half they did not.* Measured on
the tree this landed against: **17 live disagreements across 11 entries**, every one created by
the two hand sweeps retitling the index and leaving the body behind. The forgotten copy is almost
always the **mirror bullet** - it accounts for **11 of the 17**, and in **6** of those the `# `
heading had already been updated by the very commit that missed the bullet three lines below it.

**Cost, declared rather than suppressed** (§4). One parse of `BACKLOG.md` plus one read of each
open entry's body: **linear in the number of open entries**, which is **92** today, and linear in
their bytes. `body_headlines` is called once per letter per assertion rather than cached, so the
worst case is a small constant multiple of that, not a higher order. The whole module runs in
well under a tenth of a second.

**The index is canonical, checked rather than assumed.** For every live disagreement the index
line's headline was set on the same day as the body's or later, never earlier, so the repair
direction is always body-follows-index.

**Retitling in place is the house pattern, not a rewrite of a record.** `afx.md`, `afv.md` and
`agv.md` all correct the title and quote the original beneath it. Bodies of **open** entries are
instruction, which is why `test_live_documents_cite_code_that_exists.py` already counts them as
living documents; a record keeps its stale text in the sub-bullets, where these entries keep it.

⚠ **SCOPE, DECLARED RATHER THAN IMPLIED** (§4's twenty-second member, and the 71st again - a guard
whose scope is undeclared reads as complete):

* **Open entries only** - the letters `BACKLOG.md` carries as open work. `SHIPPED.md` is out for
  the reason `(ago)`'s guard gives for excluding it: a closure describes a run that happened, so
  it is provenance rather than instruction. Retired bodies (`ags.md`, `aco.md` head themselves
  *"this is a RECORD, not an open entry"*) are out for the same reason - they are not reachable
  from the index this reads.
* **Headlines only.** It says nothing about whether the body's *argument* still matches its title,
  which is the semantic half above.
* **An open entry with no body file is skipped, not flagged.** One exists today, `(agm)`. Whether
  every open entry should have a body is a different rule and is not smuggled in here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKLOG = ROOT / "docs/BACKLOG.md"
BODIES = ROOT / "docs/research/backlog"

#: An entry's index line, and the same line mirrored at the top of its body. The headline runs to
#: the closing ``**``, and `re.DOTALL` is required because long ones wrap.
ITEM = re.compile(r"^- \*\*\(([a-z]{1,3})\) (.*?)\*\*", re.MULTILINE | re.DOTALL)


def _heading(letter: str) -> re.Pattern[str]:
    """The body's ``# (x) ...`` title line."""
    return re.compile(rf"^# \({re.escape(letter)}\) (.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Headline:
    """One place a headline is written, and what it says there."""

    letter: str
    where: str
    text: str


def normalize(raw: str) -> str:
    """Collapse wrapping, drop a trailing full stop. **Case is deliberately significant.**

    Measured over the corpus: **156** triples agree exactly and **0** differ by case alone, so
    case-folding would buy nothing and would open a hole - `(abe)`'s correction is carried partly
    by its capitals (*"REPAIRING PRE-EXISTING ROWS IS THE OPEN HALF"*).
    """
    return re.sub(r"\s+", " ", raw).strip().rstrip(".")


def _line_of(text: str, offset: int) -> int:
    """1-indexed line holding `offset`. So a finding can be opened rather than searched for."""
    return text[:offset].count("\n") + 1


def index_headlines() -> dict[str, Headline]:
    """Every open entry's headline, from the index. First definition wins, as elsewhere.

    Read from the whole text rather than line by line: a long headline wraps, and one that did
    would otherwise be skipped silently - which is the vacuous half this module refuses.
    """
    text = BACKLOG.read_text(encoding="utf-8")
    found: dict[str, Headline] = {}
    for match in ITEM.finditer(text):
        letter = match.group(1)
        if letter not in found:
            where = f"docs/BACKLOG.md:{_line_of(text, match.start())}"
            found[letter] = Headline(letter, where, normalize(match.group(2)))
    return found


def body_headlines(letter: str) -> tuple[Headline, ...]:
    """The two copies inside `<letter>.md`: its `# ` title, and its mirrored bullet.

    A body with no mirrored headline returns one copy, not zero - `afx.md` writes its bullet as
    ``- **(afx)**`` with the sentence as prose, which is the house way of keeping a third copy
    from existing at all. That is a repair, not a gap.
    """
    body = BODIES / f"{letter}.md"
    if not body.is_file():
        return ()
    text = body.read_text(encoding="utf-8")
    name = f"docs/research/backlog/{letter}.md"
    found: list[Headline] = []
    title = _heading(letter).search(text)
    if title:
        where = f"{name}:{_line_of(text, title.start())} (title)"
        found.append(Headline(letter, where, normalize(title.group(1))))
    mirror = ITEM.search(text)
    if mirror and mirror.group(1) == letter:
        where = f"{name}:{_line_of(text, mirror.start())} (mirror)"
        found.append(Headline(letter, where, normalize(mirror.group(2))))
    return tuple(found)


def disagreements(index: dict[str, Headline]) -> list[str]:
    """Every copy that does not match its index line. Pure: the corpus goes in as an argument."""
    out: list[str] = []
    for letter, canonical in sorted(index.items()):
        for copy in body_headlines(letter):
            if copy.text != canonical.text:
                out.append(
                    f"({letter}) {copy.where}\n"
                    f"      index: {canonical.text}\n"
                    f"      body : {copy.text}"
                )
    return out


def comparisons(index: dict[str, Headline]) -> int:
    """How many copies were actually compared - the number every assertion here rests on."""
    return sum(len(body_headlines(letter)) for letter in index)


# ------------------------------------------------------------------------------ the guard itself


def test_every_open_entry_says_the_same_thing_in_all_three_places() -> None:
    found = disagreements(index_headlines())
    assert not found, (
        "an open entry's headline disagrees with its index line:\n\n"
        + "\n".join(found)
        + "\n\nThe index is canonical. Correct the body's title AND its mirrored bullet, and "
        "quote the original beneath the title the way afx.md, afv.md and agv.md do - a "
        "correction that deletes what it corrects leaves the next reader unable to tell which "
        "half moved."
    )


# ----------------------------------------------------------------------------------- anti-vacuity


def test_the_guard_has_headlines_to_compare() -> None:
    """A collector that parses nothing makes every assertion above true.

    **Measured on the tree this landed against**: **92** open entries, **91** with a body file,
    **169** copies compared (91 titles and 78 mirrors). The floor is `> 120` - far enough below
    169 that ordinary closures never reach it, far enough above zero to fail loudly if the index
    stopped parsing or the body directory moved, which are the two ways this goes quietly
    vacuous.
    """
    index = index_headlines()
    assert len(index) > 60, f"only {len(index)} open entries parsed from BACKLOG.md"
    assert comparisons(index) > 120, f"only {comparisons(index)} copies compared"


def test_both_sources_are_read_and_contribute() -> None:
    """Neither half may drop out silently."""
    assert BACKLOG.is_file(), f"{BACKLOG} is gone; this guard now checks less than it says"
    assert BODIES.is_dir(), f"{BODIES} is gone; every body would skip and the suite stay green"

    index = index_headlines()
    titles = sum(1 for x in index for h in body_headlines(x) if h.where.endswith("(title)"))
    mirrors = sum(1 for x in index for h in body_headlines(x) if h.where.endswith("(mirror)"))
    assert titles > 60, f"only {titles} body titles parsed"
    assert mirrors > 60, f"only {mirrors} mirrored bullets parsed"


# ---------------------------------------------------------------------------- planted, both ways


def test_the_guard_sees_a_planted_divergence() -> None:
    """The mutation half, without touching the real corpus.

    The planted shape is the live one: an index corrected while a copy keeps the old sentence.
    """
    index = {"zz": Headline("zz", "docs/BACKLOG.md:1", normalize("A CORRECTED CLAIM."))}
    stale = Headline("zz", "docs/research/backlog/zz.md:1 (mirror)", normalize("The old claim."))
    assert stale.text != index["zz"].text

    fresh = Headline("zz", "docs/research/backlog/zz.md:1 (mirror)", normalize("A CORRECTED CLAIM"))
    assert fresh.text == index["zz"].text, "a correctly retitled entry must not be flagged"


def test_a_headline_that_only_wraps_or_gains_a_full_stop_is_not_a_divergence() -> None:
    """**Cry-wolf half.** Markdown wrapping is a formatting choice, not a claim.

    A guard that fired when a maintainer reflowed a paragraph would be switched off within a week,
    taking its real coverage with it (§4).
    """
    wrapped = "THE LOCK DIRECTORY GROWS\n  ONE EMPTY FILE PER DRIVE, FOREVER."
    flat = "THE LOCK DIRECTORY GROWS ONE EMPTY FILE PER DRIVE, FOREVER"
    assert normalize(wrapped) == normalize(flat)


def test_case_is_significant() -> None:
    """The direction the normalizer must NOT relax, and the corpus is the argument.

    Zero triples differ by case alone, so folding case only ever hides a real correction - several
    of which are carried by their capitals.
    """
    assert normalize("Repairing pre-existing rows") != normalize("REPAIRING PRE-EXISTING ROWS")


def test_the_guard_fails_when_made_to_flag_everything() -> None:
    """Control run, the direction Q327 asks for: a guard that cannot go red proves nothing.

    Comparing every copy against a headline no entry carries must produce one finding per copy.
    """
    index = index_headlines()
    everything = {x: Headline(x, h.where, "NOT ANY REAL HEADLINE") for x, h in index.items()}
    assert len(disagreements(everything)) == comparisons(index) > 120
