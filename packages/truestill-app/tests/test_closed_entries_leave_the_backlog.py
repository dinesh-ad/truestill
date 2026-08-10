"""A commit that closes an entry must also move it out of `BACKLOG.md`.

**Why this exists.** `BACKLOG.md` carries open work only - `SHIPPED.md`'s header says that split
exists because `(aae)` and `(jj)` once sat in the wrong section while they were shipping. The rule
was written down and nothing ran it. On 2026-08-10 a sweep found three entries stale, and by the
end of that same day **three more** - `(acq)`, `(acr)`, `(acs)` - had been closed and left in
place, one of them by a commit whose own message said it was closing it.

That is `(ace)`'s pattern: a rule that depends on somebody remembering. Prose cannot refuse to run.

**The declaration is a dedicated trailer line, and the looser forms were measured and refused.**
A letter counts as closed only when a line of the commit message is exactly ``Closes (xyz).`` -
nothing else on the line. Tested against the full history, the obvious wider pattern
(``closes?\\s*\\(xyz\\)`` anywhere, any case) returns **two matches and both are false**:

* `(aco)` - the prose is *"a timezone dataset is not the cheapest way to close (aco)"*, a sentence
  ABOUT closing it. The entry is legitimately open.
* `(bbb)` - *"close (bbb) with item 4 verified, not ticked"*, on an entry that still carries
  partially-built sub-items.

A guard that fires on ordinary work gets switched off and takes its real signal with it (§4), so
the marker has to be something nobody writes by accident.

**What this cannot see, stated rather than implied.** CI checks out at depth 1, so in CI `git log`
holds exactly one commit - the tip. That is the right scope for the commit being tested, but a
batch push means only the last commit of the batch is examined there. Locally the history is
complete and the window is the whole log. Neither is total; the check that matters most runs at
commit time, when the entry move belongs in the same commit anyway.

**And the gap no check can close.** `(acr)` was closed by the maintainer **in conversation**. No
repo check could ever have seen that, which is exactly why the process rule in `BACKLOG.md`'s
*Item letters* section now says a ruling is not a closure until a commit records it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKLOG = ROOT / "docs/BACKLOG.md"

#: A dedicated trailer line and nothing else on it. See the module docstring for the two false
#: positives the looser forms produce on this repo's real history.
_CLOSES = re.compile(r"^Closes \(([a-z]{1,3})\)\.?$", re.MULTILINE)

#: A letter is DECLARED by a top-level entry title, the same shape
#: `test_backlog_letters_are_unique.py` uses. A citation inside someone else's prose is not the
#: entry, so matching one would report an entry that had in fact been moved.
_DECLARED = re.compile(r"^- \*\*\(([a-z]{1,3})\)", re.MULTILINE)


def _log() -> str:
    """Whatever history this clone has. Empty string when git cannot answer."""
    try:
        done = subprocess.run(
            ["git", "log", "--format=%B"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - no git in the environment
        return ""
    return done.stdout if done.returncode == 0 else ""


def test_a_letter_a_commit_declared_closed_is_not_still_open_work() -> None:
    """The guard. A commit said it closed the entry; the entry must not be in the open-work file."""
    log = _log()
    if not log:
        pytest.skip("no git history available to read")

    closed = set(_CLOSES.findall(log))
    still_open = sorted(closed & set(_DECLARED.findall(BACKLOG.read_text("utf-8"))))

    assert not still_open, (
        f"closed by a commit and still in BACKLOG.md: {still_open}. "
        "BACKLOG.md carries open work only - move the entry to SHIPPED.md, which keeps its "
        "letter. If the entry is NOT actually closed, the commit message should not say so."
    )


def test_the_marker_does_not_match_prose_about_closing_something() -> None:
    """**The cry-wolf half, and it is the reason for the narrow marker.**

    Both strings below appear in this repo's real history and both describe an entry that is
    legitimately open. If the pattern ever widens, this fails before the widening reaches a
    contributor as a false alarm on ordinary work.
    """
    for prose in (
        "a timezone dataset is not the cheapest way to\nclose (aco).",
        "docs(backlog): close (bbb) with item 4 verified, not ticked",
        "This closes (abc) in spirit but not in fact.",
        "Closes (abc) once the second half lands.",
    ):
        assert not _CLOSES.findall(prose), f"the marker matched prose: {prose!r}"


def test_the_marker_does_match_the_declared_form() -> None:
    """The other half - a guard that matches nothing would pass forever."""
    assert _CLOSES.findall("Some body text.\n\nCloses (acq).") == ["acq"]
    assert _CLOSES.findall("Closes (acq)") == ["acq"]
