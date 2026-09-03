# (ajx) THE ~8 MINUTE BROWSER-LANE PREREQUISITE IS A BLOCK, NOT A TASK.

*Body of entry `(ajx)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ajx)** Filed 2026-09-03 (P206), measured rather than argued. `handoff-2026-09-03.md` and
  `react-migration-plan.md` both list *"the browser lane under ~8 minutes"* as a numbered
  prerequisite between `(ajv)` and the formatter work, which reads as a task somebody does. **No
  measured configuration reaches it, and the only untried lever has to deliver a factor nobody has
  demonstrated.** Until it is re-ruled it blocks per-push verification of the `(adi)` cutover.

  ## THE HARDWARE, PRINTED BY THE LANE ITSELF

  Added by `ce17611`; run `33796360000`:

  ```
  nproc      = 4
  MemTotal   = 15.6 GiB
  model name = AMD EPYC 9V74 80-Core Processor
  ```

  ## TWO SAMPLES, SAME SUITE, SAME HARDWARE, FIFTY MINUTES APART

  Derived from each job's log by attributing every result line's elapsed to the engine in its
  parametrised id (`ts(result) - ts(previous result)`, anchored at `test session starts`). Both
  reconstruct the reported total to within 0.2 s, so nothing is unaccounted for.

  ```
  --- run 33791378006 (18:35) ---  setup=58s     --- run 33796360000 (19:25) ---  setup=74s
      chromium    415.1s  ( 6.9 min)                 chromium    550.7s  ( 9.2 min)
      webkit      791.9s  (13.2 min)                 webkit      993.4s  (16.6 min)
      TOTAL      1207.4s                             TOTAL      1544.8s

  per-engine variance:  chromium +33%,  webkit +25%
  ```

  🔑 **The 28% run-to-run swing is the finding, not the totals.** A target set against the fast
  sample is missed routinely; anything proposed here must clear on the SLOW one.

  ## WHAT EACH CONFIGURATION COSTS AGAINST THE 480 s CONDITION

  | configuration | fast | slow | vs 480 s |
  |---|---|---|---|
  | today, serial (both engines, one job) | 1265 s | 1619 s | **2.6-3.4x over** |
  | split by engine (max = webkit + setup) | 850 s | 1067 s | **1.8-2.2x over** |
  | chromium job alone | 473 s | 625 s | clears on the fast sample only |

  **The split misses by 77% to 122%.** Chromium in isolation fails on the slow sample, and a
  chromium-only per-push lane is refused on its own merits by `ci.yml`'s Install-browsers comment -
  *"WebKit is what the Tauri shell renders in on Linux and macOS, and a lane that is green only in
  Chromium says nothing about it."*

  ## WHY IT IS NOT THE `if: false` SHAPE, AND WHY THAT DOES NOT RESCUE IT

  `IMPLEMENTATION_STANDARDS.md` records a prior condition - *"the first migrated screen"* - that
  **could never fire**, because `(adi)` migrates by island and no such event exists. This one *can*
  fire in principle: `-n auto` is untried and would need **>=1.88x on the fast sample and >=2.35x
  on the slow one**. So it is **unverified and receding**, not impossible - the condition was
  written for a ~470-test lane and the lane now produces **988 results**. A prerequisite whose only
  remaining route is an untested lever, against a suite that has doubled, is not functioning as a
  prerequisite.

  ## WHAT IS ALREADY RULED OUT, SO NOBODY RE-PROPOSES IT

  - **A path-filtered push trigger** - refused with proof in `IMPLEMENTATION_STANDARDS.md`:
    `(afo)` touched core, an app service and the CLI, **no markup path**, and changed wording two
    `tests/e2e/` files assert directly. A filter would have skipped it.
  - **A curated smoke subset** - refused in terms: *"A subset is a second artifact that drifts from
    the real one and gives its false confidence exactly when it matters."*
  - **Tuning the assertion budget** - `tests/e2e/conftest.py` refused to be tuned forever, and it
    is a maintainer decision. See `(ajy)`, which is why that budget is now unverified anyway.

  ## WHAT WOULD SETTLE IT

  `-n auto` on the **webkit half alone**, on a dispatch, twice, reading the **longest single wait**
  rather than the total. If the tail stays under ~25 s and webkit lands under ~420 s, split plus
  xdist clears the condition. If the tail crosses 30 s it cannot be met on this hardware, and the
  remaining answers are **runner spend** or the **contract-guard route** - moving classes out of
  the browser lane entirely, as `test_the_json_client_is_only_used_on_json_routes.py` does for the
  JSON-client class in 0.07 s with no browser. Both are the maintainer's.
