"""Structural guards on the readiness signal - the half that no browser test can prove.

`tests/e2e/test_screen_readiness.py` proves the flag behaves. Three things it cannot prove live
here, because a browser cannot see them:

1. **A load that resolves before its DOM write lands.** The flag is derived from the promises
   that perform the writes, which is only sound while "resolved" implies "written". Nothing in
   the language enforces that. A browser test cannot catch it either: a write deferred by
   `requestAnimationFrame` or `setTimeout(0)` arrives within a frame, well before a separate
   round trip could read the DOM, so the test goes green against a live defect. **This scan is
   the only defence**, and it is a text scan rather than a parser - stated here rather than
   discovered by whoever trusts it later.
2. **Uniformity, in both directions.** A signal present on some screens and absent on others is
   worse than none: a caller cannot tell "not ready yet" from "never says anything".
3. **One writer.** The mutation proof aims at a single assignment. A second one would make that
   proof mean less than it appears to.

Each guard is paired with a test that the guard can see its own target at all. Without those, a
matcher that silently matches nothing passes over every file in the repo and reports health.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "truestill_app"
APP_JS = (SRC / "static" / "app.js").read_text(encoding="utf-8")
INDEX_HTML = (SRC / "templates" / "index.html").read_text(encoding="utf-8")

#: Tokens that defer work past the promise a load resolves with. `.then(` is deliberately absent:
#: a returned/awaited `.then` chain is ordinary and correct, and telling the two apart needs a
#: parser. That gap is real and is named in the module docstring.
_DEFERRING = ("requestAnimationFrame", "setTimeout", "setInterval", "queueMicrotask")


def _registry_names() -> list[str]:
    """The function names `SCREEN_LOADS` actually starts, read from the source.

    Derived rather than listed, so a load added to a screen is covered the day it is added
    instead of the day somebody remembers to update this file.
    """
    block = re.search(r"const SCREEN_LOADS = \{(.*?)\n\};", APP_JS, re.DOTALL)
    assert block, "SCREEN_LOADS is not where this guard expects it"
    return sorted(set(re.findall(r"\(\)\s*=>\s*(\w+)\(", block.group(1))))


def _body_of(name: str) -> str:
    """The source of `async function name(...)`, by brace matching.

    Crude on purpose, and adequate only because these bodies are small, formatted by the repo's
    formatter, and change rarely. If that stops being true this should become a real parse.
    """
    start = APP_JS.index(f"async function {name}(")
    opening = APP_JS.index("{", start)
    depth = 0
    for index in range(opening, len(APP_JS)):
        if APP_JS[index] == "{":
            depth += 1
        elif APP_JS[index] == "}":
            depth -= 1
            if depth == 0:
                return APP_JS[opening : index + 1]
    message = f"unbalanced braces reading {name}"
    raise AssertionError(message)


def _deferrals_in(body: str) -> list[str]:
    return [token for token in _DEFERRING if token in body]


def test_a_registered_load_does_not_defer_its_dom_write() -> None:
    """The invariant the whole signal rests on: resolving must mean the writes have landed.

    A load that resolves and then writes on a later turn would make `data-ready` lead the DOM it
    claims to cover - the cry-wolf case, and the one with no browser test.
    """
    names = _registry_names()
    assert names, "no loads found in SCREEN_LOADS - this guard has gone blind"
    offenders = {name: found for name in names if (found := _deferrals_in(_body_of(name)))}
    assert not offenders, (
        f"these registered loads defer work past the promise readiness waits on: {offenders}. "
        "Readiness would be stamped before the write lands."
    )


def test_the_deferral_guard_can_see_a_deferral_at_all() -> None:
    """Without this, the guard above passes for a body it never actually examined."""
    assert _deferrals_in("{ const x = 1; el.innerHTML = x; }") == []
    assert _deferrals_in("{ requestAnimationFrame(() => { el.innerHTML = x; }); }") == [
        "requestAnimationFrame"
    ]
    assert _deferrals_in("{ setTimeout(() => { el.innerHTML = x; }, 0); }") == ["setTimeout"]


def test_the_body_reader_finds_a_whole_body() -> None:
    """Brace matching is the fragile part of this file, so it is proven rather than assumed."""
    body = _body_of("loadStats")
    assert body.startswith("{")
    assert body.endswith("}")
    assert "stats-result" in body, "the reader stopped before the end of the function"


def test_every_screen_ships_loading_and_every_shipped_screen_is_registered() -> None:
    """Both directions. One alone lets the sets drift: a new screen with no registry entry would
    never settle, and a registry entry for a deleted screen would never be noticed.
    """
    shipped = re.findall(
        r'<section class="screen(?: active)?" id="screen-([a-z]+)"([^>]*)>', INDEX_HTML
    )
    assert len(shipped) == 7, f"expected 7 screens in the markup, found {len(shipped)}"

    for name, attributes in shipped:
        assert 'data-ready="loading"' in attributes, f"#screen-{name} does not ship as loading"
        assert 'aria-busy="true"' in attributes, f"#screen-{name} does not ship busy"

    block = re.search(r"const SCREEN_LOADS = \{(.*?)\n\};", APP_JS, re.DOTALL)
    assert block, "SCREEN_LOADS is not where this guard expects it"
    registered = set(re.findall(r"\n  (\w+): \[", block.group(1)))
    in_markup = {name for name, _ in shipped}
    assert registered == in_markup, (
        f"SCREEN_LOADS and the markup disagree: "
        f"only in the registry {registered - in_markup}, only in the markup {in_markup - registered}"
    )


def test_ready_is_never_shipped_in_the_markup() -> None:
    """The primary cry-wolf defence, and the cheapest: if a screen shipped as `ready`, every
    wait on it would be satisfied by the starting state and would never test anything. What a
    test waits on has to BECOME true."""
    assert 'data-ready="ready"' not in INDEX_HTML
    assert 'data-ready="failed"' not in INDEX_HTML


def test_only_one_function_writes_the_flag() -> None:
    """Keeps the mutation proof meaningful: it aims at one line, and a second writer would let
    the flag be set somewhere the proof never looks."""
    writes = re.findall(r"\.dataset\.ready\s*=", APP_JS)
    assert len(writes) == 2, (
        f"expected exactly 2 assignments to dataset.ready (the reset and the terminal value), "
        f"found {len(writes)} - readiness must have exactly one writer"
    )
    settle = APP_JS.index("function settleScreen(")
    following = APP_JS.index("\nfunction ", settle + 1)
    assert APP_JS.count(".dataset.ready =", settle, following) == 2, (
        "an assignment to dataset.ready lives outside settleScreen"
    )
