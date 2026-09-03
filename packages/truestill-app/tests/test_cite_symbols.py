"""The symbol index, the resolver and the converter's refusal discipline. `(ago)`

⚠ **NOTHING HERE HARDCODES A LINE NUMBER, and in this file that is not a stylistic preference.**
Every fixture *locates* what it needs at runtime - the first method of a class, the constant under
a ``#:`` block - because a test for the cure to line-citation rot that itself rots on line numbers
would be the joke it is named after. This is the discipline
`test_the_detector_catches_a_blank_line_and_a_line_past_the_end` already uses for its blank line,
applied to the format that replaces it.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import cite_symbols as cite

ROOT = Path(__file__).resolve().parents[3]

#: The six basenames carried by BOTH `truestill-core` and an app service. This is the population
#: behind the line guard's silent 13% skip, so it is named rather than derived - a derivation that
#: quietly returned the empty list would make every assertion below vacuous.
SHARED_BASENAMES = ("migrate.py", "trips.py", "backup.py", "takeout.py", "bake.py", "verify.py")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_a_line_inside_a_function_body_resolves_to_that_function() -> None:
    """The 59% case: a citation points at code inside a body, not at the ``def``.

    Only 15.6% of the corpus's citations sit on a ``def``/``class`` line, so resolving *only* those
    would have covered a sixth of the problem.
    """
    path = "packages/truestill-core/src/truestill_core/drive.py"
    spans = cite.symbols(path, _read(path))

    target = next(s for s in spans if s.name == "library_independence")
    inside = target.start + (target.end - target.start) // 2

    found = cite.enclosing(spans, inside)
    assert found is not None
    assert found.name == "library_independence", f"a line inside the body resolved to {found.name}"


def test_a_method_is_named_with_its_class() -> None:
    """Dotted, so the name is unique. Measured: 505 Python files, zero duplicate dotted names."""
    path = "packages/truestill-core/src/truestill_core/catalog.py"
    spans = cite.symbols(path, _read(path))

    method = next(s for s in spans if s.name == "Catalog.holder_sets")
    body = cite.enclosing(spans, method.start + 1)

    assert body is not None
    assert body.name == "Catalog.holder_sets"


def test_every_dotted_name_in_a_file_is_unique() -> None:
    """The property the format rests on, asserted rather than assumed."""
    for path in (
        "packages/truestill-core/src/truestill_core/catalog.py",
        "packages/truestill-cli/src/truestill_cli/cli.py",
    ):
        names = [s.name for s in cite.symbols(path, _read(path))]
        assert len(names) == len(set(names)), f"{path} has a duplicate dotted name"


def test_a_doc_comment_block_belongs_to_the_symbol_below_it() -> None:
    """``#:`` documents the symbol under it, so a citation into the block is about that symbol.

    Nine of the fifteen Python citations with no enclosing symbol were exactly this shape.
    """
    path = "packages/truestill-app/src/truestill_app/jobs.py"
    text = _read(path)
    spans = cite.symbols(path, text)
    lines = text.splitlines()

    constant = next(s for s in spans if s.name == "FINISHED_CLEAN")
    assert lines[constant.start - 1].strip().startswith("#:"), (
        "fixture check: the span should have been widened up onto the #: block"
    )
    assert cite.enclosing(spans, constant.start) is not None


def test_a_decorated_function_starts_at_its_decorator() -> None:
    path = "packages/truestill-core/src/truestill_core/reclaim.py"
    text = _read(path)
    spans = cite.symbols(path, text)
    lines = text.splitlines()

    decorated = [s for s in spans if lines[s.start - 1].strip().startswith("@")]
    assert decorated, "fixture check: reclaim.py should carry a decorated symbol"
    for span in decorated:
        assert cite.enclosing(spans, span.start) is not None


def test_app_js_resolves_without_a_javascript_parser() -> None:
    """`app.js` caused `(ago)`'s incident and `ast` cannot read it, so the regex index is load-bearing."""
    path = "packages/truestill-app/src/truestill_app/static/app.js"
    spans = cite.symbols(path, _read(path))

    assert len(spans) > 150, f"the JS index collapsed to {len(spans)} symbols"
    names = [s.name for s in spans]
    assert len(names) == len(set(names)), (
        "a duplicate top-level name would make citations ambiguous"
    )

    known = next(s for s in spans if s.name == "backupCompletion")
    assert cite.enclosing(spans, known.start + 1) is not None


def test_a_file_with_no_symbols_yields_none_rather_than_raising() -> None:
    """`.toml`, `.yml` and `.html` have no symbols here. That is a shape, not an error."""
    assert cite.symbols("pyproject.toml", _read("pyproject.toml")) == []


# ------------------------------------------------------------------ the six shared basenames


@pytest.mark.parametrize("basename", SHARED_BASENAMES)
def test_the_symbol_picks_between_core_and_the_app_service(basename: str) -> None:
    """🔑 **The measurable win.** The line guard skipped these silently - a bare basename several
    files share was *"not this guard's question"* - which left **46 citations, 13% of the corpus**,
    unchecked, and they are exactly the pairs where confusing core with the app service matters.

    Measured over all six: **0 of 237 symbol names appear on both sides.**
    """
    core = f"packages/truestill-core/src/truestill_core/{basename}"
    app = f"packages/truestill-app/src/truestill_app/service/{basename}"
    tracked = cite.tracked_files()
    assert core in tracked, "fixture check: core file must exist"
    assert app in tracked, "fixture check: app service file must exist"

    core_names = {s.name for s in cite.symbols(core, _read(core))}
    app_names = {s.name for s in cite.symbols(app, _read(app))}
    assert core_names, f"{basename}: the core index is empty"
    assert app_names, f"{basename}: the app index is empty"
    assert not (core_names & app_names), f"{basename}: a shared name would defeat the resolver"

    target, why = cite.resolve(basename, sorted(core_names)[0], tracked)
    assert why is None, f"{basename}: {why}"
    assert target == core, f"{basename}: core symbol resolved to {target}"


def test_a_path_prefix_the_author_wrote_is_not_thrown_away() -> None:
    """``service/bake.py`` has already said which one it means.

    Matching on the basename alone reported an ambiguity the author had resolved - 17 of the
    converter's first 38 refusals were this, and none of them were real.
    """
    tracked = cite.tracked_files()
    options = cite.candidates("service/bake.py", tracked)

    assert options == ["packages/truestill-app/src/truestill_app/service/bake.py"], options


def test_a_dot_path_is_not_eaten_by_the_prefix_strip() -> None:
    """`lstrip("./")` takes a character set, so it ate the leading dot of every dot-path.

    `.github/workflows/ci.yml` became `github/workflows/ci.yml`, which is neither a tracked path
    nor a suffix of one, so a correct citation was refused as "no tracked file of that name".
    Eight tracked paths were unreachable this way, both workflows among them; the guard had never
    been pointed at one until 2026-09-03.
    """
    tracked = cite.tracked_files()

    assert cite.candidates(".github/workflows/ci.yml", tracked) == [".github/workflows/ci.yml"]
    # and the prefix it IS meant to strip still goes
    assert cite.candidates("./scripts/cite_symbols.py", tracked) == ["scripts/cite_symbols.py"]


def test_an_unknown_symbol_is_reported_rather_than_resolved() -> None:
    target, why = cite.resolve("drive.py", "no_such_symbol_anywhere", cite.tracked_files())

    assert target is None
    assert why is not None
    assert "no symbol" in why


# ------------------------------------------------------------------ the converter


def test_the_converter_rewrites_a_line_into_its_enclosing_symbol() -> None:
    path = "packages/truestill-core/src/truestill_core/drive.py"
    spans = cite.symbols(path, _read(path))
    target = next(s for s in spans if s.name == "library_independence")
    inside = target.start + (target.end - target.start) // 2

    out, refused = cite.convert(f"see `drive.py:{inside}` here", cite.tracked_files())

    assert refused == []
    assert out == "see `drive.py:library_independence` here"


def test_the_converter_refuses_rather_than_guessing() -> None:
    """⚠ **The `63723b2` discipline.** A converter that guesses is the hand conversion this exists
    to prevent - `(ahz)`'s five citations moved onto other real code and stayed green."""
    tracked = cite.tracked_files()

    out, refused = cite.convert("see `pyproject.toml:17`", tracked)
    assert out == "see `pyproject.toml:17`", "a refusal must leave the text untouched"
    assert len(refused) == 1
    assert "no enclosing symbol" in refused[0]

    out, refused = cite.convert("see `no_such_module_anywhere.py:12`", tracked)
    assert out == "see `no_such_module_anywhere.py:12`"
    assert len(refused) == 1
    assert "no tracked file" in refused[0]


def test_every_rewrite_the_converter_emits_contains_the_original_line() -> None:
    """The output assertion, run over the whole live corpus rather than a sample.

    This is the property that makes the migration mechanical: a rewrite is emitted only when the
    symbol it names has a span containing the line the citation used to point at.
    """
    tracked = cite.tracked_files()
    checked = 0

    for document in sorted(ROOT.glob("docs/**/*.md")):
        text = document.read_text(encoding="utf-8")
        for match in cite.LINE_CITE.finditer(text):
            raw, low = match.group(1), int(match.group(2))
            if any(marker in raw for marker in cite.FOREIGN):
                continue
            rewritten, refused = cite.convert(match.group(0), tracked)
            if refused:
                continue
            symbol = rewritten.split(":", 1)[1]
            target, why = cite.resolve(raw, symbol, tracked)
            assert target is not None, f"{match.group(0)} -> {rewritten}: {why}"
            span = next(s for s in cite.symbols_for(target) if s.name == symbol)
            assert span.start <= low <= span.end, (
                f"{match.group(0)} -> {rewritten} does not contain line {low}"
            )
            checked += 1

    assert checked > 200, f"only {checked} conversions were verified; the corpus scan collapsed"


def test_the_index_agrees_with_ast_about_what_exists() -> None:
    """Anti-vacuity for the index itself: a `symbols()` that returned `[]` would pass much of the
    file above without this."""
    path = "packages/truestill-core/src/truestill_core/drive.py"
    text = _read(path)
    from_ast = {
        node.name
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }
    from_index = {s.name.rsplit(".", 1)[-1] for s in cite.symbols(path, text)}

    assert from_ast, "fixture check: drive.py has functions"
    assert from_ast <= from_index, f"the index lost {sorted(from_ast - from_index)}"
