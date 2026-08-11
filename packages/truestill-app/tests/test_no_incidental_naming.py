"""No incidental vendor or personal naming in the repo (2026-07-31 naming sweep).

**Incidental is the whole point.** A name is incidental when the code would mean exactly the
same thing without it: "exiftool is 74% of wall on <vendor>" is a measurement on *a cloud FUSE
mount*, and naming the vendor tells a reader nothing they can act on while tying an open-source
repo to one person's storage provider. A name is **not** incidental when removing it would make
the code lie about what it does, and those are allowlisted below with the reason attached.

**What is deliberately still here**, because a blanket ban would have destroyed it:

* **Google Takeout, rclone, exiftool, SQLite, Playwright** - real formats, dependencies and
  tools. Renaming these would misdescribe the feature. They are not in :data:`BANNED` at all.
* **Cited evidence** - PhotoPrism, Immich, IMatch, PixSort, Lightroom and the rest, where a
  docstring cites another tool's behaviour to justify an invariant. `hash_cache.py`'s
  size+mtime rule *is* PhotoPrism's rule, and IMatch is the documented counter-example that
  bounds it. Strip those and the invariant is left with no stated reason, which is the drift
  four audit passes were spent removing. Also not in :data:`BANNED`.
* **Drive nicknames** - "The Memory Cabinet", "Output". They are named corpora:
  `PERFORMANCE.md` §2.1 binds every measurement row to state its corpus, and "a cloud mount" is
  not traceable. **The fenced folder is NO LONGER among them** - it was, on the argument that
  a fence nobody can name is a fence nobody can enforce, and the maintainer reversed that on
  2026-08-11: a public repository may not name his private tree, and the fence is enforced
  from his environment rather than from this file.
* **Wayanad** - a place name, not personal data, and
  ``test_the_real_wayanad_run_is_one_full_proposal_no_trim`` records that the fixture was checked
  against a remembered trip. ``test_the_real_trip_run`` would lose exactly that.

The allowlist stores the **reason**, not just the path, so the next person reads the ruling
rather than an unexplained exemption.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

#: Names that carry no meaning the surrounding text does not already carry. Matched
#: case-insensitively, anywhere in a line or a path, after the allowlist has been subtracted.
BANNED: dict[str, str] = {
    "pcloud": "a storage vendor; say what the mount *is* (cloud FUSE mount, network mount)",
    "dropbox": "a storage vendor named incidentally",
    "onedrive": "a storage vendor named incidentally",
    "icloud": "a storage vendor named incidentally",
    "tresorit": "a storage vendor named incidentally",
    "icedrive": "a storage vendor named incidentally",
    "backblaze": "a storage vendor named incidentally",
    "dinesh": "the maintainer's personal name; say 'the maintainer'",
    # ADDED 2026-08-11 after the maintainer ruled that no path revealing his cloud storage or
    # his private folder structure may appear in a PUBLIC repository. This guard did not fail:
    # it was built to PERMIT these, on the ruling that "a fence nobody can name is a fence
    # nobody can enforce". That ruling has been reversed, so the permission goes with it.
    "crypto folder": "the maintainer's locked folder; say 'the fenced folder'",
    "vintage": "a level of the maintainer's private tree; use Input/2013 or Input/2014",
}

# A PLACE NAME IS EXPOSURE WHEN IT IS HIS FOLDER, AND EVIDENCE WHEN IT IS A DATASET ROW. Read this
# before widening BANNED. On 2026-08-11 a blanket sweep replaced two Indian city names everywhere
# they appeared, which was right inside a folder name taken from the fenced tree and WRONG inside
# `reverse-geocoding-research.md`, where the same two words are gazetteer test points cited beside
# Chennai with populations and coordinates. The sweep turned a measurement record into nonsense -
# a lookup that "resolves to its own official name" - and it was caught by reading the diff rather
# than by any test.
#
# So the question is never "is this word a place". It is **whose sentence is it in**: a path the
# maintainer typed, or a row in a public dataset the record is measuring. The first is exposure and
# goes; the second is the evidence the record's conclusion rests on, and removing it leaves an
# assertion with nothing behind it - the same damage as rewriting a record to match the present.
#
# The practical consequence for this file: BANNED holds names of HIS structure, never bare
# toponyms. A term that would also match dataset rows belongs in a scoped pattern or nowhere.

#: **AN ALLOWLIST THAT GREW TO ACCOMMODATE A RULING THAT WAS LATER REVERSED IS THE SILENT-GROWTH
#: FAILURE `IMPLEMENTATION_STANDARDS.md` 6.2 ALREADY DOCUMENTS FOR THE DASH SWEEP.** Two entries
#: were removed on 2026-08-11: one exempted `encrypted pCloud mount` / `pCloud Crypto` in a
#: measurement row, and one - added the day before - exempted `~/pCloudDrive` so the corpus fence
#: could name its own path. Both were sound under the rule of their day and both were exposure
#: under the next one. An entry here must be re-justified when the ruling behind it moves, not
#: inherited.
#:
#: ``(pattern, reason)`` - text that legitimately contains a banned term. Subtracted from each
#: line *before* the scan, so these survive without exempting the whole file around them.
ALLOWED: tuple[tuple[str, str], ...] = (
    (
        r"\| (Google Takeout|Facebook|Flickr|Amazon Photos|Dropbox|iCloud) \|",
        (
            "the (jj) export-format table in SHIPPED.md. These names ARE the evidence: the "
            "scope decision - archive reading is source-agnostic, and .7z is refused because "
            "no service emits it - rests on which services export which format. Stripped, the "
            "table asserts a conclusion with nothing behind it. Same standing as the cited "
            "evidence below (PhotoPrism, IMatch): a vendor named to justify an invariant. "
            "Scoped to table rows so the names cannot spread into prose."
        ),
    ),
    (
        (
            r"pCloud / Dropbox / OneDrive \*\*mounted as a drive\*\*|"
            r"Google Drive API, S3, iCloud web"
        ),
        (
            "the two enumerations in BACKLOG.md's `(aav)` scope decision, and they are the "
            "entry's whole function: it exists so a prospective user learns in one line whether "
            "their setup is supported, and 'a cloud FUSE mount' does not answer 'does it work "
            "with mine?'. The distinction being drawn - mounted filesystem yes, web API no - is "
            "also invisible without examples on both sides, since the same company can appear "
            "on either. Same standing as the (jj) export-format table: vendors named to make a "
            "scope ruling checkable rather than to decorate it. Scoped to the two exact phrases "
            "so the names cannot spread into surrounding prose."
        ),
    ),
    (
        r'for vendor in \("pcloud", "icedrive", "dropbox", "onedrive"\):',
        (
            "the assertion in `test_run_health.py` that proves the disk-full message names NO "
            "cloud vendor. The names ARE the assertion here: the design ruling was to report "
            "the free-space DELTA rather than maintain a per-vendor cache-path table, and a "
            "test that checked for a genericised placeholder would assert nothing. Same "
            "standing as the (jj) export-format table and (aav)'s scope enumeration - vendors "
            "named to make a ruling checkable. Scoped to the one line."
        ),
    ),
    (
        r"github\.com/dinesh-ad/truestill",
        (
            "the real repository URL - package metadata, README links and advisories resolve "
            "to it, so it is an address rather than prose"
        ),
    ),
    (
        r"Copyright \d{4} Dinesh A",
        "the licence copyright line, which must name the real holder to be a licence at all",
    ),
    (
        r"dinesh-ad(?!/)",
        "the literal git identity the commit-identity policy checks against; a value, not prose",
    ),
    (
        r"rclone supports[^.]*",
        (
            "rclone.py documents which remotes a real dependency actually supports - the list "
            "is the capability described, and genericising it would make the sentence say nothing"
        ),
    ),
)

#: Files this guard cannot scan without flagging itself.
SKIP = {"packages/truestill-app/tests/test_no_incidental_naming.py"}


def _tracked_files() -> list[str]:
    """Everything that WILL be committed, not only what already is.

    ``git ls-files`` alone lists the index, so a brand-new file is invisible to this guard until
    the moment it is added - which is after the `make check` that was supposed to catch it. That
    is a false green with a delay fuse: the run that could act on it passes, and the failure
    arrives on the next one, or on CI. ``--others --exclude-standard`` adds untracked files while
    still honouring .gitignore, so the guard sees the working tree the way a reviewer would.
    """
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line and line not in SKIP]


def _strip_allowed(text: str) -> str:
    for pattern, _reason in ALLOWED:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text


def _offences(relative: str) -> list[str]:
    """``path:line: term`` for every banned term left after the allowlist is subtracted."""
    path = REPO / relative
    found: list[str] = []
    for term in BANNED:
        if term in _strip_allowed(relative).lower():
            found.append(f"{relative}: '{term}' in the FILE NAME")
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return found  # binary or unreadable: nothing to read, nothing to claim
    for number, line in enumerate(content.splitlines(), start=1):
        bare = _strip_allowed(line).lower()
        found.extend(f"{relative}:{number}: '{term}'" for term in BANNED if term in bare)
    return found


def test_no_incidental_vendor_or_personal_naming() -> None:
    offences = [o for relative in _tracked_files() for o in _offences(relative)]
    assert not offences, (
        f"{len(offences)} incidental name(s) - each is a vendor or personal name the "
        "surrounding text does not need:\n"
        + "\n".join(offences[:60])
        + ("\n  ... and more" if len(offences) > 60 else "")
        + "\n\nEither reword it, or add an ALLOWED entry stating why the name is load-bearing."
    )


def test_the_guard_catches_each_banned_term(tmp_path: Path) -> None:
    """Every entry in BANNED must actually be detectable - a term nobody can trip is decoration."""
    for term in BANNED:
        probe = tmp_path / "probe.md"
        probe.write_text(f"measured over a {term.upper()} mount\n", encoding="utf-8")
        hits = [
            line
            for number, line in enumerate(probe.read_text(encoding="utf-8").splitlines(), 1)
            if term in _strip_allowed(line).lower()
        ]
        assert hits, f"BANNED lists '{term}' but the scanner cannot see it"


def test_the_guard_spares_the_legitimate_references() -> None:
    """Cry-wolf half: the allowlisted forms and the kept names must not be reported.

    The kept names are the load-bearing ones - a dependency, an input format, cited evidence,
    a named corpus, a place. If this ever fails, the sweep has started deleting meaning.
    """
    spared = [
        "Homepage = 'https://github.com/dinesh-ad/truestill'",
        "   Copyright 2026 Dinesh A",
        "- **Commit identity policy:** `dinesh-ad`; no co-author trailers.",
        "any remote rclone supports -- pCloud, Dropbox, S3, SFTP, Google Drive -- is usable",
        "Size+mtime invalidation matches PhotoPrism's rule and is honest when the bytes change.",
        "Google Takeout's photoTakenTime is read before the filename tier.",
        "measured on The Memory Cabinet, 2,269 copies over a cloud FUSE mount",
        "test_the_real_wayanad_run_is_one_full_proposal_no_trim",
    ]
    for line in spared:
        bare = _strip_allowed(line).lower()
        flagged = [term for term in BANNED if term in bare]
        assert not flagged, f"flagged a legitimate reference {flagged}: {line}"
