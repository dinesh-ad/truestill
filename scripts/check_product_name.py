#!/usr/bin/env python3
"""The product name is **Truestill** wherever a person reads it. This checks the surfaces.

The rule is not new and is not this script's opinion: `docs/brand.md` states it, and states its
own exceptions - the import package stays ``truestill_core``, the command stays ``truestill``,
the app entry point stays ``truestill-app``, because those are identifiers. Nothing enforced it,
so the front door drifted to 17 lowercase mentions and zero capitalised, and `brand.md` broke its
own rule twice.

**Precision is the whole design, because cry-wolf would be fatal here.** A guard that fires on
``truestill organize`` or on ``truestill_core`` gets switched off within a week and takes its real
coverage with it. Four layers, cheapest first:

1. **Fenced and inline code is skipped.** Anything a reader sees as code is an identifier by
   presentation, whatever it says.
2. **Attached punctuation disqualifies.** ``truestill-cli``, ``truestill_app``, ``truestill.app``
   and ``.../truestill/...`` are all identifiers, and a word-boundary match alone would flag every
   one of them. ``TRUESTILL_DATA_DIR`` never matches: the search is case-sensitive.
3. **A subcommand after the name makes it an invocation** (:data:`SUBCOMMANDS`) - ``truestill
   undo-organize`` is something a user types, not a sentence about the product. The list mirrors
   the parser rather than guessing at "a lowercase word follows", which would also swallow
   ``truestill does not organize yet``.
4. **Anything still ambiguous is a literal allow-list entry with its reason**
   (:data:`ALLOWED_LITERALS`), which is the house convention for exactly this - see
   `normalize_dashes.ALLOWED_LITERALS`.

**Scope is the shop window, not the whole tree** (:data:`CHECKED`). A tree-wide sweep would touch
111 files and 351 lines, nearly all of them contributor prose in docstrings, tests and dated
research records - the blanket change this repo forbids, and the fastest way to make the guard
worth disabling. `brand.md` is in scope despite being a contributor doc for the obvious reason:
the document that states the rule has to keep it.

Usage::

    python3 scripts/check_product_name.py            # report, change nothing (CI / make check)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Surfaces a person outside this repo reads. The first five mirror
#: `test_user_facing_copy.USER_FACING`, which names them for the same reason.
#: **Every path must resolve** - a moved file is a broken guard, not a skip (audit F12).
CHECKED: tuple[str, ...] = (
    "packages/truestill-app/src/truestill_app/static/app.js",
    "packages/truestill-app/src/truestill_app/templates/index.html",
    "packages/truestill-cli/src/truestill_cli/cli.py",
    "README.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "docs/brand.md",
    "packages/truestill-core/README.md",
    "packages/truestill-cli/README.md",
    "packages/truestill-app/README.md",
    "packages/truestill-core/pyproject.toml",
    "packages/truestill-cli/pyproject.toml",
    "packages/truestill-app/pyproject.toml",
)

#: Subcommands of the `truestill` CLI. A name followed by one of these is an invocation the user
#: types, never prose. Mirrors `cli._build_parser`; a new subcommand quoted in prose will fail
#: here until it is added, which points at the right list rather than at a clever regex.
#: **Hand-kept, and it had drifted twice by 2026-08-04** - `analyze` and `repoint-sources` both
#: shipped without being added, so an invocation of either read as prose and was flagged. The
#: docstring above says this "mirrors the parser"; today that is a convention, not a mechanism.
#: Deriving it from the dispatch table is filed as `(abc)` rather than done here, because the
#: import direction (a repo script reaching into a package) deserves its own decision.
SUBCOMMANDS: tuple[str, ...] = (
    "analyze",
    "organize",
    "repoint-sources",
    "ingest",
    "drives",
    "undo-organize",
    "where",
    "verify",
    "status",
    "catalog",
    "config",
    "reclaim",
    "migrate-layout",
    "clean-empty",
    "rescan",
)

#: Ambiguous lines kept lowercase on purpose, each with the reason it is not prose.
ALLOWED_LITERALS: tuple[tuple[str, str], ...] = (
    (
        'prog="truestill"',
        "argparse's program name: the command the user typed, printed back in usage lines.",
    ),
    (
        'version=f"truestill {__version__}"',
        "`truestill --version` names the command, the way `git --version` prints `git version`.",
    ),
    (
        '<p class="k mono" id="app-version">truestill {{VERSION}}</p>',
        "the same version string as the CLI's, and rendered in `mono` - presented as code.",
    ),
    (
        'truestill = "truestill_cli.cli:main"',
        "the console-script entry point: the name of the executable, on both sides.",
    ),
)

#: Lowercase ``truestill`` with no identifier punctuation touching either side. Case-sensitive,
#: so ``Truestill`` and ``TRUESTILL_DATA_DIR`` are invisible to it.
NAME = re.compile(r"(?<![\w./-])truestill(?![\w./-])")

#: A fenced code block boundary, and an inline code span.
FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"`[^`]*`")

#: The name followed by a subcommand: an invocation, not the product name in a sentence.
INVOCATION = re.compile(r"truestill (?:" + "|".join(re.escape(s) for s in SUBCOMMANDS) + r")\b")


def offences(path: Path) -> list[tuple[int, str]]:
    """Lines in ``path`` where the product name is written lowercase as prose."""
    found: list[tuple[int, str]] = []
    # A backtick is a code convention in markdown, in Python docstrings and in TOML comments -
    # and in JavaScript it is SYNTAX, opening a template literal. Every rendered string in
    # `app.js` lives inside one, so applying the code-span rule there made the guard blind to
    # the app's own UI copy: the text it most exists to check. Found 2026-08-02, two lines after
    # it shipped, by writing a lowercase name into a `title=` attribute and watching it pass.
    is_backtick_code = path.suffix in {".md", ".py", ".toml"}
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if is_backtick_code and FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if any(literal in line for literal, _reason in ALLOWED_LITERALS):
            continue
        # Order matters: strip what is presentationally code, then what is an invocation, and
        # only then look for the name. Searching first would match inside both.
        stripped = INVOCATION.sub("", CODE_SPAN.sub("", line) if is_backtick_code else line)
        if NAME.search(stripped):
            found.append((number, line.strip()))
    return found


def main() -> int:
    missing = [name for name in CHECKED if not (REPO / name).exists()]
    if missing:
        print("error: checked surfaces have moved; fix the list, do not let the guard skip them:")
        for name in missing:
            print(f"  {name}")
        return 2

    total = 0
    for name in CHECKED:
        for number, line in offences(REPO / name):
            print(f"{name}:{number}: {line}")
            total += 1
    if total:
        print(
            f"\n{total} lowercase 'truestill' in prose. The product name is 'Truestill' wherever "
            "a person reads it (docs/brand.md).\nIdentifiers stay lowercase: the command, "
            "`truestill-*` packages, `truestill_*` modules, URLs and paths.\nIf one of these is "
            "genuinely an identifier, add it to ALLOWED_LITERALS with its reason."
        )
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
