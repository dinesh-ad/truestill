# (ajy) THE 28.4 s WORST CASE THE ASSERTION BUDGET RESTS ON WAS MEASURED ON HARDWARE NOBODY CAN IDENTIFY.

*Body of entry `(ajy)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ajy)** Filed 2026-09-03 (P206). `tests/e2e/conftest.py` sets `expect.set_options(timeout=30_000)`
  and argues the number from a measurement whose machine it names wrongly and cannot now be
  recovered. **The 1.6 s of headroom is the whole risk argument against `-n auto` (`(ajx)`), and it
  is unverified.**

  ## THE CLAIM, PASTED

  ```
  tests/e2e/conftest.py:39
  #: ⚠ **THIS ACCOMMODATES `(ado)`'s TAIL. IT DOES NOT FIX IT.** The cause is understood and is not
  #: a defect in this application: WebKit on a shared 2-core runner is simply slow in bursts, and a
  #: job that reports 0.2 files/sec recovers to 1.6 and finishes. Measured over three full lanes at a
  #: 60 s ceiling: **1,482 tests, zero failures to complete**, longest wait **28.4 s**. Nothing hung.
  ```

  Written 2026-08-15. The runner is **not 2-core** - `ce17611` made the lane print it:

  ```
  nproc      = 4
  MemTotal   = 15.6 GiB
  model name = AMD EPYC 9V74 80-Core Processor
  ```

  ## WHY IT CANNOT BE RE-DERIVED, ONLY RE-MEASURED

  Three checks, each run 2026-09-03:

  1. **Nothing printed the core count then.** The `Runner spec` step is `ce17611`, today. No
     earlier run carries the hardware in its log.
  2. **The logs are gone.** The oldest retained CI run is `2026-08-23T16:57:01Z`
     (`gh run list --workflow=CI --limit 200`), **eight days after** the measurement.
  3. **The visibility change is not in the API.** `gh api repos/{owner}/{repo}/events` exposes only
     `{'CreateEvent', 'DeleteEvent', 'PushEvent', 'ReleaseEvent'}` - no visibility event - so
     whether the repository was public (4-core standard runner) or private (2-core) on 2026-08-15
     cannot be established. `created_at` is `2026-07-25T07:17:09Z`; `visibility` is `public` today.

  🔑 **So the label is wrong and the number's provenance is unknown.** Either it was taken on 4
  cores and the label was always wrong, or it was taken on 2 and does not describe today's lane.
  Both readings leave the same hole: **nothing in the repository can say which.**

  ## WHAT ELSE RESTED ON THE SAME PREMISE

  | where | claim | status |
  |---|---|---|
  | `tests/e2e/conftest.py` | the 2-core label and the 30 s budget built on 28.4 s | **live, unverified** |
  | `docs/SHIPPED.md` `(ado)` | *"WebKit on a shared 2-core runner is slow in bursts"* | a **record** - correctly not rewritten |
  | `docs/SHIPPED.md` | *"up to **5091.2 ms** on contended 2-core CI I/O against 9.0 ms max across 32,119 ordinary commits"* | a **record**, headline figure on unidentifiable hardware |
  | `Makefile` | *"expect roughly half that gain on a **2-4 core** CI runner"* | **live, and already right** - its range covers 4 |

  `pyproject.toml`'s *"-n auto on 16 cores"*, `PERFORMANCE.md` and `ENGINEERING_STANDARD.md` are
  the maintainer's own machine, labelled as such, and never depended on the CI count.

  ## WHAT RE-MEASURING COSTS

  The original was *"three full lanes at a 60 s ceiling"*. At today's measured cost that is
  **3 x 21-27 min = 63-81 minutes of runner time**, plus the same again if the maintainer wants
  the pre-`-n auto` and post-`-n auto` tails compared. It needs the 60 s probe ceiling restored
  for the duration, which is a temporary edit to `conftest.py` and therefore a maintainer
  decision - the budget *"refused to be tuned forever"* and this entry does not propose tuning it.

  ⚠ **THE CHEAP HALF IS ALREADY DONE AND COSTS NOTHING FURTHER.** Every run from `ce17611` onward
  carries its own hardware, so this class cannot recur: a future measurement is dated by a log
  that states the machine it ran on. What is unrecoverable is only the past.
