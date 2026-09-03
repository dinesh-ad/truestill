#!/usr/bin/env python3
"""Resolve `file:Symbol` citations, and convert `file:line` citations into them. `(ago)`

**Why symbols.** A line citation decays under every edit that adds a line above it, not only under
a refactor. Measured 2026-09-01: a **fifteen-line comment** added to ``app.js`` displaced **46
citations across 16 documents, 18 of them live**, and
``test_live_documents_cite_code_that_exists.py`` saw none of them - every displaced citation landed
on real code, which its own docstring names as the case it cannot cover. Two citations in `(abz)`
had been wrong for weeks and surfaced only because the shift happened to push one onto a blank
line, so of ~48 wrong pointers the guard reported **one, by accident**.

**Why not a content hash** (docpin's mechanism), refused on a measurement rather than a
preference: over the twelve days to 2026-09-01, **83 of 220** cited symbols had their body change,
so a hash would have demanded 83 documentation re-records in twelve days, none of which
corresponds to a citation that got worse. Over the same window ``packages/*/src`` took
**+15,284 / -2,785** lines of churn against **88** ``def``/``class`` removals - line-shifting
events outnumber symbol-identity events by roughly **170 to 1**. A guard that fires 83 times for
nothing is `ENGINEERING_STANDARD.md` §4's cry-wolf and gets switched off.

**What this cannot do, stated rather than implied** (§4): a symbol whose body is rewritten
completely is still a valid citation. That is the hash's case and it is **not covered**. Neither is
a symbol that no longer says what the prose claims.

This module is imported by both the guard and the converter so there is one index, not two that
can disagree. ``scripts/`` is not a package; importers add it to ``sys.path`` by path, the
``test_subcommand_list_mirrors_the_parser`` pattern.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Extensions a citation may name. Unchanged from the line-format guard, so the *scope* of what is
#: cited does not move in the same commit as the *format*.
EXTENSIONS = "py|js|css|html|yaml|yml|toml|sh"

#: The old format, read by the converter only. Nothing should write one after `(ago)`.
LINE_CITE = re.compile(rf"([A-Za-z0-9_./-]+\.(?:{EXTENSIONS})):(\d+)(?:-(\d+))?")

#: The format. A dotted symbol path - ``drive.py:library_independence``,
#: ``catalog.py:Catalog.holder_sets``. The first character cannot be a digit, so this can never
#: match a line citation and the two are told apart by shape rather than by order of trying.
SYMBOL_CITE = re.compile(
    rf"([A-Za-z0-9_./-]+\.(?:{EXTENSIONS})):([A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)"
)

#: Third-party files legitimately cited by name and correctly absent from this tree.
FOREIGN = ("TiffImagePlugin.py", "Image.py", "PIL/")

#: Top-level JavaScript declarations. `app.js` is the file that caused `(ago)`'s incident and
#: Python's `ast` cannot read it, so it gets a regex rather than a parser dependency: measured over
#: today's `app.js`, this finds **203 top-level symbols with zero duplicates**, and **all 23 live
#: citations into that file land inside one**. A parser would buy nothing those numbers do not
#: already give.
_JS_TOP = re.compile(
    r"^(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(|^(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*="
)


@dataclass(frozen=True, slots=True)
class Span:
    """A named region of a file, `start` and `end` inclusive and 1-based."""

    start: int
    end: int
    name: str


def _doc_comment_start(lines: list[str], first: int) -> int:
    """Walk `first` upward over a contiguous ``#:`` block and any decorators.

    ``#:`` is Sphinx's "this documents the symbol below" convention and this codebase uses it that
    way, so a citation into such a block is a citation *about that symbol*. Nine of the fifteen
    Python citations with no enclosing symbol are exactly this - `jobs.py:93` sits 11 lines above
    ``FINISHED_CLEAN``, `drives.py:49-62` one line above ``LIBRARY_PATH_HINT``.
    """
    i = first
    while i > 1:
        above = lines[i - 2].strip()
        if above.startswith(("#:", "@")):
            i -= 1
        else:
            break
    return i


_INDEX: dict[tuple[str, int], list[Span]] = {}


def symbols_for(path: str) -> list[Span]:
    """`symbols()` for a tracked path, memoised on the file's content length.

    The corpus scan asks for the same handful of files hundreds of times; parsing `catalog.py`
    once per citation cost 23 s in a suite with a 45 s ceiling.
    """
    text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
    key = (path, len(text))
    if key not in _INDEX:
        _INDEX[key] = symbols(path, text)
    return _INDEX[key]


def symbols(path: str, text: str) -> list[Span]:
    """Every citable symbol in `text`, innermost-resolvable and dotted.

    Returns `[]` for a file this cannot parse, which is not an error: `.toml`, `.yml` and `.html`
    have no symbols here and their citations name the file alone.
    """
    lines = text.splitlines()
    found: list[Span] = []

    if path.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []

        def walk(node: ast.AST, prefix: str) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                    name = prefix + child.name
                    start = min(
                        [child.lineno, *(d.lineno for d in child.decorator_list)],
                    )
                    found.append(
                        Span(
                            _doc_comment_start(lines, start), child.end_lineno or child.lineno, name
                        )
                    )
                    walk(child, name + ".")
                elif isinstance(child, ast.Assign | ast.AnnAssign) and child.col_offset == 0:
                    target = child.targets[0] if isinstance(child, ast.Assign) else child.target
                    if isinstance(target, ast.Name):
                        found.append(
                            Span(
                                _doc_comment_start(lines, child.lineno),
                                child.end_lineno or child.lineno,
                                prefix + target.id,
                            )
                        )

        walk(tree, "")
        return found

    if path.endswith(".js"):
        tops = [
            (i + 1, m.group(1) or m.group(2))
            for i, line in enumerate(lines)
            if (m := _JS_TOP.match(line))
        ]
        # A top-level declaration runs until the next one. Coarser than a parse and enough: the
        # question a citation asks is "which symbol is this about", not "where does the block end".
        return [
            Span(start, (tops[i + 1][0] - 1) if i + 1 < len(tops) else len(lines), name)
            for i, (start, name) in enumerate(tops)
        ]

    return []


def enclosing(spans: list[Span], line: int) -> Span | None:
    """The innermost span containing `line`, or `None`."""
    inside = [s for s in spans if s.start <= line <= s.end]
    return min(inside, key=lambda s: s.end - s.start) if inside else None


def tracked_files() -> set[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return set(out.stdout.split())


#: Every path suffix of every tracked file, built once. A per-citation scan of the whole tree was
#: 10 s over the corpus in a suite with a 45 s ceiling.
_SUFFIXES: dict[tuple[str, ...], list[str]] = {}


def candidates(raw: str, tracked: set[str]) -> list[str]:
    """Tracked files a citation's path could mean, matched on whole path COMPONENTS.

    ⚠ **A basename match is wrong here and it was measured wrong.** Six basenames are carried by
    both core and an app service, and a citation written ``service/bake.py:166`` has *already*
    said which one it means. Matching on ``Path(raw).name`` throws that away and reports an
    ambiguity the author resolved - 17 of the converter's first 38 refusals were this, not a real
    one.
    """
    # `removeprefix`, never `lstrip("./")`: lstrip takes a CHARACTER SET, so it ate the leading
    # dot of every dot-path and turned `.github/workflows/ci.yml` into `github/workflows/ci.yml`,
    # which matches no tracked file and no path SUFFIX either. The guard then reported a correct
    # citation as "no tracked file of that name" - a false refusal over 8 tracked paths including
    # both workflows and `.pre-commit-config.yaml`. Found 2026-09-03 (P206) by the first document
    # that ever cited one.
    exact = raw.removeprefix("./")
    if exact in tracked:
        return [exact]
    if not _SUFFIXES:
        for path in tracked:
            parts = tuple(Path(path).parts)
            for i in range(len(parts)):
                _SUFFIXES.setdefault(parts[i:], []).append(path)
    return sorted(_SUFFIXES.get(tuple(Path(exact).parts), []))


def resolve(raw: str, symbol: str, tracked: set[str]) -> tuple[str | None, str | None]:
    """Which tracked file does `raw:symbol` mean, and what is wrong if nothing.

    🔑 **The symbol disambiguates a shared basename, which the line format could not.** Six
    basenames are carried by both `truestill-core` and an app service - `migrate.py`, `trips.py`,
    `backup.py`, `takeout.py`, `bake.py`, `verify.py` - and the line guard skipped **46 citations**
    into them silently, 13% of the corpus. Measured over those six pairs: **0 of 237 symbol names
    appear on both sides**, so the symbol picks the file every time.
    """
    options = candidates(raw, tracked)
    if not options:
        return None, "no tracked file of that name"

    holders = [path for path in options if any(s.name == symbol for s in symbols_for(path))]
    if len(holders) == 1:
        return holders[0], None
    if not holders:
        where = options[0] if len(options) == 1 else f"{len(options)} files of that name"
        return None, f"no symbol {symbol} in {where}"
    return None, f"{symbol} is in {len(holders)} files of that name"


# --------------------------------------------------------------------------- the converter


def convert(text: str, tracked: set[str]) -> tuple[str, list[str]]:
    """Rewrite every `file:line` in `text` as `file:Symbol`, refusing what it cannot resolve.

    ⚠ **IT ASSERTS ITS OWN OUTPUT AND REFUSES RATHER THAN GUESSING**, the discipline `63723b2`
    used to move 18 citations with zero mismatches. A rewrite is emitted only when the symbol it
    names has a span that **contains the original line**; anything else is left exactly as it was
    and listed. A converter that guesses is the hand conversion this exists to prevent - `(ahz)`'s
    five citations moved onto other real code and stayed green.
    """
    refused: list[str] = []

    def one(match: re.Match[str]) -> str:
        raw, low = match.group(1), int(match.group(2))
        if any(marker in raw for marker in FOREIGN):
            return match.group(0)

        options = candidates(raw, tracked)
        if not options:
            refused.append(f"{match.group(0)} - no tracked file of that name")
            return match.group(0)

        hits = []
        for path in options:
            if (span := enclosing(symbols_for(path), low)) is not None:
                hits.append((path, span))

        if len(hits) != 1:
            why = "no enclosing symbol" if not hits else f"ambiguous across {len(hits)} files"
            refused.append(f"{match.group(0)} - {why}")
            return match.group(0)

        path, span = hits[0]
        if not span.start <= low <= span.end:  # pragma: no cover - enclosing() guarantees it
            refused.append(f"{match.group(0)} - span {span.name} does not contain line {low}")
            return match.group(0)
        return f"{raw}:{span.name}"

    return LINE_CITE.sub(one, text), refused


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", nargs="+", help="markdown files to convert")
    parser.add_argument("--write", action="store_true", help="apply (default: report only)")
    args = parser.parse_args()

    tracked = tracked_files()
    total = converted = 0
    all_refused: list[str] = []
    for name in args.documents:
        path = Path(name)
        before = path.read_text(encoding="utf-8")
        after, refused = convert(before, tracked)
        here = len(LINE_CITE.findall(before))
        total += here
        converted += here - len(refused)
        all_refused += [f"{path}: {r}" for r in refused]
        if args.write and after != before:
            path.write_text(after, encoding="utf-8")

    print(f"{total} line citations; {converted} converted; {len(all_refused)} refused")
    for line in all_refused:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
