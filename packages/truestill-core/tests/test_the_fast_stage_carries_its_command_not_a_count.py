"""The FAST stage's test count is a command, never a literal - and it was a literal in five files.

**The defect, reproduced before this was written.** `(ajx)` made the two-stage split binding on
2026-09-03 and described the fast stage as *"40 s over 3,543 tests"*. Four days later the suite
collected **3,570**, and the sentence had been copied into five files - `CLAUDE.md`, the binding
`IMPLEMENTATION_STANDARDS.md`, `BACKLOG.md`, `ajx.md`, and **`.github/workflows/ci.yml`**, the
banner a person reads when deciding whether to dispatch the browser lane before tagging. All five
were wrong together, and nothing said so.

⚠ **This is the fourth time in four days that a stated figure went stale silently**, which is what
makes it a class rather than a slip: `(aka)`'s sweep, the document map's counts, §4's own member
count, and a "92%" written into an index header that was wrong within ten minutes. **The remedy is
the one P210 arrived at: carry the command, not the number.** This makes it a control instead of a
practice - `ENGINEERING_STANDARD.md` §4's twenty-seventh member is explicit that a rule which
depends on being remembered is not one.

⚠ **THE SCOPE IS DELIBERATELY ONE CLAIM, AND THAT IS NOT TIMIDITY - IT IS THE MEASUREMENT.** A
broad guard - *no bare test count anywhere* - was designed first and **refuted by counting**: of
fifteen test-count literals in the canon and the open bodies, **ten are legitimate** (dated
readings, quoted historical figures shown as wrong, and a performance table under a dated header).
A guard refusing those would fire on ordinary work, get switched off, and take its real coverage
with it - which is the failure §4's member 27 names in as many words. So this guards the one claim
that is a **standing rule** rather than a reading, and the rest of the class is a practice.

**The discriminator, measured rather than tuned**: a line stating a test count, with no date on
it, within two lines of `make check`. Against the tree that is **five hits and zero false
positives, stable from a two-line window out to five** - so it is not balanced on a magic number.
A dated line is a reading and is allowed; that is how `ci.yml`'s own *"3,498 tests on 2026-09-02"*
and the handoffs stay legal.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: The canon plus the workflow banners. **Not `*.md`** - `(aka)`: a sweep is only as wide as its
#: pathspec, and `ci.yml` held one of the five copies precisely because an earlier sweep matched
#: markdown alone. Records are out of scope by construction: a record says what was true when it
#: was written, and `trip-grouping-research.md` and `handoff-2026-09-01.md` both legitimately
#: state a count from their own day.
CANON = (
    "CLAUDE.md",
    "docs/PROJECT_STATUS.md",
    "docs/ENGINEERING_STANDARD.md",
    "docs/IMPLEMENTATION_STANDARDS.md",
    "docs/DECISIONS.md",
    "docs/BACKLOG.md",
    "docs/PERFORMANCE.md",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
)

#: How many lines either side of the count are searched for `make check`. Two, and the choice is
#: reported rather than asserted: the hit set is identical at 2, 3, 4 and 5.
_WINDOW = 2

_COUNT = re.compile(r"[0-9][0-9,]{2,}\s+tests")
_DATE = re.compile(r"20\d\d-\d\d-\d\d")


def _scope() -> list[str]:
    """The canon, plus every open backlog body - a ruling's body carries the same claim."""
    bodies = subprocess.run(
        ["git", "ls-files", "docs/research/backlog/*.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [p for p in (*CANON, *bodies) if (ROOT / p).is_file()]


def offenders_in(name: str, text: str) -> list[str]:
    """Every place `text` writes the fast stage's size as a number instead of a command.

    **Takes the text, never a path**, so a mutation is driven with a string and nothing is ever
    written into the repository to test this. §4: *"a mutation harness that dies leaves the mutant
    on disk, and `finally` does not run when the process is killed"* - a guard about stale claims
    has no business risking that to prove itself.
    """
    lines = text.split("\n")
    found: list[str] = []
    for i, line in enumerate(lines):
        if not _COUNT.search(line) or _DATE.search(line):
            continue
        window = " ".join(lines[max(0, i - _WINDOW) : i + _WINDOW + 1])
        if "make check" in window:
            found.append(f"{name}:{i + 1}: {line.strip()[:96]}")
    return found


def literal_counts(paths: list[str]) -> list[str]:
    """`offenders_in` over the tree."""
    found: list[str] = []
    for name in paths:
        found.extend(offenders_in(name, (ROOT / name).read_text(encoding="utf-8")))
    return found


def test_the_fast_stage_is_described_by_a_command_not_a_test_count() -> None:
    """A number here is a claim about the tree that nothing re-checks, in a rule about what runs
    on every push. Five copies of it were wrong simultaneously."""
    offenders = literal_counts(_scope())

    assert not offenders, (
        "the fast stage's size is stated as a literal test count, which goes stale silently:\n    "
        + "\n    ".join(offenders)
        + "\n\nWrite the command instead - `uv run pytest --collect-only -q | tail -1` - or date "
        "the line, which makes it a reading rather than a standing claim."
    )


def test_the_guard_is_reading_the_canon_and_the_workflows() -> None:
    """The cry-wolf half. An empty scope, or a pathspec that lost the workflows, would make the
    test above pass while checking nothing - and the workflow copy is the one `(aka)` was filed
    about, so its absence is the specific silence this must not have."""
    scope = _scope()

    assert len(scope) > 100, f"only {len(scope)} files in scope; the body glob is not reading"
    assert ".github/workflows/ci.yml" in scope, "the workflow banner is out of scope again"
    assert any("make check" in (ROOT / p).read_text(encoding="utf-8") for p in scope), (
        "no file in scope mentions `make check`; the detector cannot fire"
    )


def test_the_guard_sees_a_count_written_back_in() -> None:
    """Proved by mutation against the real shape rather than asserted: the sentence as it stood on
    2026-09-04, which was wrong in five files at once. Driven as a string - nothing is written."""
    sentence = "**FAST every push** (`make check`, 40 s over 3,543 tests, plus contract guards"

    assert offenders_in("synthetic.md", sentence), (
        "a re-inserted literal count beside `make check` was not detected"
    )


def test_a_dated_reading_is_left_alone() -> None:
    """The other half, and it is what keeps the guard from firing on ordinary work. `ci.yml` says
    *"3,498 tests on 2026-09-02"* and the handoffs record their own day's count; both are readings,
    not standing claims, and refusing them is how a guard gets switched off."""
    reading = "`make check` ran 3,570 tests on 2026-09-04."

    assert not offenders_in("synthetic.md", reading), (
        "a dated reading was refused; the guard would fire on ordinary work"
    )


def test_the_count_and_the_make_check_mention_must_be_near_each_other() -> None:
    """The window is what stops this becoming *no test count anywhere*, which the census refuted:
    ten of fifteen in-scope literals are legitimate. A count far from any `make check` is one of
    those and must pass."""
    far = "\n".join(["The suite has 2,849 tests."] + ["filler"] * 6 + ["Run `make check` first."])

    assert not offenders_in("synthetic.md", far), "the window is not bounding the detector"
