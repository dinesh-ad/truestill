"""A living document's citations must resolve. `(ago)`

The exposure was recorded in `BACKLOG.md`'s own text long before anything acted on it: **"Nothing
would tell us. Checked: no test or guard asserts a line number."** The pattern has a name - *docs
as tests* - and the study behind it found **230 stale code-element references across 82
repositories**, 23% of those analysed.

⚠ **THE FORMAT IS A SYMBOL, NOT A LINE, SINCE 2026-09-01, and that is the whole of `(ago)`'s
second half.** The line format failed in a way this guard could not see: **a fifteen-line comment**
added to `app.js` displaced **46 citations across 16 documents, 18 of them live**, and every one
landed on real code. Two citations in `(abz)` had been wrong for weeks and surfaced only because
the shift happened to push one onto a blank line, so of ~48 wrong pointers the old guard reported
**one, by accident**. `scripts/cite_symbols.py` carries the measurements and the refusal of a
content hash.

⚠ **THE SCOPE IS "LIVING", NOT "ALL", AND THAT IS UNCHANGED.** A record is never rewritten - *a
record rewritten to stay correct stops being one* - so research notes, audits, soak records and
`SHIPPED.md` closures keep the citations they were written with, **line numbers included**. Two
formats coexist in the corpus **because the documents differ in kind**, not because a migration
was left half-done: a living document is read in order to *do* something and must resolve today;
a record says what was true when it was written.

⚠ **WHAT IT STILL CANNOT SEE, stated rather than implied** (§4's twenty-second member):

* **A symbol whose body was rewritten completely** is still a valid citation. That is docpin's
  content-hash case, and it was **refused on a measurement**: 83 of 220 cited symbols had their
  body change in twelve days, so a hash would have demanded 83 re-records in that window.
* **A symbol that no longer says what the prose claims.**
* **Precision inside a long symbol.** 207 citations point inside a body rather than at a
  declaration; the reader now scans the enclosing symbol. Median **32 lines**, 74% under 50, but
  **12% over 80**. That is the trade this format makes - a precise pointer that decays fast, for a
  coarser one that holds - and it is named here so whoever writes the next citation knows it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import cite_symbols as cite

ROOT = Path(__file__).resolve().parents[3]

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

#: Basenames carried by BOTH `truestill-core` and an app service. Under the line format a citation
#: into one of these was **skipped in silence** - *"a bare basename several files share; not this
#: guard's question"* - which left **46 citations, 13% of the corpus**, unchecked. The symbol is
#: the discriminator: measured over all six pairs, **0 of 237 symbol names appear on both sides**.
SHARED_BASENAMES = ("migrate.py", "trips.py", "backup.py", "takeout.py", "bake.py", "verify.py")


def _tracked() -> set[str]:
    return cite.tracked_files()


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
    """Everything wrong with `document`'s citations. **It never skips in silence.**

    The line guard returned early on an ambiguous basename, and that early return was 13% of the
    corpus going unchecked without saying so. Anything this cannot resolve is now reported.
    """
    text = document.read_text(encoding="utf-8")
    found: list[str] = []

    for match in cite.SYMBOL_CITE.finditer(text):
        raw, symbol = match.group(1), match.group(2)
        if any(marker in raw for marker in cite.FOREIGN):
            continue
        _, why = cite.resolve(raw, symbol, tracked)
        if why is not None:
            found.append(f"{match.group(0)} - {why}")

    for match in cite.LINE_CITE.finditer(text):
        raw, low = match.group(1), int(match.group(2))
        if any(marker in raw for marker in cite.FOREIGN):
            continue
        options = cite.candidates(raw, tracked)
        if not options:
            found.append(f"{match.group(0)} - no tracked file of that name")
            continue
        if len(options) > 1:
            found.append(f"{match.group(0)} - {len(options)} files of that name; name the symbol")
            continue
        target = options[0]
        lines = (ROOT / target).read_text(encoding="utf-8", errors="replace").splitlines()
        top = int(match.group(3)) if match.group(3) else low
        if top > len(lines):
            found.append(f"{match.group(0)} - {target} has {len(lines)} lines")
        elif not lines[low - 1].strip():
            found.append(f"{match.group(0)} - {target} line {low} is blank")
        elif (span := cite.enclosing(cite.symbols_for(target), low)) is not None:
            # ⚠ THE ANTI-REGRESSION RULE, and it is why the format cannot quietly come back.
            # A line is a legitimate pointer only where no symbol encloses it - a `.toml` key, a
            # `.yml` step, an import block, a module docstring. Where a symbol DOES enclose it,
            # the citation has a stable name available and must use it.
            found.append(f"{match.group(0)} - inside {span.name}; cite the symbol, not the line")

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
        + "\n\nFix the citation - the code moved and the document did not. Cite a SYMBOL "
        "(`drive.py:library_independence`), not a line; `uv run python scripts/cite_symbols.py "
        "<doc>` converts one. If the document is a RECORD of something that was true once, it "
        "does not belong in this guard's scope; see the module docstring for why records are "
        "excluded rather than updated."
    )


def test_the_guard_is_actually_reading_citations() -> None:
    """Anti-vacuity, RE-BASED for the symbol format rather than ported.

    A scope built from a glob and a regex can silently match nothing, and a guard over an empty
    set passes forever. `(agn)` is the local precedent: a stub whose breakage was
    indistinguishable from the condition under test.

    **How the thresholds were measured**, 2026-09-01, so a later reader can re-derive rather than
    trust them: `_living_documents()` yields **128** documents, **50** of which carry citations;
    after the conversion those hold **315 symbol citations** and **16 line citations** - the
    latter all into `.toml`, `.yml`, `.html`, an import block or a module docstring, where no
    symbol exists. The old thresholds were `> 20` documents and `> 50` citations against a corpus
    of 348 line citations; `> 200` keeps the same generous margin under 315 and still catches a
    regex that stops matching or a scope that collapses.
    """
    documents = _living_documents()
    assert len(documents) > 20, f"the living-document scope collapsed to {len(documents)}"

    seen = sum(
        len(cite.SYMBOL_CITE.findall((ROOT / d).read_text(encoding="utf-8"))) for d in documents
    )
    assert seen > 200, f"only {seen} symbol citations found across {len(documents)} documents"
    assert _problems(ROOT / "docs/BACKLOG.md", _tracked()) == [], "fixture check: backlog is clean"


def test_the_six_shared_basenames_are_checked_rather_than_skipped() -> None:
    """🔑 **The measurable win, asserted rather than taken on trust.**

    Under the line format a citation naming one of these was skipped in silence - 46 of 348, 13%
    of the corpus, and exactly the pairs where confusing core with the app service matters most.
    Two consequences of that hole were found the day it closed: `service/trips.py:498` and
    `service/backup.py:51` both pointed at **blank lines**, and `trips.py:476` pointed **past the
    end** of a 224-line file. The old guard reported none of the three.
    """
    tracked = _tracked()
    documents = _living_documents()
    citations = [
        match.group(0)
        for document in documents
        for match in cite.SYMBOL_CITE.finditer((ROOT / document).read_text(encoding="utf-8"))
        if Path(match.group(1)).name in SHARED_BASENAMES
    ]

    assert citations, "fixture check: the corpus should still cite the shared-basename files"

    unresolved = []
    for citation in citations:
        raw, symbol = citation.rsplit(":", 1)
        if cite.resolve(raw, symbol, tracked)[1] is not None:
            unresolved.append(citation)
    assert unresolved == [], f"skipped or unresolvable: {unresolved}"


def test_a_line_citation_is_refused_where_a_symbol_exists(tmp_path: Path) -> None:
    """The anti-regression rule: the old format cannot come back where a name is available.

    The fixture *locates* its target at runtime rather than hardcoding a line, which in a file
    about line-citation rot is not a stylistic choice.
    """
    tracked = _tracked()
    target = "packages/truestill-core/src/truestill_core/drive.py"
    span = next(s for s in cite.symbols_for(target) if s.name == "library_independence")
    inside = span.start + (span.end - span.start) // 2

    document = tmp_path / "doc.md"
    document.write_text(f"see `drive.py:{inside}`\n", encoding="utf-8")
    problems = _problems(document, tracked)
    assert problems, "a line citation where a symbol exists was accepted"
    assert "cite the symbol" in problems[0]

    document.write_text("see `drive.py:library_independence`\n", encoding="utf-8")
    assert _problems(document, tracked) == [], "the symbol form was rejected"


def test_the_detector_catches_a_symbol_that_is_not_there(tmp_path: Path) -> None:
    """⚠ **THE DETECTOR NEEDS ITS OWN INPUT, and this was found by two surviving mutations.**

    With the corpus clean, deleting a rule killed nothing - there was no longer anything for it to
    find. A guard whose only evidence is *the world happens to be tidy* is unfalsifiable and would
    stay green through its own deletion. So the rules are exercised against a document written
    here, resolving against **real tracked files** rather than a stub.
    """
    tracked = _tracked()
    document = tmp_path / "doc.md"

    document.write_text("see `drive.py:library_independence`\n", encoding="utf-8")
    assert _problems(document, tracked) == [], "a citation onto a real symbol was called stale"

    document.write_text("see `drive.py:no_such_symbol_at_all`\n", encoding="utf-8")
    assert _problems(document, tracked), "a citation onto a missing symbol was not caught"

    document.write_text("see `no_such_module_anywhere.py:whatever`\n", encoding="utf-8")
    assert _problems(document, tracked), "a citation into a file that does not exist was not caught"

    lines = (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines()
    document.write_text(f"see `pyproject.toml:{len(lines) + 500}`\n", encoding="utf-8")
    assert _problems(document, tracked), "a line past the end of a symbol-less file was not caught"


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
    day it was written. **They keep line numbers, and that is a decision rather than an unfinished
    migration**: a record says what was true when it was written.
    """
    documents = _living_documents()

    assert "docs/SHIPPED.md" not in documents, "a closure is provenance, not instruction"
    assert not any(
        "-record.md" in d or "research/" in d.replace("research/backlog/", "") for d in documents
    )
