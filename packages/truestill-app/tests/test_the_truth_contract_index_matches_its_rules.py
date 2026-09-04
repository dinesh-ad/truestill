"""`IMPLEMENTATION_STANDARDS.md` §9's index says exactly what its rows say, in their order.

**The sibling of `test_the_code_standard_index_matches_its_members.py`, and the argument is the
same one.** An index is a second copy; second copies rot here; a derived copy with a guard is the
trade this repo already makes for `openapi.json` and `api.d.ts`. Without this test the index would
be 48 restatements drifting quietly out from under the rows they name, and a reader who finds the
line they want never learns the row was reworded.

⚠ **§9 IS THE ONLY SECTION OF THE BINDING CONTRACT READ ON DEMAND, AND THE MEASUREMENT IS WHY**
(P210). It is the largest single block in the mandated read at 61,272 bytes, it is the only
genuinely task-scoped section - every row fires when a user-facing string changes - and **47 of
its 48 rows name a `test_` that resolves, against 31% for `ENGINEERING_STANDARD.md` §4** - the
forty-eighth delegates per-feature.
The rule that licenses the move is that a rule may be read on demand exactly when something
mechanical, not the reading, enforces it. **Had the census come back at 31%, the section would
still be read in full.**

⚠ **SCOPED TO §9 DELIBERATELY.** Seventy-seven rows in this document open with ``| **`` and only
forty-eight are §9's - §1 and §3 carry tables of their own. A guard that read the file rather than
the section would compare the index against rules it was never about, and would have been red on
the day it was written for the wrong reason.

**What it does not check**: that a lead is a *good* handle for its row, or that the rule is still
right. Both are human rulings. This asserts equality of text, which is the whole of what a machine
can hold.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "docs/IMPLEMENTATION_STANDARDS.md"

_SECTION = "## 9. User-facing truth contract"
_INDEX_HEADING = "### The rules at a glance"
_TABLE = "| Rule | Enforced by |"

#: A rule row opens with its statement in bold, in the table's first cell.
_ROW = re.compile(r"^\| \*\*(.*?)\*\*", re.MULTILINE | re.DOTALL)


def _section() -> str:
    """§9 alone. It is the last section today, so the end is the file - found by looking for a
    following ``## `` rather than assumed, because a tenth section would silently widen this."""
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index(_SECTION)
    nxt = text.find("\n## ", start + len(_SECTION))
    return text[start:] if nxt < 0 else text[start:nxt]


def _flat(raw: str) -> str:
    """Collapse wrapping: an index line wraps at a different column from its row."""
    return re.sub(r"\s+", " ", raw).strip()


def rule_leads(section: str) -> list[str]:
    """Every row's opening rule, in table order."""
    table = section[section.index(_TABLE) :]
    return [_flat(m) for m in _ROW.findall(table)]


def index_entries(section: str) -> list[str]:
    """Every line of the index block, unwrapped.

    Bounded by the index heading and the table, so the explanatory prose above cannot leak in and
    no table row can be mistaken for an entry - a row starts ``| `` and an entry starts ``- ``.
    """
    start = section.index(_INDEX_HEADING)
    end = section.index(_TABLE, start)
    entries: list[str] = []
    for line in section[start:end].split("\n"):
        if line.startswith("- "):
            entries.append(line[2:])
        elif line.startswith("  ") and entries:
            entries[-1] += " " + line.strip()
    return [_flat(e) for e in entries]


def test_the_index_lists_every_rule_in_order_and_says_what_they_say() -> None:
    """One assertion: the failure is always "these two lists differ", and splitting it into
    add/remove/reorder would report three symptoms of one cause."""
    section = _section()
    rules = rule_leads(section)
    entries = index_entries(section)

    assert entries == rules, (
        "§9's index no longer matches its rows. The index is DERIVED - regenerate it from the "
        "table rather than editing it by hand:\n"
        f"    index has {len(entries)} entries, §9 has {len(rules)} rows\n"
        + "\n".join(
            f"    line {i + 1}: index {e!r}\n              row   {r!r}"
            for i, (e, r) in enumerate(zip(entries, rules, strict=False))
            if e != r
        )
    )


def test_the_guard_has_both_lists_and_reads_only_section_nine() -> None:
    """The cry-wolf half, and the scope check in one. Two empty lists are equal, so a parser that
    stopped matching would pass the test above; and a section boundary that slipped would pull in
    §1's and §3's tables, which is 77 rows rather than 48."""
    section = _section()
    rules = rule_leads(section)

    assert len(rules) > 40, f"only {len(rules)} rows found; the table parser is not reading §9"
    assert len(index_entries(section)) > 40, "the index parser stopped matching"
    whole = CONTRACT.read_text(encoding="utf-8")
    assert len(_ROW.findall(whole)) > len(rules), (
        "the section slice is reading the whole document - other sections carry tables too, and "
        "this guard is about §9's"
    )


def test_the_guard_sees_a_reworded_rule() -> None:
    """Proved by mutation: a row reworded without the index following is the exact drift this
    exists to catch, and the one a reader would never notice."""
    section = _section()
    victim = rule_leads(section)[0]
    mutated = section.replace(f"| **{victim}**", "| **A REWORDED RULE.**", 1)

    assert index_entries(mutated) != rule_leads(mutated), (
        "rewording a row left the two lists equal - the guard is not comparing what it thinks"
    )
