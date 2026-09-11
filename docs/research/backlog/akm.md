# (akm) TWO BREAKPOINTS' DERIVATIONS WENT STALE, AND EVERY TEST STAYED GREEN.

*Body of entry `(akm)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

- **(akm)** Filed 2026-09-11, found sweeping the tree after widening `--sidebar-width` 232 -> 272.

  ## WHAT IS KNOWN

  Two media-query thresholds were each derived from the rail's width, both are **literals in the
  stylesheet**, and neither is recomputed from anything. So when a term moved, the number stayed
  and every guard stayed green.

  **1. The 1336px panel threshold.** Derived as `rail 232 + a comfortable 760 column + a 320
  panel`. **Two of its three terms have since moved**: the panel's floor went `320 -> 248` on
  2026-09-06 (`--panel-width: clamp(248px, 15vw, 320px)`) and the rail `232 -> 272` on 2026-09-11.
  Measured at a 1336px window: the content column is **1000px**, where the derivation assumed
  1040. `tests/e2e/test_large_viewports.py:test_the_panel_threshold_did_not_move` passed across
  both changes, correctly - it asserts the panel is hidden at 1335 and nothing else.

  **2. The 1023px `.org-modes` breakpoint.** Its comment claimed *"the rail takes 232px and
  `.main` 48px of padding, so a 1024px window leaves ~744 and three cards are ~230 each - the last
  width at which a title and a one-line description still read."* ⚠ **Measured, all three figures
  were wrong BEFORE the rail moved**: `.main`'s padding is **32px** a side, the row was **674px**,
  and each card **216.7px**. At the 272px rail the same window gives **634px** and **203.3px** a
  card; ~230 is first reached at ~1107px. The floor the comment names has never been met at the
  breakpoint the comment is attached to.

  ## WHY IT IS FILED AND NOT FIXED

  Moving either number is a **behaviour change on a screen**, decided by looking at a rendering
  and judging where a title stops reading - not by re-running the arithmetic that was wrong in the
  first place. The rail commit was scoped to the rail. Both comments now carry the measured
  numbers and say the threshold is held rather than derived, so nothing states a false fact while
  this waits.

  ## THE CLASS, WHICH IS THE POINT

  A derived constant that is stored as a literal **cannot go red when its derivation changes**.
  Four documents and three test docstrings said the rail was 232px on the day it became 272, and
  `make check` and the full browser lane were both green. The remedy is not a guard per number -
  `(ago)`'s bar refuses one written green on the day it lands - it is that **a derivation is
  written down beside the literal, with its terms named**, so a sweep can find it. Both sites now
  are.

  ## WHAT WOULD SETTLE IT

  - Render Organize at 1024px and at 1107px and look: is a 203px card actually unreadable, or was
    ~230 a guess that has been quietly wrong for months?
  - Decide whether 1336 should follow its terms (`272 + 760 + 248` is ~1300 plus gaps) or stay.
