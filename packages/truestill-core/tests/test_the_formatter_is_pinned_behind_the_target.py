"""This repo does not adopt PEP 758, and the flag that prevents it is not self-enforcing.

At `target-version = "py314"` the **formatter** rewrites ``except (A, B):`` into ``except A, B:``.
That is valid, and it is also visually identical to Python 2's ``except E, name:``, which BOUND
the exception rather than catching two - so a reader who learned Python 2 reads
``except OSError, ValueError:`` as *"catch OSError as ValueError"*. Unambiguous to the interpreter,
ambiguous to a person, for two characters.

⚠ **There is no configuration key**, measured against ruff 0.16.0 and 0.16.4: `[tool.ruff.format]`
rejects one, and the rewrite is the formatter gated on `target-version`, not a lint rule. The only
lever is ``--target-version py313`` per invocation.

⚠ **And that lever is silent when it fails.** A file that *already* contains the unparenthesised
form passes ``ruff format --check --target-version py313`` - it reports "1 file already formatted"
and exits 0. So an editor formatting on save reads `py314` from `pyproject.toml`, rewrites, and
nothing in the toolchain objects. This test is what makes the rule real rather than a practice.
"""

from __future__ import annotations

import ast
import itertools
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]

#: Every place the formatter runs, and the shape the flag has in each.
_INVOCATIONS = (
    ("Makefile", "ruff format --target-version py313 ."),
    ("Makefile", "ruff format --check --target-version py313 ."),
    (".github/workflows/ci.yml", "ruff format --check --target-version py313 ."),
    (".pre-commit-config.yaml", "args: [--target-version, py313]"),
)


def _tracked_python_files() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "*.py"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [_REPO / name for name in listed.stdout.split("\0") if name]


@pytest.mark.parametrize(("relative", "needle"), _INVOCATIONS)
def test_every_formatter_invocation_pins_the_target(relative: str, needle: str) -> None:
    """One unflagged `ruff format` is enough to rewrite the repo on somebody's next save."""
    text = (_REPO / relative).read_text(encoding="utf-8")
    assert needle in text, (
        f"{relative} no longer pins the formatter with {needle!r}. Without it, `ruff format` reads "
        "target-version = py314 from pyproject.toml and adopts PEP 758 across the repo."
    )


def _python_invocations_without_the_pin() -> list[str]:
    """`ruff format` spelled as argv inside a `.py` file, found by PARSING rather than matching.

    ⚠ **This function exists because the text version reported its own docstring.** The first
    draft matched `["ruff", "format", ...]` as a regex, and the paragraph explaining that it does
    so is itself such a string - §4's fifty-ninth member, caught by CI rather than by review. An
    `ast` walk sees a list of two adjacent string constants and does not see prose about one.
    """
    offenders: list[str] = []
    for path in _tracked_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.List | ast.Tuple):
                continue
            words = [
                e.value
                for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            ]
            for first, second in itertools.pairwise(words):
                if (
                    first.endswith("ruff")
                    and second == "format"
                    and "--target-version" not in words
                ):
                    offenders.append(
                        f"{path.relative_to(_REPO).as_posix()}:{node.lineno}: argv invocation"
                    )
    return offenders


def test_no_invocation_escapes_the_pin() -> None:
    """⚠ The cry-wolf half: a NEW call site would pass the test above by not existing.

    The list is only as good as its completeness, so this asks the repository rather than the
    list - §4's rule about reading a structural source instead of a narrative one.

    ⚠ **And it looks for the form each file would really use**, which is what keeps it from
    reporting its own explanation. `ruff format` written as two contiguous words is a *shell*
    invocation, so it is searched for in shell-shaped files with comments stripped. A Python file
    that ran the formatter would spell it `["ruff", "format", ...]`; the contiguous string inside
    a `.py` file is prose by construction, and `scripts/mutate_once.py` contains exactly that -
    a docstring explaining how reformatting defeats an anchor.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    offenders: list[str] = []
    for name in listed.stdout.split("\0"):
        if not name or name.endswith(".md"):
            continue
        path = _REPO / name
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if name.endswith(".py"):
                continue  # handled structurally below, not by text
            if (
                re.search(r"(?<![\w-])ruff format(?!\w)", line.split("#", 1)[0])
                and "--target-version" not in line
            ):
                offenders.append(f"{name}:{number}: {line.strip()}")
    offenders.extend(_python_invocations_without_the_pin())
    assert not offenders, (
        "a `ruff format` invocation does not pin --target-version py313:\n  "
        + "\n  ".join(offenders)
    )


def test_no_tracked_source_uses_the_unparenthesised_form() -> None:
    """The property itself, asked of the code rather than of the configuration.

    Parsed rather than grepped: `except A, B:` inside a string or a comment is not the thing being
    forbidden, and a regex over source text cannot tell the difference.
    """
    offenders: list[str] = []
    for path in _tracked_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # a fixture deliberately not valid
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or not isinstance(node.type, ast.Tuple):
                continue
            # A parenthesised tuple starts at the `(`; an unparenthesised one starts at its first
            # element, which is strictly after the `except` keyword plus a space.
            line = path.read_text(encoding="utf-8").splitlines()[node.lineno - 1]
            if not re.match(r"\s*except\*?\s*\(", line):
                offenders.append(
                    f"{path.relative_to(_REPO).as_posix()}:{node.lineno}: {line.strip()}"
                )
    assert not offenders, (
        "PEP 758's unparenthesised multi-except appears in tracked source. This repo keeps the "
        "parentheses - see pyproject.toml beside `target-version`:\n  " + "\n  ".join(offenders)
    )


# --- and the formatter must not reach into documents at all -----------------------------------


def test_the_formatter_does_not_own_fenced_blocks_in_documents() -> None:
    """A fenced ``python`` block in a document is a QUOTATION; without this it is code ruff owns.

    ⚠ **Found by it happening** (`(agf)`, 2026-08-23). `(age)` quoted one line of
    `filesystem.py` - ``free_bytes=need if free is None else free,`` , a keyword argument - and
    `make check` rewrote it to ``free_bytes = (need if free is None else free,)``, a tuple
    assignment that appears nowhere in the file. In the entry whose entire subject is a value
    being silently transformed one line after it was got right.

    **It is not only fragments**, which is why the remedy is a config line and not a rule about
    what may be quoted: a whole valid statement is normalised too - ``{'a': 1}`` becomes
    ``{"a": 1}`` - so any block quoting source written in another style is misquoted, less
    visibly and with nothing to notice it.

    ⚠ **The records are the real exposure.** ``docs/*research*.md`` are never rewritten, by a rule
    this repo states twice, and `trip-grouping-research.md` carries six such blocks. A formatter
    reaching inside a record is that rule broken by a tool nobody would think to check.

    **Excluding costs nothing measurable**: an unparseable fragment is silently skipped rather
    than reported, so ruff offers no diagnostic value over a document - it rewrites only blocks
    that *do* parse, which is exactly the set where the rewrite is wrong.
    """
    config = tomllib.loads((_REPO / "pyproject.toml").read_text(encoding="utf-8"))
    excluded = config["tool"]["ruff"]["format"].get("exclude", [])

    assert "*.md" in excluded, (
        "[tool.ruff.format] no longer excludes *.md, so the formatter owns every fenced python "
        "block in every document - including the records, which are never rewritten"
    )


def test_the_exclusion_is_load_bearing_rather_than_decorative() -> None:
    """The cry-wolf half: prove ruff really would rewrite a quotation without the setting.

    Asserting the config key alone would keep passing if ruff stopped formatting Markdown, and
    the line would then be cargo. This runs the formatter over a throwaway document with the
    setting absent and requires it to bite - so the day the behaviour goes away, this fails and
    the setting can be retired on evidence rather than left forever.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")
        doc = root / "quoted.md"
        original = "x\n\n```python\nfree_bytes=need if free is None else free,\n```\n"
        doc.write_text(original, encoding="utf-8")

        # The pin goes on this invocation too, and the guard above is what noticed it was
        # missing - it reads every `ruff format` argv in the repo, including this file's.
        subprocess.run(
            ["ruff", "format", "--target-version", "py313", "."],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        assert doc.read_text(encoding="utf-8") != original, (
            "ruff no longer formats python inside Markdown; the [tool.ruff.format] exclude of "
            "*.md is no longer load-bearing and should be retired on this evidence"
        )
