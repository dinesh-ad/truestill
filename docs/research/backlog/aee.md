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

  ✅ **AND IT FIRED, on 2026-08-19, two runs after it was added.** Run 32295312064's `e2e` job was
  killed at **45m18s** with `Install browsers` stuck 43m33s in a mirror it could not reach. The
  bound turned a lane that would have run to GitHub's 360-minute default into a **bounded, labelled
  failure in 45 minutes**, with the three `check` lanes passing underneath it. That is the whole of
  what it was for.

  ⚠ **AND GITHUB REPORTS A TIMEOUT-KILLED JOB AS `cancelled`, NOT `failure`.** Verified on this
  run: `conclusion: cancelled` on both the job and the run. **Three different causes now sit behind
  that one value** - a human pressing cancel, a `concurrency` supersede (this workflow sets
  `cancel-in-progress: true`, so it happens routinely), and a timeout. **The timeout is the one
  nobody will expect**, and it is the only one of the three that means something is wrong. It is a
  standing GitHub complaint rather than a local quirk - `community` discussion **#38004** is titled
  *"timing out github action without 'failure' status"*.

  Nothing in this repo branches on that field today - `scripts/flake_report.py` requests
  `conclusion` but works from the uploaded test-result XML - so this is a hazard recorded before it
  bites rather than a defect. ⚠ **But the artifact route has the same blind spot and it is live:**
  the timed-out run uploaded **no `test-results-e2e` artifact at all**, so `flake_report` over the
  last six runs reports exactly one failure - the macOS probe - and **shows nothing whatever for a
  lane that died after 45 minutes**. A timeout produces zero recorded failures, so the flake report
  reads clean. Whoever adds a check on run health should count a `cancelled` lane as a thing to
  look at, not a thing to skip.

  ## (2) THE APT FALLBACK - THE ALTITUDE WAS WRONG, AND ONE OF MY OWN CLAIMS WITH IT

  **Rewritten 2026-08-19 after run 32295312064**, a second mirror outage the same day, which
  settled two things and pointedly failed to settle the one this section was originally about.

  ### PROVEN: the bound was at the wrong altitude

  It went in as **flags on one command** - `sudo apt-get -o Acquire::Retries=1 ... update` on
  `Install exiftool (Linux)`. That bounded the call site being looked at. The outage found the
  others:

  | apt consumer, run 32295312064 | bounded then? | duration |
  |---|---|---|
  | `check` -> `Install exiftool (Linux)` | yes | 58 s |
  | `e2e` -> `Install exiftool` - same command, other job | **no, missed entirely** | 88 s |
  | `e2e` -> `Install browsers`, i.e. `playwright install --with-deps` | **no, and unreachable** | **43m33s, killed** |

  ⚠ **The third one is why per-command flags were structurally wrong, not merely incomplete.**
  `playwright install --with-deps` runs its own `apt-get` inside a third-party installer. There is
  no flag of ours to pass it. The setting has to live in `/etc/apt/apt.conf.d/`, where **every**
  consumer inherits it - ours, Playwright's, and whatever is added next.

  **The generalising line, which is worth more than the fix: bounding a call site fixes the calls
  you can see.** A policy that must be re-applied per invocation is a policy that will be missed,
  and the miss is silent because the bounded call looks fine. `test_ci_bounds_apt_in_one_place`
  now fails if any apt command carries its own flags, and fails if a job reaches apt without the
  drop-in or reaches it first.

  ### PROVEN: the bound fired, and this is what it was added for

  `Install browsers` ran **19:53:01 -> 20:36:34 (43m33s)** and the job was killed at **45m18s**
  against `timeout-minutes: 45`. **One bounded failure instead of a six-hour hang, on the second
  run after the bound was added**, during the second outage of the same day. The three `check`
  lanes passed underneath it, so the failure was also *localised* rather than total.

  🔒 **And it is NOT evidence for raising the bound.** A bound that fires during an outage is a
  bound that is correctly sized. `(aec)`.

  ### ⚠ UNPROVEN, STILL - AND A CLAIM OF MINE, CORRECTED IN PLACE

  **I reported a controlled comparison, and it was not one.** I wrote that 58 s bounded against
  33 minutes unbounded was "the same outage, the same minute". It was not: **the 33-minute figure
  came from run 32279378834, a different run and a different outage.** The honest same-run control
  is **58 s bounded against 88 s unbounded** - and both were fine.

  **So the numbers cannot carry the claim, and the reason is package count.** `exiftool` is one
  small package; `--with-deps` pulls a large dependency set, so a degraded mirror costs it
  enormously more per index and per file. That difference, not the bound, is the obvious
  explanation for 88 s against 43m33s. **A plausible mechanism is not a measurement.**

  ⚠ **THIS OUTAGE DID NOT SETTLE IT, AND THAT NEEDS SAYING OUT LOUD** - a reader who finds an
  outage recorded here will reasonably assume it did. It did not. The bounded and unbounded copies
  of the *same* command both completed comfortably; the only catastrophic step was one that was
  unbounded **and** far larger, so the two variables moved together.

  **The standing instruction therefore stands unchanged: the next time that mirror goes dark,
  record the lane's duration here.** What would settle it is the bounded and unbounded forms of a
  *comparable* apt call in one outage - realistically, `Install browsers` before and after this
  drop-in.


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

  ### And a third instrument, whose premise the same outage falsified

  `scripts/ci_timing_summary.py` exists to tell a slow **runner** from a slow **suite**, and its
  discriminator is the ratio of pytest to a fixed-cost step. Its own words (`ci_timing_summary.py`
  lines 5-6): *"Installing exiftool downloads and unpacks the same archive every run, so its
  duration is a property of the machine and nothing else."*

  ⚠ **It is a property of the mirror.** That step measured **33+ min, 58 s and 88 s** across three
  runs on 2026-08-19. During an outage the ratio is meaningless - and an outage is exactly when
  someone reaches for an instrument that answers *"is it the runner or the suite?"*. The drop-in
  also changes that baseline, so ratios from before and after this commit are not comparable.

  **All three findings are one shape, and this is the line to keep:** *an instrument whose premise
  holds in the normal case and quietly fails in the abnormal one is unavailable in the only case it
  exists for.* `E2E_SECONDS_MAX` cannot see the job, `timeout-minutes` cannot see pytest, and the
  timing ratio cannot see a mirror. None of the three is wrong; each is silent about the thing that
  went wrong.

  ### The spread, recorded as a spread rather than a conclusion

  | run / source | measurement | value |
  |---|---|---|
  | local `make gate` | pytest runtime | 1478.02 s (24m38s) |
  | local `make gate` | pytest runtime | 1476.83 s (24m36s) |
  | 32283137544 | e2e job wall clock | 22m32s |
  | 32287632288 | e2e job wall clock | **36m40s** |
  | 32287632288 | pytest runtime | 1244.11 s (20m44s) |
  | 32295312064 | e2e job wall clock | **45m18s - KILLED by the bound** (mirror outage; pytest never ran) |

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
