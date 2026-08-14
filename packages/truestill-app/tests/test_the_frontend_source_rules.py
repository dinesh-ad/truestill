"""Three rules over `frontend/src`, each with an allow-list whose stale entries also fail.

Grouped in one file because they share a subject - every source file under `frontend/src` - and
one scan. Split them when one of them grows a reason of its own.

**The allow-list shape, and the half that matters.** An entry that no longer describes a real
violation **also fails**. Without that, an allow-list nobody prunes becomes a list of places the
rule does not apply, which is how a guard turns into a suggestion without anyone deciding to.
Same shape as `test_app_core_import_boundary.py` and
`test_catalog_opens_go_through_the_session.py`.

**Text scanning, not a TypeScript parse.** There is no TS parser in the Python gate and adding
one would be a dependency to justify for three rules. The cost is honest and bounded: a comment
saying the word `any` can trip rule 1. That is a false positive with an obvious fix - the
allow-list - and it fails loudly rather than passing quietly, which is the direction to be wrong
in. All three are O(total source bytes), single pass.
"""

from __future__ import annotations

import re
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parents[3] / "packages/truestill-app/frontend"
_SRC = _FRONTEND / "src"


def _sources() -> list[Path]:
    return sorted(p for p in _SRC.rglob("*") if p.suffix in {".ts", ".tsx"} and p.is_file())


def _relative(path: Path) -> str:
    return path.relative_to(_FRONTEND).as_posix()


def _check(pattern: re.Pattern[str], allowed: dict[str, str], rule: str, remedy: str) -> None:
    """Fail on any unallowed match, AND on any allow-list entry that has stopped matching."""
    offenders: dict[str, list[int]] = {}
    for source in _sources():
        lines = [
            number
            for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1)
            if pattern.search(line)
        ]
        if lines:
            offenders[_relative(source)] = lines

    unallowed = {name: lines for name, lines in offenders.items() if name not in allowed}
    assert not unallowed, f"{rule}\n{unallowed}\n{remedy}"

    stale = sorted(set(allowed) - set(offenders))
    assert not stale, (
        f"allow-list entries that no longer violate the rule: {stale}. Remove them. An "
        "allow-list nobody prunes becomes a list of places the rule does not apply."
    )


# --- rule 1: no `any` -----------------------------------------------------------------------
#: `path -> why`. Every entry is checked to still be true.
_ANY_ALLOWED: dict[str, str] = {}
_ANY = re.compile(r"(?<![\w$])any(?![\w$])")


def test_no_any_in_frontend_source() -> None:
    """`unknown` at trust boundaries, narrowed before use - never `any`.

    The boundary that will matter here is the sidecar's JSON: it arrives over a socket from
    another process, possibly a different version after an upgrade, and an interface declaration
    is an assertion about it rather than a check of it. `any` turns that assertion into silence.
    """
    _check(
        _ANY,
        _ANY_ALLOWED,
        "`any` found in frontend source:",
        "Use `unknown` and narrow it. If a cast is genuinely unavoidable, add the file to "
        "`_ANY_ALLOWED` with the reason, in the commit that introduces it.",
    )


# --- rule 2: no hand-memoization ------------------------------------------------------------
#: `path -> why`. Empty, and it should stay that way until something is measured.
_MEMO_ALLOWED: dict[str, str] = {}
_MEMO = re.compile(r"(?<![\w$])(useMemo|useCallback|React\.memo|\bmemo)\s*\(")


def test_no_hand_memoization() -> None:
    """Memoize only what has been measured, and record the measurement beside it.

    ⚠ **Not because the React Compiler will do it.** The compiler is a separate opt-in Babel
    plugin and it is NOT installed here - `package.json` has five devDependencies and none of
    them is `babel-plugin-react-compiler`. Installing React 19 does not bring it. So the reason
    this rule holds is the ordinary one the canon already gives: optimise the proven bottleneck,
    and a memo without a measurement is a guess with a dependency array attached. If the compiler
    is adopted later, this rule keeps its force and gains a second reason.
    """
    _check(
        _MEMO,
        _MEMO_ALLOWED,
        "hand-memoization found in frontend source:",
        "Measure first. If the measurement justifies it, add the file to `_MEMO_ALLOWED` with "
        "the number, not the intuition.",
    )


# --- rule 3: tokens.css is not pulled into the bundle ---------------------------------------
#: `path -> why`. Nothing should ever be here; the file cannot be in two places.
_TOKENS_ALLOWED: dict[str, str] = {}
_TOKENS = re.compile(r"""["'][^"']*tokens\.css["']""")


def test_tokens_css_is_not_imported_into_the_bundle() -> None:
    """`tokens.css` lives in the Python package and is served by Starlette. It does not move.

    Its home is `truestill_app/static/tokens.css`, where the static route serves it and **20 e2e
    files assert computed styles against it**. Importing it from `frontend/src` would have Vite
    emit a second copy into the bundle, and the two would drift the first time one was edited -
    silently, because nothing in the Python gate reads CSS (`ENGINEERING_STANDARD.md` §4).

    This guard exists because a proposed frontend layout put `tokens.css` under
    `frontend/src/styles/`, which reads like tidying and is a two-copy bug.
    """
    _check(
        _TOKENS,
        _TOKENS_ALLOWED,
        "`tokens.css` referenced from frontend source:",
        "It is served from truestill_app/static/ and must have exactly one copy. Link it from "
        "the template, do not import it into the bundle.",
    )


def test_the_scan_actually_reads_files() -> None:
    """Cry-wolf guard. Every rule above passes vacuously if the glob finds nothing - a renamed
    directory, a moved frontend - and three green tests would report a standard nobody is held
    to. Assert the corpus is non-empty before trusting three assertions about it."""
    sources = _sources()
    assert sources, (
        f"no .ts/.tsx files found under {_SRC}. The frontend has moved and this file has to move "
        "with it, in the same commit."
    )
    assert any(source.read_text(encoding="utf-8").strip() for source in sources), (
        "every frontend source file is empty, so the scans above prove nothing"
    )
