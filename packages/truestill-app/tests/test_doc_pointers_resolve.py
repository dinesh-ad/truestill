"""A markdown link in a tracked `.md` file points at something that exists.

**Why this exists, and why it was written BEFORE the move it protects.** `BACKLOG.md` is 3,690
lines and its bodies are about to move out to `docs/research/backlog/`. A guard written *after*
a move can only confirm the move was clean if it was; written before, it fails on the current
state, the pointers get fixed, and then it protects the move. Same rule as the grid guards.

⚠ **SCOPE IS MARKDOWN LINKS ONLY, AND THAT IS A MEASURED DECISION RATHER THAN A CONVENIENT ONE.**
A first pass guarded *every* path-shaped token - anything matching ``name.ext`` - across every
tracked source and doc. Run against the tree it reported **377 unresolved out of 1,893**, and
essentially all of it was noise:

| what the 377 actually were | example | n |
|---|---|---:|
| filenames the *product* writes, which are not repo files | ``.truestill-drive.json`` | 16 |
| prose examples of a file a user might have | ``report.txt``, ``notes.txt`` | many |
| targets that deliberately DO NOT exist | ``Cargo.toml`` (Tauri is unbuilt) | 5 |
| a file cited *because* it was correctly deleted | ``brand/LICENSE-DejaVu.txt`` | 1 |
| not a path at all - the extension pattern matched a product name | ``Next.js`` | 2 |

The fourth row is the one that settles it. `test_bundled_font_ships_with_its_licence` names
``brand/LICENSE-DejaVu.txt`` in its docstring **to explain that the file must not be revived**;
a guard demanding it exist would demand the repo undo a correct deletion. **A pointer naming a
deliberately-absent file is common and correct**, so "every path-shaped token resolves" is not a
rule this repo can hold. A markdown link is different: it is written to be *followed*, and a
reader who clicks it expects to arrive.

⚠ **LINE NUMBERS ARE NOT GUARDED, AND THIS IS THE HONEST LIMIT RATHER THAN AN OVERSIGHT.**
253 pointers carry a ``:line``. Only the line *count* is checkable - whether the file is at least
that long - and that catches nothing useful: a citation that has drifted onto unrelated code is
still *within* the file, which is precisely the drift
`IMPLEMENTATION_STANDARDS.md` already answers with *"symbols are cited over line numbers"*. Worse,
the only four pointers that do run past end-of-file are all in `docs/code-quality-audit.md`, a
**record** - and this repo forbids rewriting records to stay correct. A line guard would therefore
either fail for ever or need an exemption that leaves it guarding nothing. Not written.
"""

from __future__ import annotations

import posixpath
import re
import subprocess
from pathlib import Path

#: `[text](target)`. Reference-style and bare-URL links are not used in this repo's docs.
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

#: Not file pointers: the web, an in-page anchor, an address.
_NOT_A_PATH = ("http://", "https://", "#", "mailto:")

#: Generated, vendored or archived trees. `.superseded/` is deliberately included: it holds
#: copies of files as they were BEFORE an edit, so their pointers describe a past tree and are
#: not the present one's problem.
_SKIP = (
    ".git/",
    ".venv/",
    "dist/",
    "out/",
    "node_modules/",
    ".superseded/",
    ".pytest_cache/",
    ".scratch/",
    "static/dist/",
)

#: Below this the guard is not doing its job. It is a floor against the failure mode where a
#: path change, a bad glob or a moved test file leaves the corpus empty and the assertion passes
#: by having nothing to check - `ENGINEERING_STANDARD.md` §4, fifty-second member.
_MINIMUM_LINKS = 60


def _root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def _tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True)
    return [
        rel
        for rel in out.stdout.split("\n")
        if rel and not any(rel.startswith(s) or f"/{s}" in rel for s in _SKIP)
    ]


def broken_links(docs: dict[str, str], tracked: set[str]) -> list[tuple[str, str]]:
    """Every link in ``docs`` that resolves to nothing, as ``(origin, target)``.

    Pure and takes its whole world as arguments, so the cry-wolf test below can hand it a tree
    that does not exist on disk. A guard whose logic can only be exercised against the real repo
    can only be proven by breaking the real repo.
    """
    directories = {str(Path(rel).parent) for rel in tracked}
    broken: list[tuple[str, str]] = []
    for origin, text in docs.items():
        for match in _LINK.finditer(text):
            target = match.group(1)
            if target.startswith(_NOT_A_PATH):
                continue
            # A link may address a section of another file; the file is what we can check.
            target = target.split("#", 1)[0]
            if not target:
                continue
            # ⚠ `normpath`, not `Path(...)`. `docs/BACKLOG.md` linking `../README.md` builds
            # `docs/../README.md`, which `as_posix()` leaves untouched and no lookup matches -
            # so a correct upward link read as broken. Found by the cry-wolf test below on a
            # synthetic tree, not by the real corpus.
            joined = posixpath.join(posixpath.dirname(origin), target)
            resolved = posixpath.normpath(joined)
            if resolved in tracked or resolved in directories:
                continue
            broken.append((origin, match.group(1)))
    return broken


def _corpus() -> tuple[dict[str, str], set[str]]:
    root = _root()
    tracked = _tracked(root)
    docs = {
        rel: (root / rel).read_text(encoding="utf-8", errors="replace")
        for rel in tracked
        if rel.endswith(".md")
    }
    return docs, set(tracked)


def test_every_markdown_link_points_at_something_that_exists() -> None:
    """The whole tree, not a sampled subset."""
    docs, tracked = _corpus()
    broken = broken_links(docs, tracked)
    assert not broken, "markdown links that resolve to nothing:\n" + "\n".join(
        f"  {origin} -> {target}" for origin, target in sorted(broken)
    )


def test_the_guard_is_actually_looking_at_something() -> None:
    """A guard that checks nothing passes for ever, and reads exactly like a guard that works."""
    docs, _ = _corpus()
    assert len(docs) >= 40, f"only {len(docs)} tracked .md files were collected"
    found = sum(
        1
        for text in docs.values()
        for m in _LINK.finditer(text)
        if not m.group(1).startswith(_NOT_A_PATH)
    )
    assert found >= _MINIMUM_LINKS, (
        f"only {found} file links were found across {len(docs)} documents, under the "
        f"{_MINIMUM_LINKS} floor. Either the corpus stopped being collected or the link "
        "pattern stopped matching - both pass this suite silently otherwise."
    )


def test_the_guard_fails_when_a_link_goes_stale() -> None:
    """Cry-wolf, proven on a synthetic tree rather than by breaking the real one.

    Three cases in one, because the failure this protects against is a *move*: the target
    disappearing, the target moving to a new directory, and a link that must keep passing while
    the other two fail - otherwise a guard that rejects everything would look identical here.
    """
    tracked = {"docs/BACKLOG.md", "docs/research/backlog/aaa.md", "README.md"}

    live = {"docs/BACKLOG.md": "see [aaa](research/backlog/aaa.md) and [readme](../README.md)"}
    assert broken_links(live, tracked) == [], "a correct link was reported as broken"

    moved = {"docs/BACKLOG.md": "see [aaa](aaa.md)"}
    assert broken_links(moved, tracked) == [("docs/BACKLOG.md", "aaa.md")], (
        "a body that moved out of BACKLOG.md left a link at the old path and the guard did not "
        "notice - which is the exact failure it was written before the move to catch"
    )

    deleted = {"README.md": "[gone](docs/deleted-file.md)"}
    assert broken_links(deleted, tracked) == [("README.md", "docs/deleted-file.md")]
