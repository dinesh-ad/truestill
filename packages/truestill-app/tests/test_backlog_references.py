"""A settled backlog item must not be described as pending work somewhere else.

**Two reported "no stale status" answers were wrong, both the same way.** Entry bodies were
checked; **references to** the entry that changed were not. Closing `(aaj)` left `(bbb)` saying
*"the half that is missing is recorded as (aaj)"* and the Converged programs block saying
*"the unbuilt half of item 4 is (aaj)"*. The restructure left `(n)` and `(ii)` contradicting the
section they sat in. Every one of them was a grep away.

That is the shape of guard rules #3 and #4: something correct in one place while its dependents
silently disagree. **Docs are the same class as code here** - a stale cross-reference is a
document asserting something false, and the reader most likely to hit it is a cold start with no
way to tell.

**Scope, measured rather than assumed** (`ENGINEERING_STANDARD.md` §4 - a guard that fires on
ordinary work gets switched off):

=========================================  =======
tree state                                 hits
=========================================  =======
before `(aaj)` was closed - correctly open  **0**
the moment it was closed, stale refs live   **2**
after both were repaired                    **0**
=========================================  =======

Zero false, and it caught a third stale line that two manual sweeps had missed.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKLOG = Path(__file__).resolve().parents[3] / "docs" / "BACKLOG.md"

#: Sections whose entries are settled: nothing in them is outstanding work.
_SETTLED = ("out of scope", "and built")

#: Phrases that assert an item is unfinished. Deliberately narrow, and narrowed **again** on its
#: first real outing: it flagged `(vv)`'s sentence about a *journal row* still being "pending",
#: which asserts nothing about any item's status. "pending" is domain vocabulary here -
#: `Catalog.pending_migration` is an API - so it is gone, alongside "remains" and "deferred",
#: which legitimately describe a settled item's reasoning. A guard that fires on ordinary prose
#: is one someone switches off, taking its real coverage with it (§4).
_PENDING = (
    "is missing",
    "still to build",
    "not built",
    "unbuilt",
    "not yet built",
    "outstanding",
)

_ITEM = re.compile(r"- \*\*.*?\((aa[a-z]|[a-z]{1,3})\)")


def _settled_items_and_defining_lines() -> tuple[set[str], set[int]]:
    settled: set[str] = set()
    defining: set[int] = set()
    section = ""
    for number, line in enumerate(BACKLOG.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            section = line[3:].lower()
        match = _ITEM.match(line)
        if match:
            defining.add(number)
            if any(marker in section for marker in _SETTLED):
                settled.add(match.group(1))
    return settled, defining


def _stale_references() -> list[str]:
    settled, defining = _settled_items_and_defining_lines()
    stale: list[str] = []
    for number, line in enumerate(BACKLOG.read_text(encoding="utf-8").splitlines(), 1):
        # An item's own headline may describe the problem it was raised for ("progressive
        # disclosure is missing"); that is its subject, not a claim about its status.
        if number in defining:
            continue
        for item in settled:
            if f"({item})" in line and any(word in line.lower() for word in _PENDING):
                stale.append(f"BACKLOG.md:{number}: ({item}) - {line.strip()[:90]}")
    return stale


def test_no_settled_item_is_described_as_pending() -> None:
    stale = _stale_references()
    assert not stale, (
        "a backlog item that is built or out of scope is called unfinished elsewhere:\n"
        + "\n".join(stale)
        + "\n\nWhen an item's status changes, grep for every reference to it - the entry body "
        "is not the only place its status is asserted."
    )


def test_the_guard_has_settled_items_to_watch() -> None:
    """Anti-vacuity: if nothing is classified as settled, the scan above proves nothing."""
    settled, _ = _settled_items_and_defining_lines()
    assert len(settled) > 10, f"only {len(settled)} settled items found; is the scope still right?"


def test_the_guard_sees_a_planted_stale_reference() -> None:
    """Mutation half, without touching the real file: the phrase-and-id shape must be caught."""
    settled, _ = _settled_items_and_defining_lines()
    item = next(iter(sorted(settled)))
    line = f"the unbuilt half of that work is `({item})`."
    assert any(word in line.lower() for word in _PENDING)
    assert f"({item})" in line

    # Cry-wolf half: naming a settled item without claiming it is unfinished is ordinary prose.
    fine = f"decided against; see `({item})` for the reasoning."
    assert not any(word in fine.lower() for word in _PENDING)
