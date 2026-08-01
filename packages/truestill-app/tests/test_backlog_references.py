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

**Two files since the split (2026-08-01), and that CLOSED a gap rather than adding one.**
Built provenance moved to `SHIPPED.md`. Settledness is now decided **by file** for everything
there, which is stronger than the marker it replaces: the old `_SETTLED` markers were
`"out of scope"` and `"and built"`, and neither is a substring of
`## Shipped (kept for provenance)` - so that whole section had been outside this guard's scope
for as long as it existed. Nothing in `SHIPPED.md` is outstanding work by construction, so
nothing there needs a heading to say so.

`BACKLOG.md` keeps one settled heading of its own, *Consciously out of scope*, because a
decided-against item is settled while living beside open work.

**Scope, measured rather than assumed** (`ENGINEERING_STANDARD.md` §4 - a guard that fires on
ordinary work gets switched off):

=========================================  =======
tree state                                 hits
=========================================  =======
before `(aaj)` was closed - correctly open  **0**
the moment it was closed, stale refs live   **2**
after both were repaired                    **0**
after the split, both files clean           **0**
=========================================  =======

Zero false, and it caught a third stale line that two manual sweeps had missed.
"""

from __future__ import annotations

import re
from pathlib import Path

_DOCS = Path(__file__).resolve().parents[3] / "docs"

#: Open work lives here; so do the settled-by-heading sections that belong beside it.
BACKLOG = _DOCS / "BACKLOG.md"

#: Built provenance. **Everything defined here is settled by virtue of the file.**
SHIPPED = _DOCS / "SHIPPED.md"

SOURCES = (BACKLOG, SHIPPED)

#: Headings within `BACKLOG.md` whose entries are settled. `"and built"` is gone with the split
#: - the built sections are a file now, not a heading.
_SETTLED_HEADINGS = ("out of scope",)

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


def _settled_items_and_defining_lines() -> tuple[set[str], set[tuple[Path, int]]]:
    """``(settled item letters, {(file, line) of every item definition})``.

    An item is settled when it is defined in `SHIPPED.md` **at all**, or when it is defined
    under one of `BACKLOG.md`'s settled headings.
    """
    settled: set[str] = set()
    defining: set[tuple[Path, int]] = set()
    for source in SOURCES:
        section = ""
        settled_by_file = source is SHIPPED
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("## "):
                section = line[3:].lower()
            match = _ITEM.match(line)
            if match:
                defining.add((source, number))
                if settled_by_file or any(m in section for m in _SETTLED_HEADINGS):
                    settled.add(match.group(1))
    return settled, defining


def _stale_references() -> list[str]:
    settled, defining = _settled_items_and_defining_lines()
    stale: list[str] = []
    for source in SOURCES:
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            # An item's own headline may describe the problem it was raised for ("progressive
            # disclosure is missing"); that is its subject, not a claim about its status.
            if (source, number) in defining:
                continue
            for item in settled:
                if f"({item})" in line and any(word in line.lower() for word in _PENDING):
                    stale.append(f"{source.name}:{number}: ({item}) - {line.strip()[:90]}")
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
    """Anti-vacuity: if nothing is classified as settled, the scan above proves nothing.

    **Re-measured at the split.** The floor was `> 10` when settledness came from headings in
    one file; both files together define 26 settled items, so `> 20` keeps real headroom while
    still failing loudly if `SHIPPED.md` stopped being read or its items stopped parsing - the
    two ways this check could go quietly vacuous.
    """
    settled, _ = _settled_items_and_defining_lines()
    assert len(settled) > 20, f"only {len(settled)} settled items found; is the scope still right?"


def test_both_sources_are_read_and_contribute() -> None:
    """Neither file may drop out silently.

    `SHIPPED.md` supplies settledness by file, so if it moved or emptied, every item in it
    would quietly stop being watched while the suite stayed green - the vacuous-pass shape this
    module exists to refuse.
    """
    for source in SOURCES:
        assert source.is_file(), f"{source} is gone; this guard now checks less than it says"

    _, defining = _settled_items_and_defining_lines()
    per_file = {source: sum(1 for src, _n in defining if src is source) for source in SOURCES}
    assert per_file[BACKLOG] > 5, f"only {per_file[BACKLOG]} items parsed from BACKLOG.md"
    assert per_file[SHIPPED] > 5, f"only {per_file[SHIPPED]} items parsed from SHIPPED.md"


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
