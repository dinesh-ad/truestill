# (aec) 62 FIXED WAITS IN THE BROWSER LANE, EACH ONE A COIN TOSS AGAINST A MEASURED LATENCY.

*Body of backlog entry `(aec)`, under **Internal / tooling**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aec) 62 FIXED WAITS IN THE BROWSER LANE, EACH ONE A COIN TOSS AGAINST A MEASURED LATENCY.**
  Recorded 2026-08-19, out of the CI failure that closed `(ado)`'s third repeat. **One was fixed;
  the class was not**, and filing it is the honest half of that.
  - ⚠ ✅ **WHAT THE 62 ADD UP TO IS `(afx)`, MEASURED 2026-08-22.** The full local lane ran
    **1996.21 s against a 2000 s ceiling** - **3.79 s of headroom** - so this entry stopped being
    only about flake risk and became the reason the lane is at its bound. **The census has not
    moved**: re-counted the same day, still exactly **62 across 20 files**. ⚠ **And nobody was
    watching the total for a structural reason** - the lane went nightly on 2026-08-22, so its
    duration stopped crossing anyone's desk on a push. `(afx)` carries the ceiling, the
    CI-versus-local asymmetry, and the ruling it needs; this entry stays the census.
  - **The census**, counted rather than estimated: **62 `wait_for_timeout` calls across 20 files**
    in `tests/e2e/`. Most-loaded files: `test_sidebar_stays_put.py`, `test_screen_pass_2026_08.py`
    and `test_large_viewports.py` at 6 each, `test_palette_and_resting_panel.py` at 5, then four
    files at 4 - including `test_text_size_setting.py`, **which still has 4 after today's fix
    removed 2**.
  - **The values, which are the finding.** `200 ms` x14, `120` x9, `250` x8, `150` x8, `400` x7,
    `300` x5, `600` x4, `500` x2. **Nothing derived these**; they are the numbers that made a test
    pass on the machine it was written on.
  - 🔑 **WHAT TODAY ESTABLISHED, and it is why this is a defect class rather than untidiness.**
    `test_the_choice_survives_a_reload` waited **200 ms** for a click that POSTs a setting, which
    `run_in_threadpool`s a **catalog write** - the operation `(adt)` measured at **6,558 ms** on a
    CI runner. **A fixed wait in front of an operation measured at 6.5 s is not a wait, it is a
    coin toss**, and that test came up tails three times across five days (`31821214510`,
    `32178286777`, `32250647783`).
  - ⚠ **AND THE 30 s BUDGET DOES NOT COVER THEM.** `(ado)`'s ruling raised the budget for
    **auto-retrying** assertions. A `wait_for_timeout` followed by a bare `assert` gets nothing
    from it - which is exactly why the one census member that never fitted the stall shapes was
    also the one the budget could not reach. **Every remaining fixed wait sits outside that
    protection.**
  - **The shape of the fix, established rather than guessed:** wait for the thing itself. Today's
    two were `expect_response` around the click that writes, and `wait_for_function` polling the
    value instead of sleeping. Playwright's own guidance is unambiguous - *"Never wait for
    timeout... Tests that wait for time are inherently flaky. Use Locator actions and web
    assertions that wait automatically."*
  - **A second, measured reason to do it:** removing 2 sleeps took `test_text_size_setting.py`
    from **37.32 s to 8.14 s**. If that ratio holds anywhere near across 62 calls, **the sleeps
    are a real component of a 24-minute lane** - which is `(ado)`'s cost argument from the other
    end.
  - ⚠ **NOT A TAIL-END TASK, and that is why it is filed rather than done.** A sweep of 62 call
    sites in a suite whose only verification is a **24-minute** run is its own piece of work: each
    site needs the question *"what is this actually waiting for"* answered individually, and
    today's fix broke two tests on the first attempt because clicking an already-selected radio
    fires no event and so has no response to wait for. **That failure mode is per-site.** Doing
    62 of them at the end of an unrelated change is how a green lane becomes a red one.
  - **Where to start, if anyone asks:** the sites in front of a **write**, since those are the
    ones racing a latency the repo has measured. The rest are in front of rendering, where the
    stake is smaller and `expect(...).to_have_css(...)` usually replaces them directly.
  - **Not proposed here:** whether a guard should forbid new `wait_for_timeout` calls once the
    count reaches zero. It would be cheap and it would be premature - a ratchet on a number
    nobody is yet reducing is a rule with no work behind it.
  - **Related.** `(ado)` - the census this came out of, and the budget that does not cover these.
    `(adt)` - the 6,558 ms write that made one of them a coin toss.
