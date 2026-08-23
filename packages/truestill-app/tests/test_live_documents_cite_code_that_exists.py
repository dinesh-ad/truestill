"""A document describing work still to be done must point at code that exists. `(ago)`

`BACKLOG.md` records this exposure in its own text, under *Consciously out of scope*: **"Nothing
would tell us. Checked: no test or guard asserts a line number."** It was written about a
JavaScript formatter rewriting `app.js`, and the exposure is wider than that - **632 `path:line`
citations** across the corpus, drifting under every ordinary refactor.

The industry name for the remedy is **docs as tests**: use tooling to detect stale documentation
and fail the build on it, rather than relying on review. The published study behind it found *230
stale code-element references across 82 repositories*, 23% of those analysed, and the technique it
recommends is exactly this - a cheap grep that flags references which have vanished from source.

⚠ **THE SCOPE IS "LIVING", NOT "ALL", AND THAT IS THE WHOLE DESIGN.** This repo's doctrine is that
**a record is never rewritten** - *"a record rewritten to stay correct stops being one"* - so
research notes, audits, soak records and `SHIPPED.md` closures describe what was true when they
were written and their citations are allowed to age. Measured 2026-08-23: **31 of 32** unresolved
citations in the corpus sit in exactly those documents. A guard over all of them would go red on
the past on the day it was written, get switched off, and take its real signal with it
(`ENGINEERING_STANDARD.md` §4).

**What is left is the set where a stale pointer actively misleads**: the binding canon, the current
guides, and the body of every backlog entry that is **still open** - the documents somebody reads
in order to *do something*.

⚠ **WHAT IT CANNOT SEE, stated rather than implied** (§4's twenty-second member). It checks that a
cited file exists, that the line is in range, and that the line is **not blank**. It cannot tell
that a line moved *within* a file to another piece of real code. Measured on the audit that
produced it: of five drifted citations found by hand, this would have caught **two**. The blank
line is the cheap half of the signal and nobody cites one on purpose; catching the rest honestly
would mean citing symbols rather than line numbers, which is a different and larger change.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: A citation names a source file and a line. Documentation-only references (`.md:12`) are
#: excluded deliberately: prose moves for prose reasons, and `test_doc_pointers_resolve.py`
#: already owns whether a document exists at all.
CITE = re.compile(r"([A-Za-z0-9_./-]+\.(?:py|js|css|html|yaml|yml|toml|sh)):(\d+)(?:-(\d+))?")

#: Third-party files legitimately cited by name and correctly absent from this tree. Pillow's
#: internals are quoted by `(aev)` and the soak records because the defect was **in** them.
FOREIGN = ("TiffImagePlugin.py", "Image.py", "PIL/")

#: Binding canon and current guides. `SHIPPED.md` is deliberately NOT here: a closure describes a
#: run that happened, which makes it provenance rather than instruction.
LIVING = (
    "CLAUDE.md",
    "README.md",
    "SECURITY.md",
    "docs/PROJECT_STATUS.md",
    "docs/ENGINEERING_STANDARD.md",
    "docs/IMPLEMENTATION_STANDARDS.md",
    "docs/DECISIONS.md",
    "docs/BACKLOG.md",
    "docs/PERFORMANCE.md",
    "docs/cli-app-parity.md",
)


def _tracked() -> set[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return set(out.stdout.split())


def _open_letters() -> set[str]:
    """The letters `BACKLOG.md` still carries as open work.

    Read from the document rather than listed here, so an entry that ships leaves this guard's
    scope in the same commit that moves it - no second list to keep in step.
    """
    text = (ROOT / "docs/BACKLOG.md").read_text(encoding="utf-8")
    return set(re.findall(r"^- \*\*\(([a-z]{1,3})\)", text, re.MULTILINE))


def _living_documents() -> list[str]:
    bodies = [f"docs/research/backlog/{letter}.md" for letter in _open_letters()]
    return [d for d in (*LIVING, *bodies) if (ROOT / d).is_file()]


def _problems(document: Path, tracked: set[str]) -> list[str]:
    by_name: dict[str, list[str]] = {}
    for path in tracked:
        by_name.setdefault(Path(path).name, []).append(path)

    found = []
    for match in CITE.finditer(document.read_text(encoding="utf-8")):
        raw, low, high = match.group(1), int(match.group(2)), match.group(3)
        if any(marker in raw for marker in FOREIGN):
            continue
        exact = raw.lstrip("./")
        candidates = by_name.get(Path(raw).name, [])
        if exact in tracked:
            target = exact
        elif len(candidates) == 1:
            target = candidates[0]
        elif not candidates:
            found.append(f"{match.group(0)} - no tracked file of that name")
            continue
        else:
            continue  # a bare basename several files share; not this guard's question
        lines = (ROOT / target).read_text(encoding="utf-8", errors="replace").splitlines()
        top = int(high) if high else low
        if top > len(lines):
            found.append(f"{match.group(0)} - {target} has {len(lines)} lines")
        elif not lines[low - 1].strip():
            found.append(f"{match.group(0)} - {target} line {low} is blank")
    return found


def test_every_living_document_cites_code_that_exists() -> None:
    """The guard itself. A citation into open work must resolve, or it sends someone nowhere."""
    tracked = _tracked()
    stale = {
        document: problems
        for document in _living_documents()
        if (problems := _problems(ROOT / document, tracked))
    }

    assert not stale, (
        "these documents describe work still to be done and cite code that is not there:\n"
        + "\n".join(f"  {d}\n      " + "\n      ".join(p) for d, p in sorted(stale.items()))
        + "\n\nFix the citation - the code moved and the document did not. If the document is a "
        "RECORD of something that was true once, it does not belong in this guard's scope; see "
        "the module docstring for why records are excluded rather than updated."
    )


def test_the_guard_is_actually_reading_citations() -> None:
    """Anti-vacuity, and it is not optional here.

    A scope built from a glob and a regex can silently match nothing - a renamed directory, a
    tightened pattern - and a guard over an empty set passes forever. `(agn)` is the local
    precedent: a stub whose breakage was indistinguishable from the condition under test.
    """
    documents = _living_documents()
    assert len(documents) > 20, f"the living-document scope collapsed to {len(documents)}"

    tracked = _tracked()
    seen = sum(len(CITE.findall((ROOT / d).read_text(encoding="utf-8"))) for d in documents)
    assert seen > 50, f"only {seen} citations found across {len(documents)} documents"
    assert _problems(ROOT / "docs/BACKLOG.md", tracked) == [], "fixture check: the backlog is clean"


def test_the_detector_catches_a_blank_line_and_a_line_past_the_end(tmp_path: Path) -> None:
    """⚠ **THE DETECTOR NEEDS ITS OWN INPUT, and this was found by two surviving mutations.**

    With the corpus clean, deleting the blank-line rule and deleting the range rule each killed
    nothing - there was no longer anything for them to find. A guard whose only evidence is *the
    world happens to be tidy* is unfalsifiable, and it would stay green through its own deletion.

    So the rules are exercised against a document written here, resolving against **real tracked
    files** rather than a stub, and the blank line is *located* rather than hardcoded so the
    fixture cannot rot the way the citations it guards did.
    """
    tracked = _tracked()
    real = "packages/truestill-core/src/truestill_core/catalog.py"
    lines = (ROOT / real).read_text(encoding="utf-8").splitlines()
    blank = next(i for i, line in enumerate(lines, start=1) if not line.strip())
    code = next(i for i, line in enumerate(lines, start=1) if line.strip())

    document = tmp_path / "doc.md"

    document.write_text(f"see `catalog.py:{code}`\n", encoding="utf-8")
    assert _problems(document, tracked) == [], "a citation onto real code was reported as stale"

    document.write_text(f"see `catalog.py:{blank}`\n", encoding="utf-8")
    assert _problems(document, tracked), f"a citation onto blank line {blank} was not caught"

    document.write_text(f"see `catalog.py:{len(lines) + 500}`\n", encoding="utf-8")
    assert _problems(document, tracked), "a citation past the end of the file was not caught"

    document.write_text("see `no_such_module_anywhere.py:12`\n", encoding="utf-8")
    assert _problems(document, tracked), "a citation into a file that does not exist was not caught"


def test_the_detector_is_silent_about_third_party_files(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF.** Pillow's internals are cited by `(aev)` and the soak records because
    the defect was **in** them, and they are correctly absent from this tree. A detector that
    called those stale would be red about the one class of citation nobody can fix."""
    document = tmp_path / "doc.md"
    document.write_text("see `TiffImagePlugin.py:950` and `PIL/Image.py:1136`\n", encoding="utf-8")

    assert _problems(document, _tracked()) == []


def test_records_are_outside_the_scope_on_purpose() -> None:
    """The exclusion is the design, so it is pinned rather than left to the docstring.

    `SHIPPED.md` and the research records carry citations that have legitimately aged - measured
    at 31 of 32 unresolved in the corpus - and pulling them in would make this guard red on the
    day it was written.
    """
    documents = _living_documents()

    assert "docs/SHIPPED.md" not in documents, "a closure is provenance, not instruction"
    assert not any(
        "-record.md" in d or "research/" in d.replace("research/backlog/", "") for d in documents
    )
