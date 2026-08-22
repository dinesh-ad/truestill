#!/usr/bin/env python3
"""commit-msg hook: an entry that LEAVES ``BACKLOG.md`` is closed, and closed in this commit.

`test_closed_entries_leave_the_backlog.py` checks one direction - a letter a commit declared
closed must not still be open work. It cannot check the other: a letter that leaves the backlog
without ever being declared, or that leaves and arrives nowhere. Measured 2026-08-10, the whole
history carries exactly **one** ``Closes`` trailer, so two of the three entries the rule was
written for do not satisfy it and nothing said so.

**Why this is a hook and not a test.** The other direction is not honestly checkable against the
corpus. "A letter in ``SHIPPED.md`` must carry a trailer" fails **31 of its 32 entries** on the
day it is written, and "an allocated letter is in one of the two files" is false as well -
``(e)``, ``(h)`` and ``(gg)`` are legitimately in neither, retired and cited from research docs.
A guard that goes red on the past gets switched off and takes its real signal with it (§4).

**So the boundary is structural, not a date.** This reads *only the staged diff of the commit
being made*. It has no opinion about anything already committed, which is why there is no "from
now on" to record and nothing to grandfather: an undated "from now on" is the next drift.

Refuses when a commit removes an entry title from ``BACKLOG.md`` and either the message carries
no ``Closes (xyz).`` line for it, or the entry does not arrive in ``SHIPPED.md`` in the same
commit. A retitled entry is not a departure - a letter removed and re-added inside ``BACKLOG.md``
is ignored.

**What it cannot see, stated rather than implied:** ``git commit --amend`` re-stages nothing, so
an amend that only edits the message sees an empty diff and passes. Fails open with no git, or
when neither document is staged.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BACKLOG = "docs/BACKLOG.md"
SHIPPED = "docs/SHIPPED.md"

#: The closure declaration. **The full stop is optional deliberately** - the documented form
#: carries it, and requiring it would mean a missing period silently stops a commit counting as a
#: closure, which is the same silence the rule exists to end. Widening it this far is safe: the
#: line must be a trailer of its own, which nobody writes by accident. See the module test for
#: the four real near-misses from this repo's history that must NOT match.
CLOSES = re.compile(r"^Closes \(([a-z]{1,3})\)\.?$", re.MULTILINE)

#: The other honest way for an entry to leave: **refused and retired**, which is not a closure and
#: must not be filed as one. Added 2026-08-11, after this hook would have refused a legitimate
#: retirement - it assumed every departure ends in `SHIPPED.md`, and a refused idea never ships.
#: A retired letter must still be NAMED in `BACKLOG.md`, because the *Item letters* section rules
#: that "a letter that is invisible here is retired, not free" and a letter nobody records is a
#: letter somebody reassigns.
RETIRES = re.compile(r"^Retires \(([a-z]{1,3})\)\.?$", re.MULTILINE)

#: A letter is DECLARED by a top-level entry title, the shape both documents use. ``MULTILINE``
#: because the guard test scans whole documents with it while this file matches a line at a time;
#: without the flag ``findall`` silently answers only for the first line of a file, and a citation
#: inside someone else's prose is not an entry, so a looser pattern would report a moved entry as
#: still present.
ENTRY = re.compile(r"^- \*\*\(([a-z]{1,3})\)", re.MULTILINE)


def staged_diff() -> str:
    """The two documents' staged changes. Empty string when git cannot answer."""
    try:
        done = subprocess.run(
            ["git", "diff", "--cached", "-U0", "--", BACKLOG, SHIPPED],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except OSError, subprocess.SubprocessError:  # pragma: no cover - no git in the environment
        return ""
    return done.stdout if done.returncode == 0 else ""


def entry_moves(diff: str) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Letters whose entry title was removed from / added to each document, per file.

    The path comes from the ``diff --git`` header rather than from ``+++``, which reads
    ``/dev/null`` for a deleted file and would attribute its removals to nothing.
    """
    removed: dict[str, set[str]] = {BACKLOG: set(), SHIPPED: set()}
    added: dict[str, set[str]] = {BACKLOG: set(), SHIPPED: set()}
    current = ""
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current = line.rpartition(" b/")[2]
        elif current in removed and line.startswith("-"):
            found = ENTRY.match(line[1:])
            if found:
                removed[current].add(found.group(1))
        elif current in added and line.startswith("+"):
            found = ENTRY.match(line[1:])
            if found:
                added[current].add(found.group(1))
    return removed, added


def refusals(message: str, diff: str) -> list[str]:
    """What is wrong with this commit, one actionable sentence each. Empty means nothing is."""
    removed, added = entry_moves(diff)
    # A retitled entry is removed AND re-added in the same file: that is an edit, not a departure.
    left = removed[BACKLOG] - added[BACKLOG]
    declared = set(CLOSES.findall(message))
    retired = set(RETIRES.findall(message))
    backlog_text = Path(BACKLOG).read_text(encoding="utf-8") if Path(BACKLOG).exists() else ""
    out = []
    for letter in sorted(retired):
        if letter not in left:
            out.append(
                f"({letter}) is declared retired but did not leave {BACKLOG}. Retiring removes "
                f"the entry; a letter that is still an entry is still open work."
            )
        elif f"({letter})" not in backlog_text:
            out.append(
                f"({letter}) was retired and is now named nowhere in {BACKLOG}. Record it in the "
                f"*Item letters* section: a letter that is invisible there is free, and letters "
                f"are permanent identifiers."
            )
    for letter in sorted(left - retired):
        if letter not in declared:
            out.append(
                f"({letter}) left {BACKLOG} but the message does not say `Closes ({letter}).` "
                f"on a line of its own. A ruling is not a closure until a commit records it; "
                f"if the entry is not closed, it belongs in {BACKLOG}. If it was refused rather "
                f"than built, say `Retires ({letter}).` instead and keep the letter recorded."
            )
        elif letter not in added[SHIPPED]:
            out.append(
                f"({letter}) left {BACKLOG} and did not arrive in {SHIPPED}. A closed entry "
                f"keeps its letter and moves - it is provenance, not something to delete."
            )
    return out


def main() -> int:
    message = Path(sys.argv[1]).read_text(encoding="utf-8")
    problems = refusals(message, staged_diff())
    for problem in problems:
        print(f"commit-msg: refused -- {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
