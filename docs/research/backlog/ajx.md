# (ajx) THE ~8 MINUTE BROWSER-LANE CONDITION IS RETIRED - IT ASKED THE WRONG QUESTION.

*Body of entry `(ajx)`, in [`BACKLOG.md`](../../BACKLOG.md) under **Rulings**; the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ajx)** Filed 2026-09-03 (P206) as a block; **ruled the same day (P207): the condition is
  retired, not pursued.** `IMPLEMENTATION_STANDARDS.md` carries the binding form of what replaces
  it. This body carries the measurement that killed it and the field evidence that says the
  replacement is standard practice rather than a concession.

  ## THE HARDWARE, PRINTED BY THE LANE ITSELF

  Added by `ce17611`, so no future measurement of this lane is on unidentifiable hardware
  (which is `(ajy)`):

  ```
  nproc      = 4
  MemTotal   = 15.6 GiB
  model name = AMD EPYC 9V74 80-Core Processor
  ```

  ## THE SERIAL BASELINE - TWO SAMPLES, AND THE VARIANCE IS THE FINDING

  Per-engine, by attributing every result line's elapsed to the engine in its parametrised id.
  Both reconstruct the reported total to within 0.2 s.

  ```
  --- run 33791378006 (18:35) ---  setup=58s     --- run 33796360000 (19:25) ---  setup=74s
      chromium    415.1s  ( 6.9 min)                 chromium    550.7s  ( 9.2 min)
      webkit      791.9s  (13.2 min)                 webkit      993.4s  (16.6 min)
      TOTAL      1207.4s                             TOTAL      1544.8s
  ```

  **A 28% run-to-run swing on identical work.** A split by engine costs `max(webkit) + setup` =
  **850-1067 s** against the 480 s condition and **misses by 77-122%**.

  ## THE LEVER, MEASURED - `-n auto` ON THE WEBKIT HALF, TWICE

  `-k webkit` selects exactly the 477 webkit cases, verified by collection before spending a run:
  *"477/988 tests collected (511 deselected)"*, and no test name contains `webkit` to over-select.
  Run sequentially, because `ci.yml`'s `concurrency` is keyed on `event_name` with
  `cancel-in-progress: true` and two dispatches would have cancelled each other.

  | | run | wall | speedup vs 791.9 / 993.4 | setup | job |
  |---|---|---|---|---|---|
  | sample 1 | `33802113061` | **554.97 s** | 1.43x / 1.79x | 54 s | 10.2 min, **RED** |
  | sample 2 | `33803207647` | **695.19 s** | 1.14x / 1.43x | 141 s | 13.9 min, **RED** |

  It needed **>=1.88x** on the fast baseline and **>=2.35x** on the slow one. **The best
  configuration ever measured is 10.2 minutes and it was red.**

  ## THE TAILS, AND WHY ONE SAMPLE WOULD HAVE LIED

  ```
  sample 1:  19.17s call  test_custody_strip.py::test_the_counted_wording_states_the_floor_too[webkit]
  sample 2: 330.08s call  test_migrate_undo.py::test_cancel_during_undo_apply_stops_and_leaves_the_journal_resumable[webkit]
  ```

  🔑 **The same test, 14.85 s in sample 1 and 330.08 s in sample 2 - a 22x swing.** Sample 1's
  tail was under the budget and everything but `(ajm)` passed; **it would have read as a pass.**
  Sample 2 exhausted the budget twice, and the failures are the crossing itself, not collateral:

  ```
  E   AssertionError: Locator expected to contain text 'to copy'
  E     - Expect "to_contain_text" with timeout 30000ms
  E   AssertionError: Locator expected to contain text 'already organized'
  E     - Expect "to_contain_text" with timeout 60000ms
  E       123 × locator resolved to <span class="why" id="org-why">…
  ```

  The general form of this is recorded in [`PERFORMANCE.md`](../../PERFORMANCE.md) beside the
  lane's own measurement, because it applies to **any** timing of this lane, not only to this
  entry. ⚠ **The assertion budget was NOT touched**: `tests/e2e/conftest.py` refused to be tuned
  forever, and that is a maintainer decision. `(ajy)` is why the budget's own 28.4 s provenance is
  separately unverified.

  ## AND `(ajm)` FIRED IN BOTH, WHICH MAKES IT A GATE

  `test_narrow_top_bar.py::test_the_catalog_path_fits_rather_than_truncating_to_nothing[webkit]`
  failed on `'/tmp/pytest-of-runner/pytest-0/popen-gw2/test_the_catalog_path_fit…catalog.sqlite'`.
  xdist inserts a `popen-gwN` component and lengthens `tmp_path` - a **second trigger** for
  `(ajm)`'s root cause. Any future parallelism has to fix it first.

  ## THE RULING - TWO STAGES, WHICH IS WHERE THE FIELD PUTS THEM

  1. **FAST, every push.** `make check` - **40 s over 3,543 tests**, inside best-in-class - plus
     the **contract guards that catch browser classes without a browser**. The worked example is
     `test_the_json_client_is_only_used_on_json_routes.py`: it catches the
     JSON-client-on-a-bodiless-route class in **0.07 s**, the class that cost a nightly red and
     shipped a broken cancel to users in 0.1.0. **Growing this stage is the standing work.**
  2. **SLOW, a narrower trigger.** The full browser suite, **both engines, unchanged** - nightly,
     on `workflow_dispatch`, and before a tag.

  **The ten-minute rule is real and near-universal.** Kent Beck: *"a build that takes longer than
  ten minutes will be used much less often, missing the opportunity for feedback."* DORA sets the
  same upper limit. ⚠ **But DORA's own remedy is not "make the slow tests fast"**: *"improve the
  efficiency of your tests, add more compute resources so you can run them in parallel, or **split
  out longer-running tests into a separate build** using the deployment pipeline pattern."* A 2026
  cost analysis puts it from the other side - *"some PRs run a 90-second smoke test; some run the
  full 30-minute integration."* 🔑 **We already have the fast loop.** Forcing a 20-minute
  two-engine browser suite into it is the thing the pattern says not to do.

  ## WHAT THE RETIREMENT DOES NOT MEAN

  - **It does not mean the lane matters less.** It moved to the stage it belongs in. `(ajv)` is
    the standing proof of what a dark browser lane costs: green for nineteen days over a bundle
    the published v0.1.0 never had.
  - **It does not license a curated subset.** `IMPLEMENTATION_STANDARDS.md` refuses one in terms -
    *"A subset is a second artifact that drifts from the real one and gives its false confidence
    exactly when it matters"* - and **that refusal stands unchanged**.
  - **The `(adi)` cutover's gate is explicit**: the unchanged browser suite runs **green against
    React, both engines, on a dispatch, before the flip commit**. That is the differential oracle
    `react-migration-plan.md` already describes, and it is **achievable today with no lever, no
    spend and no subsetting** - which the ~8 minute condition never was.
