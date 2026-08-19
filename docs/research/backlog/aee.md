# (aee) CI'S TIMEOUTS AND ITS MIRROR RETRIES WERE BOTH DEFAULTS NOBODY CHOSE.

*Body of backlog entry `(aee)`, under **Shipped**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aee) CI'S TIMEOUTS AND ITS MIRROR RETRIES WERE BOTH DEFAULTS NOBODY CHOSE.** Recorded and
  fixed 2026-08-19 in `6e70ea0`, from run **32279378834**, where the ubuntu `check` lane sat
  **33+ minutes** inside `apt-get update` while the other two lanes finished in **1m07s** and
  **3m02s**. Two findings, filed together because they are the same failure of attention - a
  default is a decision that was never made - and because the second is only expensive when the
  first is absent.

  ## (1) `ci.yml` HAD NO `timeout-minutes`, SO THE DEFAULT WAS SIX HOURS

  **An observability property of the config, not an incident.** ⚠ The interesting part is not that
  a job hung; it is that **hung and slow were indistinguishable from outside**, which is exactly
  how a wedged lane came to read as merely slow for half an hour. Nothing was mis-set. Nothing was
  chosen at all, and the unchosen value was six hours.

  `release.yml` carried `timeout-minutes` at two steps (`release.yml:176,216`); `ci.yml` never had
  one at any level, so GitHub's 360-minute default applied to every job.

  **This is `(ads)`'s shape,** and that is the reason to file it here rather than as a one-line CI
  fix: *"THE CATALOG'S CONCURRENCY MODEL IS SQLITE'S DEFAULT, NOT A DECISION."* The same question -
  *which of these values did anyone pick?* - has now found two answers in two subsystems, and it is
  worth asking of any config this project inherits rather than writes.

  **Now:** `timeout-minutes: 20` on `check`, roughly 6x its slowest legitimate run (Windows, ~3
  min), and `45` on `e2e`, which runs ~24 min and already enforces a 2000 s ceiling **inside** the
  step. Those two bounds answer different questions and both are wanted: the inner ceiling reports
  a suite that got slow, the outer one catches a hang **before pytest ever starts**, which the
  inner one cannot see.

  ## (2) THE APT MIRROR FALLBACK - MECHANISM VERIFIED, FIX UNPROVEN

  GitHub's Ubuntu images resolve packages through a mirrorlist that puts
  `azure.archive.ubuntu.com` first and falls back to `archive.ubuntu.com`.

  **Verified, and it inverts the standard advice:**
  - apt **>= 2.3.2 already defaults to `Acquire::Retries=3`**, at a default 120 s timeout.
  - The failing run's log shows **exactly four `Ign:` rounds** per index - one attempt and three
    retries. The default, doing its job, at our expense.
  - The fallback **works**: the same log then reads `Hit: https://archive.ubuntu.com`. Nothing was
    broken except the cost of reaching it.
  - Checked rather than assumed: `apt-config dump` carries no explicit `Acquire::Retries` or
    `Acquire::http::Timeout` entry, so the compiled default is what applies.

  ⚠ **So `-o Acquire::Retries=3` - the advice in every CI write-up on this failure - was already in
  force and was the problem.** Adding it would have changed nothing. The fix is the opposite:
  `Retries=1` and a 15 s timeout, so failover to the working mirror costs ~15 s instead of 4x120 s
  per index. `update` and `install` were also split from a single `&&` chain, because chained, a
  flaky index refresh fails the step even when the package would have installed from the lists
  already on the image.

  **Nothing is made less reliable by asking less:** the retry that helps a genuinely flaky
  connection still happens once, and **a mirror that is DOWN is not made reachable by asking it
  four times.**

  🔒 **THE FIX IS UNPROVEN AND IS RECORDED AS UNPROVEN.** The very next run (**32283137544**) took
  **1m31s** on that lane - and that proves nothing. The mirror may simply have recovered, in which
  case the old configuration would have been just as fast. **Demonstrating this fix requires an
  outage, and an outage cannot be staged.** What is measured is the mechanism; what is inferred is
  the saving. The next time that mirror goes dark is the test, and whoever sees it should record
  the lane's duration here.

  ## THE THIRD MECHANISM-FIX-WITHOUT-REPRODUCTION IN ONE DAY, AND WHY THAT IS ALLOWED

  2026-08-19 produced three fixes of the same epistemic kind, and the pattern is worth naming
  before it becomes a habit nobody examines:

  | fix | mechanism | reproduced? |
  |---|---|---|
  | the text-size e2e wait (`(ado)` census) | a 200 ms fixed wait racing a catalog write `(adt)` measured at **6,558 ms** | no - 8 runs green before, 6 green under load after |
  | the macOS probe test `(abg)`/`(adx)` | `Thread.join(timeout)` waits **at least** the timeout, so a 100 ms margin decided the test | no - 60/60 green locally under 6 CPU burners |
  | the apt retries, here | `Retries=3` x 120 s against a mirrorlist whose fallback works | no - needs an outage |

  **What makes it acceptable is that the mechanism is measured even when the failure is not
  reproducible on demand.** Each row above rests on a number taken from the real system - 6,558 ms,
  a demonstrated late join, four `Ign:` rounds - not on a plausible story. The alternative is
  waiting for an outage in order to fix an outage, which is not a standard, it is a way of never
  fixing anything that fails rarely.

  ⚠ **The cost is that "fixed" means something weaker here than usual, and each of the three says
  so in place.** A fix whose evidence is a mechanism must be written down as such, so the next
  failure is read as *"the mechanism was wrong"* rather than as *"it came back"*. That distinction
  is the whole value of recording it.

  ## (3) THE TWO BOUNDS ARE NOT THE SAME MEASUREMENT, AND NEITHER ALONE SEES A SLOW LANE

  Added 2026-08-19, from the run that landed this entry. **This is worth more than the number that
  prompted it.**

  - `E2E_SECONDS_MAX` (2000 s) is enforced **inside** the step and times **pytest's own runtime**.
  - `timeout-minutes` (45) is enforced by GitHub and times the **job's wall clock**.

  Everything between them - queueing, checkout, `uv sync`, the browser install, the frontend
  build - is **invisible to the instrument anyone would reach for first**, because that instrument
  starts its stopwatch after all of it.

  **Measured, run 32287632288:**

  | | |
  |---|---|
  | pytest's own runtime | **1244.11 s** (20m44s), reported by pytest itself |
  | the e2e job's wall clock | **36m40s** |
  | outside pytest | **15m56s - 43% of the job** |

  ⚠ **AND THE OBVIOUS READING OF THAT IS WRONG, WHICH IS THE POINT.** It is tempting to say the run
  breached the 2000 s ceiling and passed anyway. It did not: pytest genuinely ran in 20m44s, well
  under, and the ceiling was right to stay silent. **The lane was slow in the only way that costs
  anyone anything - wall clock - while the instrument built to notice a slow lane correctly
  reported it as fine.** A guard that is working exactly as designed can still leave the thing you
  care about unmeasured.

  ### The spread, recorded as a spread rather than a conclusion

  | run / source | measurement | value |
  |---|---|---|
  | local `make gate` | pytest runtime | 1478.02 s (24m38s) |
  | local `make gate` | pytest runtime | 1476.83 s (24m36s) |
  | 32283137544 | e2e job wall clock | 22m32s |
  | 32287632288 | e2e job wall clock | **36m40s** |
  | 32287632288 | pytest runtime | 1244.11 s (20m44s) |

  ⚠ **Mixing those rows is itself the finding.** The local figures are pytest time; the CI figures
  are job time. They are not comparable, and reading them as one series is exactly the mistake
  section (3) exists to prevent. **Only 32287632288 has both numbers**, because the older jobs'
  logs no longer return through `gh run view --log`.

  **Nothing is concluded from this yet.** The 36m40s came on a **docs-only commit - three markdown
  files** - so the suite cannot have got slower, which leaves runner variance or queueing, and one
  sample distinguishes neither. **Add each subsequent run's duration to the table above until there
  is enough to say something.**

  ### What this says about the 45

  `timeout-minutes: 45` was justified against a ~24 minute job as comfortable headroom. **This run
  left 8m20s of margin rather than the ~21 minutes that reasoning assumed** - on the second run
  after it was written.

  🔒 **The bound is NOT being raised, and that is a ruling rather than an oversight.** One sample is
  not a trend, and raising a bound to accommodate a slow day is the reflex `(aec)` exists to
  resist - the same move as widening a fixed wait until the flake stops. If the table above grows
  enough to show the spread is real, the change to argue for is more likely a second instrument
  than a larger number.

  ## LEFT UNDONE, DELIBERATELY

  - **No retry wrapper around the apt step.** It would paper over exactly the signal this entry
    exists to preserve, and the bound above already fails fast.
  - **No exiftool caching.** It would remove the mirror from the path entirely and is the more
    complete fix, but it is a different change with its own cache-invalidation question, and
    nothing has measured the install as a recurring cost outside an outage.
  - **No step-level `timeout-minutes`.** The job-level bound is sufficient to end the six-hour
    class; per-step bounds are a finer instrument than any current evidence asks for.
