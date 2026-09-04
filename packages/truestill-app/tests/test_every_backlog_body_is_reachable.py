"""Every backlog body on disk is reachable from an index. The direction nothing guarded.

**This is the missing half of a pair, not a new idea.** `test_doc_pointers_resolve.py` asserts
that a markdown link points at a file that exists - **link → file**. Nothing asserted
**file → link**, so a body could sit on disk reachable from nowhere and every guard stayed green.
`test_backlog_headlines_agree.py` and `test_live_documents_cite_code_that_exists.py` do not close
it either: both start from *letters* and derive the filename, so a body whose letter is not in
the index they read is not examined - it is not even looked for.

⚠ **`CLAUDE.md` states one half of this and does not notice the other.** Its words are *"AN ENTRY
LINKS ITS OWN BODY, and that is what guards the body's existence - `test_doc_pointers_resolve.py`
already fails on a markdown link that resolves to nothing, so a linked body cannot go missing"* -
which is true, and is exactly the half that leaves an **unlinked** body invisible. The same
document's map then excludes all backlog bodies deliberately, on the stated promise that they are
*"reached through its own index rather than listed here"*. This test is what makes that promise
checkable instead of assumed.

**It earned itself by going red on the day it was written**, which is `(ago)`'s bar and the reason
a map-completeness guard was refused in the same session: **15 bodies** were in neither index, and
**10 of those were referenced from nowhere in the repository at all**. Every one belonged to an
entry that had shipped - `SHIPPED.md` carried the row and the row carried no link to its body.
That is the asymmetry: a `BACKLOG.md` entry linking its body was already checked by the pair
above, and an entry moving to `SHIPPED.md` could drop the link on the way with nothing to say so.

**Reachable means a markdown link from one of the two indexes**, not the filename appearing
somewhere. A body named in passing by a soak record is *evidence cited*, not *indexed*; three of
the fifteen were exactly that and would have read as fine under a looser rule.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKLOG = ROOT / "docs/BACKLOG.md"
SHIPPED = ROOT / "docs/SHIPPED.md"

#: How an index writes a link to a body. `BACKLOG.md` and `SHIPPED.md` both sit in `docs/`, so
#: the link is relative to that directory - `[Full entry](research/backlog/aaa.md)`.
_LINK_PREFIX = "research/backlog/"


def _tracked_bodies() -> list[str]:
    """Every tracked body, read from **git rather than the filesystem**.

    An untracked scratch file in that directory is not a document this repo ships, and demanding
    it be indexed would fail on somebody's working copy for a file nobody else can see.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "docs/research/backlog/*.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(name for name in listed.stdout.split("\0") if name)


def _index_text() -> str:
    return BACKLOG.read_text(encoding="utf-8") + SHIPPED.read_text(encoding="utf-8")


def unreachable(bodies: list[str], index: str) -> list[str]:
    """The bodies no index links. Separated from the test so a mutation can drive it directly."""
    return [b for b in bodies if f"{_LINK_PREFIX}{Path(b).name}" not in index]


def test_every_backlog_body_is_linked_from_an_index() -> None:
    """A body nothing links is a document that cannot be found, however good it is.

    The corpus rule this serves is `(ait)`/`(aiu)`'s: a record is never deleted to shorten a list,
    because a lost answer key corrupts every measurement taken against it. A record nobody can
    reach is lost in the way that matters, while still costing a reader who greps.
    """
    missing = unreachable(_tracked_bodies(), _index_text())

    assert not missing, (
        "these backlog bodies exist and no index links them, so nothing can reach them:\n    "
        + "\n    ".join(missing)
        + "\n\nAdd `[Full entry](research/backlog/<letter>.md)` to the entry's row in "
        "`BACKLOG.md` or `SHIPPED.md`. An entry that moves to SHIPPED keeps its body and must "
        "keep the link with it - that is how all fifteen of these were lost."
    )


def test_the_guard_is_reading_real_bodies_and_real_links() -> None:
    """The cry-wolf half. An empty body list, or an index this could not read, would make the
    test above pass while checking nothing - the vacuous green this repo files against."""
    bodies = _tracked_bodies()
    index = _index_text()

    assert len(bodies) > 100, f"only {len(bodies)} bodies found; the glob is not reading them"
    linked = [b for b in bodies if f"{_LINK_PREFIX}{Path(b).name}" in index]
    assert len(linked) > 100, f"only {len(linked)} bodies resolve to a link; the pattern is wrong"


def test_the_guard_sees_a_body_whose_link_is_removed() -> None:
    """Proved by mutation rather than asserted: the detector is driven against an index with one
    body's link taken out, which is the exact shape of the defect it exists to catch."""
    bodies = _tracked_bodies()
    victim = Path(bodies[0]).name
    index = _index_text().replace(f"{_LINK_PREFIX}{victim}", "")

    assert [b for b in unreachable(bodies, index) if Path(b).name == victim], (
        f"removing the only link to {victim} did not make it unreachable - the detector is "
        f"matching something other than the link"
    )
