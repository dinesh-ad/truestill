"""`(aef)` Option B: the release list answers "what must ship before v1", and stays true.

**The finding this exists for is not that the answer was wrong. It is that there was no answer.**
`(aef)`: the release question *"is not stored anywhere - it is RECOMPUTED from judgement every
time it is asked, which is why it comes out different."* Option B stores it in one place;
this stops that place from rotting.

⚠ **THE STATE COLUMN IS DERIVED, NEVER TRUSTED.** Every letter is resolved against `BACKLOG.md`
and `SHIPPED.md` and compared with what the list declares. That is the one thing a guard can hold
here, and it is exactly the class the 2026-08-22 whole-backlog re-read found and nothing
automatic could see: `(abo)` sat open for two weeks after shipping, `(ach)` for thirteen days,
both closed by commits naming a **different** letter, so the closure gate was blind to them by
construction. A letter on this list going the same way would be a release plan naming work that
is done.

**Doc-to-CODE, not doc-to-doc.** `ENGINEERING_STANDARD.md` §4 records why a doc-to-doc
consistency guard cannot fail honestly and was refused; this is the shape it names as writable
instead - *"the claim is machine-checkable by construction"*, like `test_doc_pointers_resolve`
and the letter-uniqueness test.
"""

from __future__ import annotations

import re
from pathlib import Path

_DOCS = Path(__file__).resolve().parents[3] / "docs"
STATUS = _DOCS / "PROJECT_STATUS.md"
BACKLOG = _DOCS / "BACKLOG.md"
SHIPPED = _DOCS / "SHIPPED.md"

#: The heading the list lives under. Named rather than guessed: a guard that scans the whole file
#: for anything table-shaped would fire on every other table `PROJECT_STATUS.md` carries.
_HEADING = "### ⚠ THE RELEASE LIST"

#: A row: `| `(xyz)` | STATE | why |`. The letter and the state are the machine-readable part;
#: the third column is prose for a person and is deliberately not parsed.
_ROW = re.compile(r"^\|\s*`\((?P<letter>[a-z]+)\)`\s*\|\s*(?P<state>[A-Z]+)\s*\|")

#: What a row may declare. `OPEN` means still to build; `DONE` means it shipped and the list is
#: recording that it no longer blocks. Anything else is a typo, and a typo that silently parsed
#: as neither would make a row invisible to this guard.
_STATES = frozenset({"OPEN", "DONE"})


def _rows() -> list[tuple[str, str]]:
    """Every `(letter, declared_state)` under the release-list heading."""
    text = STATUS.read_text(encoding="utf-8")
    assert _HEADING in text, f"the release list heading is gone from {STATUS.name}"
    section = text.split(_HEADING, 1)[1].split("\n### ", 1)[0]
    return [(m["letter"], m["state"]) for line in section.splitlines() if (m := _ROW.match(line))]


def _open_letters() -> set[str]:
    """Letters that are still open work, read the way `PROJECT_STATUS.md` §2b's command reads."""
    text = BACKLOG.read_text(encoding="utf-8")
    section = text.split("## Approved - still to build", 1)[1].split("## Settled technical", 1)[0]
    return set(re.findall(r"^ *- \*\*\(([a-z]+)\)", section, re.M))


def _shipped_letters() -> set[str]:
    return set(re.findall(r"^- \*\*\(([a-z]{1,3})\)", SHIPPED.read_text(encoding="utf-8"), re.M))


def test_the_list_is_not_empty() -> None:
    """§4's fifty-second member, and here it is the whole of the guard's power.

    Zero disagreements over a list nobody could parse is the same green as zero over a correct
    one - and this parser reads a **markdown table**, which is exactly the kind of subject that
    stops matching when someone reformats it.
    """
    rows = _rows()
    assert rows, (
        "no release-list rows parsed. Either the list is empty - which is a decision, and this "
        "test should be changed deliberately - or the table's shape moved and this guard has "
        "silently stopped reading anything."
    )


def test_every_letter_on_the_list_is_a_real_entry() -> None:
    """A release plan naming a letter that exists nowhere is worse than a short plan."""
    known = _open_letters() | _shipped_letters()
    unknown = [letter for letter, _state in _rows() if letter not in known]
    assert not unknown, (
        f"the release list names letters that are in neither BACKLOG.md nor SHIPPED.md: {unknown}"
    )


def test_every_declared_state_is_one_this_guard_understands() -> None:
    """A typo must not parse as a third state nothing compares against."""
    bad = [(letter, state) for letter, state in _rows() if state not in _STATES]
    assert not bad, f"unknown state on the release list: {bad}. Expected one of {sorted(_STATES)}"


def test_the_declared_state_matches_the_file_the_entry_lives_in() -> None:
    """⚠ **The one that earns this file.** A gate that opened must not read as still shut.

    The whole-backlog re-read found two entries closed in fact and open on paper for a fortnight,
    both closed by commits naming a different letter. Nothing could see it, because the closure
    gate keys on a commit **declaring** a letter and is blind to work that closes somebody else's
    entry. On this list that failure is a release plan blocking on finished work - so the state is
    derived from which file the entry lives in, and disagreement is a red test rather than a
    re-read somebody has to remember to do.
    """
    still_open, shipped = _open_letters(), _shipped_letters()
    wrong: list[str] = []
    for letter, declared in _rows():
        actual = "OPEN" if letter in still_open else "DONE" if letter in shipped else "?"
        if actual != declared:
            wrong.append(f"({letter}) says {declared}, but it is {actual}")
    assert not wrong, (
        "the release list disagrees with where the entry lives: "
        + "; ".join(wrong)
        + ". Update the list deliberately - a letter that shipped stops blocking a tag, and a "
        "plan that still names it is asking for work that is already done."
    )


def test_a_letter_appears_at_most_once() -> None:
    """Two rows for one letter can disagree with each other, and the guard above would pass both.

    Cheap, and it closes the one way this table can be internally inconsistent while every other
    assertion here holds.
    """
    letters = [letter for letter, _state in _rows()]
    duplicates = sorted({x for x in letters if letters.count(x) > 1})
    assert not duplicates, f"the release list names these letters more than once: {duplicates}"
