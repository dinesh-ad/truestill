# (afx) THE BROWSER LANE HAS GROWN INTO ITS OWN CEILING: 1996.21 s AGAINST 2000.

*Body of backlog entry `(afx)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afx)** Measured 2026-08-22 by the full local lane run before `(afu)`'s commit:

  ```
  973 passed, 3 skipped in 1996.21s (0:33:16)
  E2E_SECONDS_MAX ?= 2000          # Makefile
  ```

  **3.79 seconds of headroom. 0.19%.** The next browser test added breaches it.

  ## 🔑 DO NOT RAISE THE CEILING

  **A bound raised to fit its subject measures nothing.** The number exists to fail when the lane
  grows past what anyone decided it should cost; moving it the first time it does that converts a
  control into a formality, and every later reading is against a line drawn to accommodate
  whatever had already happened.

  ⚠ **It is doing its job by reporting now rather than after.** The lane passed. Nothing is
  broken. That is the whole value of a bound with headroom left in it - `ENGINEERING_STANDARD.md`
  §2's *"a lane that grows into one fails loudly rather than being re-measured into prose"*, which
  is the sentence this entry exists to honour rather than quote.

  ## ⚠ THE DEFECT IS THE ASYMMETRY, NOT THE NUMBER

  **CI overrides the ceiling to 3600** (`ci.yml:542`,
  `make e2e E2E_EXTRA=... E2E_SECONDS_MAX=3600`). So when the lane crosses 2000 s:

  - **CI stays green.** It has 1600 s of slack and will not notice for a long time.
  - **`make e2e` fails locally**, at 2000 s.

  🔑 **The stricter lane is on the developer's machine, so the failure lands on whoever is doing
  the right thing.** A person who runs the browser lane before committing - which is what
  `IMPLEMENTATION_STANDARDS.md` §6.1 asks for when a change reaches a screen - gets a red they did
  not cause, about a limit CI does not enforce. The person who skips it sees nothing. **That
  rewards not running it**, which is the one behaviour the lane cannot survive, and it is the same
  cry-wolf shape `(afn)` records: a check that fires on ordinary work gets switched off and takes
  its real coverage with it.

  **So the two numbers disagreeing is the finding.** Whatever is decided about the duration, a
  local bound stricter than the enforced one is backwards.

  ## ⚠ IT IS `(aec)`'s BILL

  `(aec)` counted **62 `wait_for_timeout` calls across 20 files** on 2026-08-19. **Re-counted
  2026-08-22: still exactly 62 across 20** - the census has not moved, and neither has the time
  they cost. That entry is about each wait being *"a coin toss against a measured latency"*; this
  is what the same 62 add up to.

  ⚠ **And nobody was watching the total, for a structural reason.** The lane went nightly on
  2026-08-22 (`if: false` before that, from 2026-08-20), so its duration stopped crossing anyone's
  desk on a push. A number that only appears in a 03:17 run is a number nobody reads. The two
  entries are cross-referenced in both directions: `(aec)` names the waits, this names their sum.

  ## ⚠ WHAT THE INSTRUMENT CANNOT SEE, STATED WHERE IT IS BOUNDED

  `E2E_SECONDS_MAX` wraps **the `pytest` invocation only**. The `Makefile` target is
  `e2e: frontend`, so `make frontend` - `tsc --noEmit && vite build` - runs **before** the ceiling
  starts counting, and the browser install is a different target (`make e2e-install`) that is not
  in `make e2e` at all. On CI more sits outside still: queueing, checkout and
  `playwright install --with-deps`.

  **This is `ENGINEERING_STANDARD.md` §4's fifty-fourth member, already recorded against this
  exact constant** - `(aee)` measured pytest at **1244.11 s** inside a job that took **36m40s**,
  so **43% of the lane was outside what the instrument could see**. Repeated here because the
  member's own remedy is to *say what the instrument does not measure, next to the instrument*,
  and the place a reader meets this number is the `Makefile` and this entry.

  ⚠ **It cuts toward urgency rather than away from it.** The 1996.21 s is pytest's own clock, so
  the *lane* already costs more than the ceiling's subject does, and a build that is currently
  incremental is one `npm ci` away from adding minutes the bound will never see.

  ## NOT PROPOSED, AND DELIBERATELY

  **`pytest-xdist` is the obvious lever** - it is already a dependency, `make test` already runs
  `-n auto`, and `make e2e` is serial across two browsers. `ci.yml` names it as the condition for
  per-push returning (*"when the lane finishes in under ~8 minutes"*).

  ⚠ **It is not worth measuring here.** This lane protects a UI that `(adi)` is replacing island
  by island, and parallelising a suite whose subject is being rewritten spends the measurement
  twice. Recorded so the next person does not re-derive the lever and mistake its absence for an
  oversight - `ENGINEERING_STANDARD.md` §4's fifty-eighth member: an unwritten reason is invisible
  to every review.

  **What this entry asks for is a ruling on the pair of numbers**, not a speed-up.

  ## RELATED

  `(aec)` (the 62 waits, and the other direction of this cross-reference), `(aee)` (which measured
  what the ceiling cannot see), `(adi)` (the migration that makes optimising this lane a poor
  trade), `(afn)` (cry-wolf: a check that fires on ordinary work gets switched off).
