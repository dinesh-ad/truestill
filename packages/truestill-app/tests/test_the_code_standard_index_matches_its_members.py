"""`ENGINEERING_STANDARD.md` §4's index says exactly what its members say, in their order.

**An index is a second copy, and this repo's whole history with second copies is that they rot.**
The counts beside §4 alone went stale three times in eight days - 68 recorded, 76 a week later
while the 68 stood beside it as though current, 86 today - and that is a single integer. An
86-line list restating 86 headlines would rot faster and less visibly, because a reader who finds
the line they want never learns the member was reworded underneath it.

⚠ **So the index is only defensible because it is DERIVED and this test holds it derived.** It
fails when a member is added, removed, reworded or reordered without the index following. That is
the difference between this guard and the map-completeness census refused in the same session
(P209): `(ago)`'s bar is that a guard must earn itself, and a census that is green on the day it
is written over a class nothing has ever broken earns nothing - while this one guards a copy that
was created on the day it was written and would otherwise have no protection at all.

**What it deliberately does NOT check.** That the headline is a *good* summary of its member, or
that the member still earns its place - both are human rulings and §4 says so itself. This
asserts equality of text, which is the whole of what a machine can hold.

**Why not simply generate the index at build time?** There is no build step for a markdown
document here, and adding one would put the canon behind a tool. A checked-in copy with a guard
is the same trade `openapi.json` and `api.d.ts` already make in this repo: derived, committed,
and red on drift.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STANDARD = ROOT / "docs/ENGINEERING_STANDARD.md"

_SECTION_START = "## 4. Code standard"
_SECTION_END = "## 5. "
_INDEX_HEADING = "### The members at a glance"

#: A member opens with its headline in bold. `re.DOTALL` because a long one wraps across lines -
#: the same reason `test_backlog_headlines_agree.py` reads the whole text rather than line by line.
_MEMBER = re.compile(r"^- \*\*(.*?)\*\*", re.MULTILINE | re.DOTALL)


def _section() -> str:
    text = STANDARD.read_text(encoding="utf-8")
    start = text.index(_SECTION_START)
    return text[start : text.index(_SECTION_END, start)]


def _flat(raw: str) -> str:
    """Collapse wrapping. An index line wraps at a different column from its member's headline,
    so comparing anything but the flattened text would fail on layout rather than on content."""
    return re.sub(r"\s+", " ", raw).strip()


def member_headlines(section: str) -> list[str]:
    """Every member's opening sentence, in document order."""
    return [_flat(m) for m in _MEMBER.findall(section)]


def index_entries(section: str) -> list[str]:
    """Every line of the index block, unwrapped.

    Bounded by the index heading and the first member, so the surrounding prose - which contains
    no list of its own - cannot leak in and no member can be mistaken for an index entry: a member
    starts ``- **`` and an entry starts ``- `` followed by anything else.
    """
    start = section.index(_INDEX_HEADING)
    end = section.index("\n- **", start)
    entries: list[str] = []
    for line in section[start:end].split("\n"):
        if line.startswith("- "):
            entries.append(line[2:])
        elif line.startswith("  ") and entries:
            entries[-1] += " " + line.strip()
    return [_flat(e) for e in entries]


def test_the_index_lists_every_member_in_order_and_says_what_they_say() -> None:
    """One assertion, because the failure is always "these two lists differ" and splitting it
    into add/remove/reorder cases would report three symptoms of one cause."""
    section = _section()
    members = member_headlines(section)
    entries = index_entries(section)

    assert entries == members, (
        "§4's index no longer matches its members. Regenerate it from the members - the index is "
        "derived, never edited by hand:\n"
        f"    index has {len(entries)} entries, §4 has {len(members)} members\n"
        + "\n".join(
            f"    line {i + 1}: index {e!r}\n              member {m!r}"
            for i, (e, m) in enumerate(zip(entries, members, strict=False))
            if e != m
        )
    )


def test_the_guard_has_both_lists_to_compare() -> None:
    """The cry-wolf half. Two empty lists are equal, so without this the test above passes when
    either parser stops matching - the vacuous green §4's own members are largely about."""
    section = _section()

    assert len(member_headlines(section)) > 50, "the member parser stopped matching"
    assert len(index_entries(section)) > 50, "the index parser stopped matching"


def test_the_guard_sees_a_reworded_member() -> None:
    """Proved by mutation: a member reworded without the index following is the exact drift this
    exists to catch, and it is the one a reader would never notice."""
    section = _section()
    victim = member_headlines(section)[0]
    mutated = section.replace(f"- **{victim}**", "- **A REWORDED MEMBER.**", 1)

    assert index_entries(mutated) != member_headlines(mutated), (
        "rewording a member left the two lists equal - the guard is not comparing what it thinks"
    )
