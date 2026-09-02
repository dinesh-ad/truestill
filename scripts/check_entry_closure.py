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

⚠ **AND THE CONVERSE, since 2026-08-23**: a message that declares ``Closes (xyz).`` while
``(xyz)`` is still an entry in ``BACKLOG.md``. The corpus test owns that direction and **cannot
catch it in time** - it reads the commit message, which does not exist when ``make check`` runs
before the commit, so it can only report on a commit already made. Commit ``4051914`` is the
measured instance: this hook passed it and all three CI lanes went red.

**What it cannot see, stated rather than implied:** ``git commit --amend`` re-stages nothing, so
an amend that only edits the message sees an empty diff and passes. Fails open when neither
document is staged - an empty diff IS a clean answer - and fails CLOSED when git cannot answer
(P189, 2026-09-02; before that a git failure read as an empty diff).
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


#: ⚠ **UTF-8 AND `surrogateescape`, NEVER THE MACHINE LOCALE - `(aic)`'s ruling, applied to git.**
#: `text=True` alone decodes with `locale.getpreferredencoding(False)`, which is **cp1252 on
#: Windows**, and both documents this hook reads are full of `⚠`, `❌` and `🔑`. `❌` is
#: `E2 9D 8C`, and `0x9D` is one of the five bytes cp1252 does not map - so the first one to
#: land in `BACKLOG.md` took the Windows lane red while every local run stayed green, because a
#: POSIX locale is UTF-8 and the failure cannot appear here. Measured 2026-08-30: the primary
#: path crashed at byte 18,761 while `read_text(encoding="utf-8")` two lines below it had made
#: the correct decision all along - **the fallback was explicit and the fast path was not.**
#:
#: **Stated at both call sites rather than shared through a dict**: `subprocess.run`'s overloads
#: cannot see through a `**` unpack, so the shared form degraded the return type to `Any` and
#: mypy said so - two literal keyword pairs are also the thing a reader can check at a glance.
#:
#: `surrogateescape` rather than strict for `(aic)`'s own reason, one layer up: a commit-msg hook
#: that dies on a byte is one that gets bypassed with `--no-verify`, which costs more than the
#: check is worth - which is exactly what `test_closed_entries_leave_the_backlog.py` says about
#: this hook's fail-open posture. It is byte-identical to strict on valid UTF-8.


def staged_diff() -> str | None:
    """The two documents' staged changes, or ``None`` when git could not answer.

    ⚠ ``None``, not ``""``: an empty diff means *nothing staged* and is a clean pass, so a git
    failure returning it read as clean. Found 2026-09-02 (P189) as the substitution shape - a
    reader that reports its output makes "could not read" and "nothing there" the same string.
    """
    try:
        done = subprocess.run(
            ["git", "diff", "--cached", "-U0", "--", BACKLOG, SHIPPED],
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def staged_text(path: str) -> str | None:
    """``path`` as THIS COMMIT will contain it, not as the working tree happens to look.

    The two differ whenever something is edited but not staged, and the commit is what the rule is
    about. ``None`` when git could not show it: the working tree is a different document from the
    one being committed, and judging it in the commit's place was the same substitution shape.
    """
    try:
        done = subprocess.run(
            ["git", "show", f":{path}"],
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


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


CANNOT_READ = (
    "git could not report the staged {what}, so this commit cannot be judged - and unknown is "
    "not green. Run `git status` and `git diff --cached` by hand; if git itself is broken, fix "
    "that first."
)


def refusals(message: str, diff: str | None) -> list[str]:
    """What is wrong with this commit, one actionable sentence each. Empty means nothing is."""
    if diff is None:
        return [CANNOT_READ.format(what="diff")]
    removed, added = entry_moves(diff)
    # A retitled entry is removed AND re-added in the same file: that is an edit, not a departure.
    left = removed[BACKLOG] - added[BACKLOG]
    declared = set(CLOSES.findall(message))
    retired = set(RETIRES.findall(message))
    backlog_text = staged_text(BACKLOG)
    if backlog_text is None:
        return [CANNOT_READ.format(what=f"copy of {BACKLOG}")]
    out = []
    # ⚠ **THE OTHER DIRECTION, ADDED 2026-08-23 AFTER IT COST A RED CI.** This loop iterated only
    # over what LEFT the backlog, so a commit could declare a closure it had not performed and be
    # accepted - which `4051914` did, saying `Closes (afw)` with `(afw)` still an entry.
    #
    # **`test_closed_entries_leave_the_backlog.py` owns that direction and cannot catch it in
    # time.** It reads the COMMIT MESSAGE, and when `make check` runs - before every commit, by
    # the standing rule - that message does not exist yet. So it can only ever report on a commit
    # already made, which in practice means from CI after the push. The two guards were not two
    # halves of one rule; they were one half, twice.
    #
    # It keys on *"is it still open work"* rather than *"did it leave in this commit"*, so a
    # follow-up commit repeating a trailer is not a false claim - the entry is already gone, which
    # is the end state the rule exists to produce.
    for letter in sorted(declared & set(ENTRY.findall(backlog_text))):
        out.append(
            f"({letter}) is declared closed but is still an entry in {BACKLOG}, which carries "
            f"open work only. Move it to {SHIPPED} in this commit - it keeps its letter and is "
            f"provenance. If part of it is genuinely unfinished, split that part into a new "
            f"letter rather than leaving the whole entry open, and do not claim the closure."
        )
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
