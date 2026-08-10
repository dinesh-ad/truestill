"""A screen switch must wait before acting on anything the screen's own loads can move.

**The rule, and why it is not "no bare screen switches".** Switching screens and acting
immediately is *usually fine*. It is unsafe in one specific case: when the thing acted on sits
**at or below** a region that screen's loads write, because writing that region pushes everything
under it down - the control moves out from under the click. That is `(abq)`'s mechanism and it
cost four CI failures.

A blanket ban would be easier to write and would teach the wrong rule. Of the 68 bare switches
present when this guard was written, **23 are correct**: 12 go to `import` or `find`, which fetch
nothing on open, and 11 act only on controls *above* everything their screen writes. Permanently
allowlisting two dozen correct sites trains everyone to read the allowlist as noise, and an
allowlist read as noise stops being a ratchet.

Shell loads are deliberately out of scope: the `ui` fixture waits for them since Stage 1, so
`prefill` writing `#ev-source` is no longer a hazard anyone has to think about here.

**Two limits, stated because the next person will otherwise find them the hard way:**

1. **The window is fail-open.** Only the few statements following a switch are examined. An
   unsafe action further down is invisible to this guard. That is a deliberate trade: widening
   the window past the next control-flow boundary produces false positives, and a guard that
   cries wolf gets suppressed, which is worse than one with a known blind spot.
2. **A wait anywhere in the window counts, even after the unsafe action.** Two sites in
   `test_cancel_renders_cancelled.py` fill and click and only then assert; the assertion falls
   inside the window, so the guard passes them although the fill still races. Catching those
   needs the guard to order actions rather than scan text. Recorded rather than fixed - it is
   why this guard under-reports.
3. **Selector resolution is partial.** Only `#id` selectors are matched against the markup.
   Sites acting through a class, a `data-testid`, or a computed selector are not classified -
   19 of the original 68 fell here - and are treated as **not violating**. Fail-open again, and
   the same reasoning.

Neither limit lets a violation *in* silently: what they do is let some slip past unexamined. The
guard's job is to stop the count rising, not to prove the suite race-free.
"""

from __future__ import annotations

import re
from pathlib import Path

E2E = Path(__file__).resolve().parents[3] / "tests" / "e2e"
SRC = Path(__file__).resolve().parents[1] / "src" / "truestill_app"
INDEX_HTML = (SRC / "templates" / "index.html").read_text(encoding="utf-8")
APP_JS = (SRC / "static" / "app.js").read_text(encoding="utf-8")

#: How many statements after a switch are examined. See limit 1.
_WINDOW = 4

#: The FIRST element each screen's own loads write, in DOM order. One id per screen is enough:
#: the rule is "at or below this", so only the topmost write matters.
#:
#: Curated rather than derived, and the reason is worth stating: getting these out of the load
#: bodies means following `$("x").innerHTML = …` through a helper and, for `refreshUndoAffordance`,
#: through a panel passed in as an argument. That is JS dataflow, and a guard that gets it subtly
#: wrong is worse than one that is honestly a list. Both ends are pinned by tests below - the key
#: set against `SCREEN_LOADS`, the values against the markup - so it cannot drift silently.
_TOPMOST_LOAD_WRITE = {
    "organize": "org-undo-panel",
    "events": "ev-undo-panel",
    "backups": "drives-list",
    "stats": "stats-result",
    "settings": "layout-current",
}

#: Waits that actually retry. `wait_for_timeout` is absent on purpose: a sleep is satisfied by a
#: slow page as readily as a fast one, so accepting it would let the guard be answered by the one
#: idiom §3 forbids.
_REAL_WAITS = (
    "expect(",
    "wait_for_selector",
    "wait_for_load_state",
    "wait_for_function",
    "open_screen(",
)

#: Switches that must stay bare. `test_screen_readiness.py` observes screens WHILE they load - it
#: asserts `data-ready="loading"` and holds requests open. Requiring `open_screen` there would
#: make every one of those tests wait for the state they exist to catch, destroying the tests that
#: prove the signal is honest.
_EXEMPT_FILES = {"test_screen_readiness.py"}

#: Frozen at 8 on 2026-08-10 and emptied by Stage 2. **This may only shrink**, and it is now at
#: the floor: every site the rule can see either waits or is legitimately bare.
#:
#: An empty allowlist is NOT a claim that the suite is race-free - the three fail-open limits in
#: the module docstring mean this guard under-reports by construction. It means nothing it CAN
#: see is unguarded, and that anything new must be too.
_ALLOWED: set[tuple[str, str]] = set()


def _screen_dom_order() -> dict[str, list[str]]:
    """Element ids per screen, in document order, read from the markup the app actually serves."""
    order: dict[str, list[str]] = {}
    current: str | None = None
    for line in INDEX_HTML.splitlines():
        opened = re.search(r'<section class="screen(?: active)?" id="screen-(\w+)"', line)
        if opened:
            current = opened.group(1)
            order[current] = []
        elif current and "</section>" in line:
            current = None
        if current:
            order[current].extend(re.findall(r'id="([\w-]+)"', line))
    return order


def _enclosing_test(lines: list[str], index: int) -> str:
    for back in range(index, -1, -1):
        found = re.match(r"def (\w+)", lines[back])
        if found:
            return found.group(1)
    return "<module>"


def _scan(name: str, text: str) -> set[tuple[str, str]]:
    """The rule itself, over one file's source. Split out from `violations` so it can be proven
    on input written to violate - once the allowlist reaches zero there are no real findings
    left to demonstrate the matcher still works, and a matcher nobody can demonstrate is the
    thing this whole file exists to avoid."""
    order = _screen_dom_order()
    found: set[tuple[str, str]] = set()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        switch = re.search(r"""click\(\s*['"][^'"]*data-screen=.?["']?(\w+)""", line)
        if not switch:
            continue
        screen = switch.group(1)
        topmost = _TOPMOST_LOAD_WRITE.get(screen)
        if topmost is None or topmost not in order.get(screen, []):
            continue  # the screen loads nothing of its own - nothing can move
        limit = order[screen].index(topmost)
        window = "\n".join(lines[i + 1 : i + 1 + _WINDOW])
        if any(wait in window for wait in _REAL_WAITS):
            continue
        touched = re.findall(r"#([\w-]+)", window)
        if any(t in order[screen] and order[screen].index(t) >= limit for t in touched):
            found.add((name, _enclosing_test(lines, i)))
    return found


def violations() -> set[tuple[str, str]]:
    """Every switch that acts on something its screen's loads can move, with no retrying wait."""
    found: set[tuple[str, str]] = set()
    for path in sorted(E2E.glob("test_*.py")):
        if path.name in _EXEMPT_FILES:
            continue
        found |= _scan(path.name, path.read_text(encoding="utf-8"))
    return found


def test_no_new_bare_switch_acts_on_what_a_load_can_move() -> None:
    """The ratchet's forward direction: nothing new may be added."""
    new = violations() - _ALLOWED
    assert not new, (
        f"these switch screens and act on something the screen's loads can move, with no "
        f"retrying wait: {sorted(new)}. Use `open_screen(ui, name)` from e2e_support."
    )


def test_the_allowlist_only_shrinks() -> None:
    """The ratchet's other direction, and the half that keeps it honest.

    Without this an entry stays after its site is fixed, and the allowlist slowly becomes a list
    of places a bare switch is permitted rather than a list of places one is still owed.
    """
    stale = _ALLOWED - violations()
    assert not stale, f"these no longer violate and must be deleted from _ALLOWED: {sorted(stale)}"


def test_the_guard_can_see_a_violation_at_all() -> None:
    """Four cases, on source written for the purpose. The allowlist is empty, so real findings
    can no longer serve as the demonstration - and "it found nothing" has to be distinguishable
    from "it looks at nothing".

    **Aimed at SETTINGS, and it used to be aimed at Backups.** `(acd)` moved `#drives-list` below
    every Backups control, so `#bk-source` stopped being below a written region and this fixture
    stopped describing anything unsafe - it went green for the wrong reason the moment the defect
    was fixed. That is §4's twenty-eighth member happening to the guard that member was written
    beside: a check proven by the problem it hunts dies when the problem dies. Settings is used
    because `#mig-path` really does sit below `#layout-preview`, which `loadLayout` writes.
    """
    head = "def test_x(ui):\n    ui.click('button[data-screen=\"settings\"]')\n"

    # Unsafe: #mig-path sits below #layout-current, which loadLayout writes on screen open.
    assert _scan("f.py", head + '    ui.fill("#mig-path", "/x")\n') == {("f.py", "test_x")}

    # Safe: an auto-retrying wait first.
    assert (
        _scan("f.py", head + '    expect(x).to_be_visible()\n    ui.fill("#mig-path", "/x")\n')
        == set()
    )

    # Safe: acts only on the section itself, above everything the load writes.
    assert _scan("f.py", head + '    ui.locator("#screen-settings").click()\n') == set()

    # Unsafe still: a sleep is not a wait, and this is the case a blunter guard gets wrong.
    assert _scan(
        "f.py", head + '    ui.wait_for_timeout(200)\n    ui.fill("#mig-path", "/x")\n'
    ) == {("f.py", "test_x")}


def test_every_screen_that_loads_has_a_topmost_write_recorded() -> None:
    """Pins the curated map's KEYS to `SCREEN_LOADS`, so a screen that gains a load cannot be
    silently unguarded, and one that loses its last load cannot leave a stale entry behind."""
    block = re.search(r"const SCREEN_LOADS = \{(.*?)\n\};", APP_JS, re.DOTALL)
    assert block, "SCREEN_LOADS is not where this guard expects it"
    pairs = re.findall(r"(\w+):\s*\[([^\]]*)\]", block.group(1), re.DOTALL)
    loading = {name for name, body in pairs if body.strip()}
    assert loading == set(_TOPMOST_LOAD_WRITE), (
        f"screens with loads {loading} but recorded {set(_TOPMOST_LOAD_WRITE)}"
    )


def test_every_recorded_write_exists_where_it_is_claimed() -> None:
    """Pins the map's VALUES to the markup. A renamed or moved element makes the position rule
    meaningless, and would otherwise turn this guard off without a word."""
    order = _screen_dom_order()
    for screen, element in _TOPMOST_LOAD_WRITE.items():
        assert element in order.get(screen, []), f"#{element} is not inside #screen-{screen}"
