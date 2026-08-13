"""The static assets this install actually carries - the app's half of `(aad)`'s self-check.

**Why this is here and not in core.** The fonts and their licence live in `truestill_app/static`,
and core importing the app is forbidden (`IMPLEMENTATION_STANDARDS.md` §2 - the app depends on
core only, never the reverse). So core answers for exiftool, the trash backend and the file
locations, and this module adds the one thing only the app can see. `truestill-cli` depends on
core alone and therefore cannot reach these checks; it says so with
`selfcheck.not_checked_finding` rather than omitting them.

**THE ARTIFACT REPORTS WHAT IT HOLDS; THE CALLER DECIDES WHETHER THAT IS RIGHT.** A frozen build
cannot know what it was supposed to contain - a truncated font and a correct one are both "a file
that is here" - so every face is reported with its **size and sha256** and the comparison against
the repository's own bytes belongs to the packaging job. That split is the only reason `(aad)`'s
*"the byte count of the source file"* is answerable from inside a bundle.

**Reading the SERVER's own path is load-bearing, not a shortcut.** The root comes from
`server._STATIC` rather than being rebuilt here, because a check against a different directory
than the one Starlette mounts is a check about a different question. Two copies of that path is
exactly how a bundle could serve one tree and be checked on another.

**This half does not prove SERVING, and must never be read as though it did.** `(aad)`'s criterion
is a 200 with the right byte count, and an in-process HTTP request to ourselves would test the
reporter as much as the app - the reasoning already written into the packaging job's own comments.
So the two halves are named as halves and kept apart: **this one proves the bytes were collected
and are intact; the packaging job proves they are served.** Collapsing them for convenience gives
back a green tick that covers less than it appears to.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from truestill_core.selfcheck import Finding, Status, core_findings

from truestill_app.server import _STATIC

#: The faces the app declares in `tokens.css`. Book and Bold only - 600 resolves to Bold by CSS
#: weight matching, measured when they were bundled.
FACES = ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf")

#: Bitstream Vera binds its notice to *copies of the typefaces*, so an artifact carrying the fonts
#: without this file is a **licence defect**, not a missing extra.
LICENCE_NAME = "LICENSE-DejaVu.txt"

#: The clause that does the binding. Checked for content rather than existence, because a
#: truncated or reflowed notice satisfies `is_file()` and discharges nothing.
_BINDING_CLAUSE = "shall be included in all copies of one or more of the Font Software typefaces"

#: A TrueType file starts with this. An LFS pointer or a zero-length placeholder would satisfy
#: `is_file()` and render nothing, which is the failure a bundler is most likely to produce.
_TRUETYPE_MAGIC = b"\x00\x01\x00\x00"


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def font_findings(root: Path | None = None) -> list[Finding]:
    """One finding per face plus one for the notice, reported by size and digest.

    ``root`` exists so a test can point at a directory with a face removed or a notice truncated:
    a check that has never been seen to report `MISSING` is not known to be able to.
    """
    fonts = (root if root is not None else _STATIC) / "fonts"
    findings = [_face_finding(fonts / face) for face in FACES]
    findings.append(_licence_finding(fonts / LICENCE_NAME))
    return findings


def _face_finding(path: Path) -> Finding:
    name = f"font {path.name}"
    try:
        payload = path.read_bytes()
    except OSError:
        return Finding(name, Status.MISSING, f"not in this install ({path})", {"path": str(path)})
    evidence: dict[str, str | int] = {
        "path": str(path),
        "bytes": len(payload),
        "sha256": _digest(payload),
    }
    if payload[:4] != _TRUETYPE_MAGIC:
        return Finding(name, Status.DEGRADED, f"not a TrueType file ({path})", evidence)
    return Finding(name, Status.OK, f"{len(payload)} bytes", evidence)


def _licence_finding(path: Path) -> Finding:
    """**Read as BYTES, then decode - never `read_text`.**

    `read_text` applies universal newlines, so a CRLF checkout decodes to LF and the reported
    length is the *translated* length rather than the file's. Measured on Windows (run
    31671053639): the artifact reported **4007** bytes for a file the checkout held at **4080** -
    73 line endings - and the comparison against the repository failed on a file that was
    byte-for-byte correct. A byte count that changes with how you read it is not a byte count.
    The typefaces never showed it because binary reads are not translated.
    """
    try:
        payload = path.read_bytes()
    except OSError:
        return Finding(
            "font licence",
            Status.MISSING,
            f"the Bitstream Vera notice is not beside the typefaces ({path})",
            {"path": str(path)},
        )
    text = payload.decode("utf-8", errors="replace")
    evidence: dict[str, str | int] = {
        "path": str(path),
        "bytes": len(payload),
        "sha256": _digest(payload),
    }
    # Flattened, because the canonical notice is hard-wrapped and must not be reflowed to suit
    # an assertion - the same reason `test_bundled_font_ships_with_its_licence.py` flattens.
    if _BINDING_CLAUSE not in " ".join(text.split()):
        return Finding(
            "font licence",
            Status.DEGRADED,
            f"the notice is present but does not carry the clause that binds it ({path})",
            evidence,
        )
    return Finding("font licence", Status.OK, f"{len(payload)} bytes", evidence)


def app_findings(root: Path | None = None) -> list[Finding]:
    """Everything a packaged truestill can say about itself: core's answers plus the assets."""
    return [*core_findings(), *font_findings(root)]
