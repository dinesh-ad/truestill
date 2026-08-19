# (ado) THE E2E LANE HAS A ROTATING WEBKIT TAIL - CAUSE FOUND: THE BUDGET, NOT A MECHANISM

*The investigation record for `(ado)`, **CLOSED 2026-08-15**. The closing entry, the ruling and
its cost are in [`SHIPPED.md`](../SHIPPED.md). Kept whole rather than summarised: the arc's value
is in what was measured and what was wrong, and both are below.*

- **(ado) THE E2E LANE HAS A ROTATING WEBKIT TAIL. CAUSE FOUND 2026-08-15: THE BUDGET, NOT A
  MECHANISM.** ⚠ *Titled "CENSUS TAKEN, CAUSE UNIDENTIFIED" until 2026-08-15, when the decisive
  experiment identified it. The entry stays OPEN on the budget number alone.* Recorded
  2026-08-14 and filed rather than pursued: two hypotheses were killed by measurement in one day
  and the third needs a different instrument. ~~**This is not residue of the catalog-lock arc** -
  every run below had **zero** `database is locked` and zero `duplicate column`.~~ ⚠ **THAT CHECK
  CANNOT SEE THE CLASS IT WAS USED TO RULE OUT - see the amendment immediately below. Every
  "zero locks" line in this document inherits the same limitation.**

  ---

  ⚠ **AMENDED 2026-08-15: THE ZERO-LOCKS EVIDENCE IS THE WRONG OBSERVABLE.**

  `jobs.py:211-214` catches a busy catalog and replaces the sqlite error with
  `CATALOG_BUSY_MESSAGE` **before it reaches any log**. So a grep for `database is locked` over a
  lane's output cannot detect catalog contention inside a job: the string is never emitted.
  Measured on run `31895987230` - **0** hits for `database is locked`, **0** for
  `OperationalError`, and **1 real busy refusal**, which is what actually failed the run.

  **What this does and does not license.** It means contention was **never excluded** from the
  census - only never visible. It does **not** mean the censused failures were contention: no
  evidence here says they were, the traces that were read showed jobs reporting normally, and
  retro-fitting this mechanism onto fifteen failures nobody re-examined would be the same move
  this entry already criticises under its retired shapes. **The census stands; the exclusion does
  not.** Recorded rather than rewritten, because a claim that was believed and could not have
  been true is worth more visible than tidy.

  **The correct observable, for future runs** - any of the three, none of which is a log grep:
  - the shipped copy, which is what a user and a trace both see: grep the lane output for
    **`Another Truestill operation`** (`catalog_busy.py:45`);
  - the failing test's **trace DOM**, where the refusal renders into `#org-result` - it was
    sitting in this run's artifact the whole time;
  - the job's own **`CATALOG_BUSY_CODE`** (`catalog_busy.py`), which is the structured form and
    the only one that cannot be broken by rewording the message.

  🔢 **This is the same shape as the `AttachConsole` finding** (`PROJECT_STATUS.md` §3): not a
  contaminated measurement to be re-run, but an instrument pointed at something that could not
  answer the question. And it is this entry's own method lesson turned on itself - *ask what the
  lane already records* - because the DOM that names the cause was in `e2e-failure-artifacts`
  for every red run of this investigation.

  **What it cost here:** run `31895987230` failed on a **docs-only** commit and read as a
  sixteenth tail failure. It was not. It is filed as `(adt)`, and its mechanism is `(ads)`.

  ---

  ⚠ **ADDED 2026-08-18, AND IT IS A REPEAT RATHER THAN A NEW MEMBER - WHICH IS THE POINT.**
  Run **`32178286777`** on `0f48865` failed `test_the_choice_survives_a_reload[webkit]` on
  `assert 16 == 20 ± 0.5`. **Verified from both runs' `test-results-e2e` junit rather than taken
  on report** - run `31821214510`'s four failures were `test_the_choice_survives_a_reload`
  (`assert 16 == 20 ± 0.5`), `test_inplace_refuses_cross_device_...`,
  `test_organize_clears_typed_confirm_after_the_run` and
  `test_move_completion_reports_empty_folders_...`. Same test, same browser, **byte-identical
  assertion**. It is a **repeat, not a ninth test**, and the distinct-test count is unchanged.

  🔑 **AND IT IS THE SHAPE TABLE'S ONE-MEMBER ROW THAT CAME BACK, which is the sharper reading.**
  The distribution below records *"computed style after reload | **1** | `assert 16 == 20 ± 0.5`"*
  - a single instance, the only member of its shape and the only failure in the whole census that
  is **not** a post-job-text or page-load-ready stall. That lone row is now **2 of 2**, both the
  same test. **Within that shape nothing has ever rotated.**

  🔢 **AND IT WEAKENS THIS ENTRY'S OWN "ROTATING" CLAIM, which is why it is filed here rather than
  as a footnote.** The census reads *"membership rotating almost completely"* on the strength of
  eight distinct tests with **one** repeat. It is now eight distinct tests with **two**, and the
  new repeat is **five days after** its first appearance - and it is the one failure the census
  could never fit into either stall shape. A test that comes back after five days
  is weaker evidence of rotation than a set that never repeats - it is equally consistent with a
  small number of tests being genuinely more exposed. **The claim is not withdrawn and the
  alternative is not adopted**; what is recorded is that the evidence for it is thinner than the
  wording carries, and that the next repeat should be read against this paragraph rather than
  against the sentence below.

  ✅ **ADDED 2026-08-19: THIRD OCCURRENCE, AND THE MECHANISM IS FOUND. IT IS NOT THIS ENTRY'S.**
  Run **`32250647783`** on `65c6642` failed the same test, browser and assertion a third time -
  `test_the_choice_survives_a_reload[webkit]`, `assert 16 == 20 ± 0.5`, **in 3.2 s**. The duration
  is the tell: 3.2 s is nowhere near a budget, so the *"slow lane"* reading never applied to this
  member, which is why it sat alone in the shape table.

  **The real mechanism, traced rather than inferred.** Picking a size applies the attribute locally
  and then POSTs `/api/text-size/settings` (`app.js`), which `run_in_threadpool`s a **catalog
  write** (`server.py`). The test helper waited **200 ms** for that, then reloaded. **`(adt)`
  measured that exact write at 6,558 ms on a CI runner.** So the reload read a setting that had not
  landed, the page rendered medium, and a **plain `assert`** - not an `expect` - failed at once.

  🔑 **AND THIS IS WHY THE 30 s BUDGET COULD NEVER HAVE HELPED IT.** `(ado)`'s ruling raised the
  budget for **auto-retrying assertions**. `assert _body_px(ui) == pytest.approx(...)` is a bare
  Python assert evaluated once; Playwright's retry machinery never touches it. The one census
  member that did not fit the stall shapes is the one member the fix could not reach.

  **Fixed at the source rather than accommodated**: the helper now waits for the POST's own
  response (`expect_response`), and the post-reload check polls with `wait_for_function` instead of
  sleeping 400 ms. Playwright's guidance is explicit - *"Never wait for timeout... Tests that wait
  for time are inherently flaky."* The file also got **4.5x faster**, 37.32 s to 8.14 s, because
  the sleeps were the runtime.

  ⚠ **NOT REPRODUCED LOCALLY, and that is stated rather than hidden**: 8 consecutive runs green
  before the change, 6 more green under eight CPU burners after it. The fix rests on the
  **mechanism** - a fixed wait replaced by waiting for the thing itself - not on a reproduction.
  ⚠ **And 64 other `wait_for_timeout` calls remain across the suite**, 6 of them in this same file.
  This fixed the one that was failing; it did not fix the class.

  ⚠ **THE TEN-RUN WINDOW RESETS TO ZERO.** The lane had reached **seven** consecutive green runs
  since `31895987230` - four pushes and three scheduled nightlies on an unchanged tree. This
  failure resets it, exactly as the exit condition specifies (*"reset to zero by any failure"*),
  and `(ado)` stays open. **That is the condition working rather than a setback**: the previous
  shape - three consecutive greens - was retired precisely because a streak ending like this one
  would have closed the entry days earlier on a tail that had not stopped.

  **The census.** **Fifteen** failures across eight runs (`31816361658`, `31821214510`,
  `31823157259`, `31825233939`, and the four added 2026-08-15 below), **all of them `[webkit]`**,
  with membership rotating almost completely. One of the eight runs was fully green. ⚠ **Four of
  the eight are trees with no code change at all** - two runs of one commit, and two docs-only
  commits - which is the strongest evidence the tail does not track the code.

  ⚠ **Fifteen, not fourteen: `31870036688` had TWO failures and was first recorded as one.** The
  second was `test_the_backup_target_carries_over_from_the_check_field`, an `#org-confirm` stall,
  so that single run contains **both** of the shapes this entry used to separate - which is part
  of why they no longer are.

  🔢 **THE METHOD LESSON, and it is the most reusable thing in this entry.** `test-results-e2e`
  is uploaded with `always()`, so **per-test CI timings existed for the GREEN runs too, for the
  whole life of this investigation, and nobody read them.** The distribution table below cost no
  new instrumentation and no new runs - only opening an artifact the lane was already producing.
  Two hypotheses were killed and one entry rewritten before anyone looked. **Ask what the lane
  already records before building an instrument**; here the measurement predated the investigation
  by weeks.

  **ADDED 2026-08-15 - and this pair is the most informative entry in the census, because the two
  runs are the SAME COMMIT.** `31842922114` and `31863063168`, both on `99e35d4`, six hours apart,
  **one failure each, zero locks, all three `check` lanes green in both**:

  | run | test | assertion |
  |---|---|---|
  | `31842922114` | `test_reversible_organize_shows_durable_undo_affordance` | `to_be_visible`, `#org-confirm [data-typed-confirm]` |
  | `31863063168` | `test_a_finished_organize_says_organized_and_never_uploaded` | the same assertion, the same locator |

  Neither fails in its own body: both die at `test_ui_regressions.py:38`, inside the shared
  `_organize` helper. ⚠ **The first is byte-identical to a failure already in the census** -
  `31825233939` failed the same test at the same line on the same locator - so it is a repeat, not
  a ninth test; the second is new here. **An unchanged tree produced two different failures**,
  which is what a rotating tail looks like and what a regression cannot look like.

  **ADDED 2026-08-15, second pair - and this one narrows the tail for the first time.** Two more
  runs, **both on docs-only commits that changed nothing but Markdown**, one failure each, zero
  locks, all three `check` lanes green in both:

  | run | commit | test | stalled on |
  |---|---|---|---|
  | `31870036688` | `86e3c07` | `test_a_completed_copy_clears_the_stale_not_a_backup_message` | `#bk-result` |
  | `31871026358` | `e8c538c` | `test_golden_path::test_organize_then_back_up_then_check` | `#bk-result` |

  ⚠ **Different tests, different files, the SAME locator and the same stall point** - `#bk-result`
  still showing the pre-run card (*"8 photos · 16.1 KB to copy"*), the locator resolving **14
  times over 5 s** without ever changing. Until now the census had repeated symptoms but never a
  stall point; two consecutive runs landing on the same one is the narrowest signal it holds. ⚠
  **"The backup job started and never reported" was the first reading of this pair and it is
  WRONG** - the traces below show the job started in 5.909 ms and was reporting progress
  throughout. The pre-run card says nothing about the job, for the reason given under the
  retired shapes. The count of distinct tests is deliberately not restated.

  | shape | n | assertion |
  |---|---:|---|
  | post-job text never arrived | **8** | `to_contain_text 'Done'` / `'could not be organized'` / `to_be_visible` |
  | page load never reached ready | **3** | `Locator expected to have attribute 'ready'` |
  | computed style after reload | **1** | `assert 16 == 20 ± 0.5` |

  ⚠ **BOTH CANDIDATE SHAPES ARE RETIRED, 2026-08-15.** They were *"stalls at dedup start"* (the
  job never left `starting`) and *"stalls after the confirm"* (the organize run never reported).
  Struck on trace evidence: **neither describes what the app was doing.**

  ⚠ **WHY THE INSTRUMENT MISLED, which is the reusable half.** Playwright scopes an aria snapshot
  to the **asserted locator's subtree when that locator exists**, and falls back to the whole page
  only when it does not. So `#org-confirm [data-typed-confirm]` - which never appeared - produced a
  full-page snapshot showing `starting elapsed 4s`, while `#bk-result` - which *did* exist - produced
  a one-line snapshot of the pre-run card and nothing else. **The two shapes were an artifact of
  that difference, not a property of the failures.** `starting` also meant only *"no progress event
  has arrived yet at snapshot time"*, never *"the job is stuck at start"*. **A snapshot's scope is
  part of the reading**; treating two differently-scoped snapshots as comparable observations is
  what produced two shapes out of one mechanism.

  **THE MECHANISM AS MEASURED: THROUGHPUT COLLAPSE, NOT A HANG.** From `trace.network` and the DOM
  snapshots inside the failure traces CI uploads, on three failures. The jobs were **alive and
  reporting progress** at the moment of failure:

  | test | element | at failure |
  |---|---|---|
  | `..._clears_the_stale_not_a_backup_message` | `bk-meta` | `elapsed 5s · 2.1 files/sec` |
  | `test_organize_then_back_up_then_check` | `bk-meta` | `elapsed 5s · 0.4 files/sec`, bar at 13% |
  | `test_the_backup_target_carries_over...` | `org-meta` | `elapsed 5s · 0.2 files/sec` |

  The backup job **started cleanly** - `POST /api/backup/run` answered **200 in 5.909 ms** and the
  stream opened `200` - on a **16.1 KB, 8-file** copy. Roughly one file in five seconds. Attributed
  to the owning element rather than grepped loose, because both `bk-meta` and `org-meta` appear in
  every trace and a loose match reads one job's rate as the other's.

  ⚠ **`#bk-result` IS NEVER WRITTEN BETWEEN THE CLICK AND THE TERMINAL EVENT** (`app.js:3622`
  hides `#bk-run` and nothing else; the only writers are the four terminal branches at `:3619`,
  `:3625`, `:3627`, `:3628`). So the pre-run card persisting means exactly *"no terminal event
  arrived"* and **cannot distinguish never-started from still-running from dead-stream.** Progress
  lives in a different element. That is why the trace, not the snapshot, is the instrument here.

  **THE FACT THAT KILLS THE SIMPLE TIMEOUT STORY.** In green run `31838105689`,
  `test_organize_then_back_up_then_check[webkit]` took **12.73 s and PASSED**; in `31871026358` it
  **failed at 9.60 s**. Slower overall and green, faster overall and red. **A test fails when one
  `expect` exceeds its 5 s budget, and total duration does not predict that** - a slow test passes
  as long as no single wait goes over.

  **THE DISTRIBUTION, all four runs, WebKit only, 460 cases each.** Read from the junit artifacts:

  | run | result | median | p90 | p99 | **>5s** | >8s |
  |---|---|---:|---:|---:|---:|---:|
  | `31836139514` | green | 1.32 | 3.08 | 7.08 | **7** | 2 |
  | `31838105689` | green | 1.16 | 2.52 | 4.55 | **3** | 1 |
  | `31870036688` | RED | 1.34 | 3.39 | 8.35 | **18** | 6 |
  | `31871026358` | RED | 1.26 | 2.70 | 7.61 | **15** | 4 |

  ⚠ **The body of the distribution does not move; the tail explodes.** Median stays 1.16-1.34 s
  across green and red alike and p90 stays 2.5-3.4 s, while tests over 5 s go **3 and 7 (green) to
  15 and 18 (red)** and over 8 s **1 and 2 to 4 and 6**. This is not a slower runner - it is a
  minority of tests hitting multi-second stalls while the typical test is untouched.

  🔢 **NOT ESTABLISHED: why the tail thickens on some runs.** Runner image is **identical** across
  green and red (`ubuntu24/20260810.271`), as is runner version (2.336.0). Lane duration does not
  separate them either - green 1169/1214/1252/1266 s against red 1201/1244/1327/1391 s, ranges
  overlapping at n=4 per group. **GitHub exposes no per-run CPU, disk or noisy-neighbour data in
  these logs**, so there is nothing further to correlate against. Said plainly rather than
  reached at.

  🔬 **THE DECISIVE EXPERIMENT - RUN 2026-08-15. THE ANSWER IS BUDGET-VERSUS-TAIL.**

  **It completes. It is not a hang.** Three attempts of the WebKit lane with the `expect` budget
  raised 5 s → 60 s: **1,482 tests, zero failures, and not one case failed to finish.** The longest
  was `test_organize_then_back_up_then_check[webkit]` at **28.4 s, passing**, whose organize job ran
  from +7.06 s to +21.72 s - about **14.6 s inside a single blocked wait** - before the backup began
  and the test finished. The lane kills that wait at 5 s; given room it finishes.

  **The rate RECOVERS, which is the opposite of a stall.** From the longest case:

  | at | readout |
  |---:|---|
  | +4.03 s | `elapsed 5s · 0.2 files/sec` |
  | +6.05 s | `elapsed 7s · 0.2 files/sec` ← **the normal budget gives up here** |
  | +15.62 s | `elapsed 9s · 0.4 files/sec` |
  | +19.66 s | `elapsed 13s · 1.0 files/sec` |
  | +20.16 s | `elapsed 13s · 1.6 files/sec · less than a minute remaining` |

  **0.2 → 1.6 files/sec, an 8x recovery**, with the app's own ETA working throughout. Across the
  nine job-bearing waits: **four recover, three flat, one decays** (274 → 206 files/sec, a *fast*
  job, not a stall). **None approaches zero.** Lowest sustained rate anywhere: 0.3 files/sec, flat,
  completing at 8-13 s.

  ⚠ **THE OUTCOME LANDED OUTSIDE THE BANDS THIS ENTRY NAMED, and the bands were guesses.** They
  read *"completes at 8-20 s → budget-versus-tail; near 60 s → something retrying underneath;
  never → a real hang"*. The real figure is **28.4 s** - above the first band and nowhere near the
  second, so there is no timeout-and-retry underneath. **Tune to 28.4 s and the three attempts
  behind it, never to 8-20 s**, which was invented before any measurement existed.

  ✅ **What this settles:** the throughput reading was measuring the *right* phase, and the
  mechanism recorded above - throughput collapse rather than a stall - is **confirmed**. The fix is
  a **budget number**, not a mechanism.

  ⚠ **AND THE BUDGET IS DELIBERATELY NOT SET.** Picking it from three runs of the very lane whose
  tail is the thing being measured is the local-measurement trap wearing a different costume - the
  one that has caught this project three times. It wants more samples, or an explicit ruling that a
  slower lane with a higher budget is simply the cost of WebKit on a shared runner. **No timeout was
  changed by this experiment.**

  ⚠ **LIMITS OF THE INSTRUMENT, stated rather than discovered later.** The probe fixture measured
  **whole-test duration**, not a single `expect`. So *28.4 s* is the test, and the **14.6 s blocked
  wait is inferred** from the progress series spanning +7.06 s to +21.72 s while the test was
  waiting on the organize job's completion text - sound, but an inference, not a direct reading. A
  per-assertion timer would settle it. And **three attempts is three**: rates this variable deserve
  more samples before any number is tuned to them.

  ⚠ **The earlier members are still classified from snapshots**, which the scoping problem above
  now makes unreliable, and only these three have traces. Whether the whole family is one mechanism
  is **unestablished**: it is a claim to test, not a conclusion, and the reason for not lumping is
  on the record two entries down - `duplicate column` read as *the* mechanism of the lock arc when
  it was **4 of 88**.

  ~~⚠ **The concentration is real and is the strongest signal in the census.**
  `test_ui_regressions.py` holds **31 of 458** e2e test functions - **6.8%** of the suite - and
  produced **7 of 10** failures. Uniform failure would predict 0.7. That is a **10x**
  concentration, and it is not a big-file artifact: it is the largest file, but not by enough to
  matter. It is also where the job-driving tests live.~~

  ⚠ **STRUCK 2026-08-15: THE CONCENTRATION IS A SELECTION EFFECT, NOT A SIGNAL - and this is the
  more important half of the experiment.** The arithmetic above is correct and the conclusion drawn
  from it was wrong. Of the **37** waits over 5 s the probe recorded, **28 had no job running at
  all** - only **9** were job stalls. The longest non-job wait was **16.35 s**, on
  `test_the_chevron_follows_the_boundary`, `test_the_nav_is_grouped`, and other pure layout and
  page-load tests with no progress element on screen.

  **So the tail is general WebKit slowness on the runner, not a job problem.** `test_ui_regressions.py`
  dominates the census because it is where the tests with a **5 s wait in them** live, not because
  anything about it fails more: a slow layout test has nothing to time out *against*, so it is
  simply slow and green, while the same slowness inside a job wait fails an assertion and gets
  censused. **The file was selected by the instrument, not by the fault.**

  ⚠ **Every mechanism hypothesis this arc produced was therefore aimed at the wrong thing** - SSE
  buffering, the catalog lock, fixture teardown order, the `(adk)` SSE reader. `(adk)` was a real
  defect and is correctly fixed on its own evidence; it was never this. The last line of the struck
  paragraph - *"it is also where the job-driving tests live"* - was the observation that explained
  it, sitting in the entry the whole time, read as corroboration instead of as the answer.

  **RULED OUT BY MEASUREMENT, both of them:**
  - **SSE buffering.** Research describes WebKit withholding server-sent events until the
    connection is severed, which would fit exactly: our failures wait for text delivered over
    `/api/jobs/{id}/events`, and the fixture tears the server down *before* the page closes, so
    the sever that would flush a buffer happens after the assertion has already failed. **It does
    not happen.** Both ends instrumented, one real organize, 17 events: every event reached the
    client **1.5-45 ms** after the server yielded it, and the two engines' delta series are
    near-identical. Buffering would have put event 1 at ~351 ms and the last near 0. Independently,
    a chunked socket read against uvicorn showed one chunk per yield at 300 ms steps, and the app
    applies no compression middleware.
  - **The catalog lock.** Zero locks in all four runs, after `(adl)`'s sibling fix.

  **INVESTIGATED 2026-08-15, AND THE FINDING WAS A DIFFERENT DEFECT.** The teardown hypothesis
  below has a proven mechanism: `JobManager.stream` blocked in a timeout-less `queue.Queue.get()`,
  which kept a uvicorn server thread alive **20.00 s after `should_exit`** with the client already
  gone - and `RetiringServers._sweep()` reclaims a server by exactly that thread dying. Fixed as
  `(adk)`. ⚠ **It did not close this entry and must not be recorded as having done so:**
  instrumenting a real run of `test_ui_regressions.py` - 31 tests, both engines - showed **zero**
  live-thread growth, so the suite does not trigger it locally. The mechanism is real; its
  connection to this tail is **unproven**.

  🔢 **The measurement this entry still wants, named so the next person does not re-derive it.**
  WebKit is **1.79x slower than Chromium** under CI's own flags (76.61 s vs 42.83 s over the same
  31 tests) on a **16-core** machine; CI runners have **4**, and record video and traces for every
  test. The slowest assertion locally sits at **2.58 s against a 5 s Playwright budget**. That is
  thin headroom and it would explain both the WebKit skew and the job-driving concentration
  without any WebKit bug - but it is measured on the wrong hardware to conclude anything. **The
  open question is the distribution of these waits on a CI runner**, which needs instrumenting the
  lane itself, not another local run.

  **NOT RULED OUT:**
  - **Fixture teardown order.** `ui(page, app_server)` sets up `page` first, so pytest tears down
    `app_server` **before** the page closes - the server is told to exit while the page is still
    live. A test ending mid-job leaves an SSE stream open, uvicorn waits for the in-flight
    request, `_pending` grows past `RetiringServers.LIMIT = 8`, and `_join_one` blocks 10 s.
    Plausible and unmeasured; nothing in the census points at it either.
  - **A page load that never reaches `ready` with no lock present.** Three of the ten, and the
    original lock symptom wearing a different cause. Nothing explains these yet.

  **OPEN PRODUCT QUESTION, separate from the lane.** The SSE measurement covered a **351 ms job
  with 17 events**. WebKit is what the Tauri shell renders in on Linux and macOS, and the
  documented buffering behaviour may have a size or duration threshold that scale never reaches.
  **A multi-minute organize is untested.** If it does buffer at that scale, a user watches a long
  run with no progress at all - a product defect, not a test one.

  ⚠ **EXIT CONDITION: ZERO E2E FAILURES ACROSS TEN CONSECUTIVE RUNS.** A rate over a fixed
  window, counted whether or not the runs touch this lane, and reset to zero by any failure.
  ⚠ **The window stands at ZERO as of 2026-08-19**, reset again by run `32250647783` after
  reaching two - see the third occurrence recorded above, whose cause was found and fixed.

  **The old condition - three consecutive greens - was RETIRED 2026-08-15, and the pair above is
  what retired it.** The lane delivered **four** consecutive greens (`31832876792`,
  `31834436577`, `31836139514`, `31838105689`), passed the bar with one to spare, and then failed
  **twice on an unchanged tree**. The condition was met by luck and would have closed `(ado)` on
  a tail that had not ended.

  ⚠ **The error was in the SHAPE of the condition, not in its size, and raising three to five
  would repeat it.** A run of consecutive greens is a coin flip against an intermittent failure:
  at this tail's observed rate, a short green streak is the *likely* outcome of a lane that is
  still broken, so the old condition tested patience rather than the lane. What distinguishes a
  fixed tail from a lucky one is failures per run over a window long enough for the rate to show
  - which is why the replacement fixes the denominator and lets a single failure reset it.

  ⚠ **THE REPO ALREADY HELD THE RIGHT INSTRUMENT AND THIS ENTRY DID NOT REUSE IT.**
  `SHIPPED.md` `(abq)` works the identical problem numerically: at an observed rate of one failure
  in three runs, an unfixed flake survives N consecutive greens with probability `(2/3)^N`, giving
  **8 as the minimum bar and 12 preferred**, written down expressly "so nobody calls it fixed on
  the second green". Against that table the four greens this lane produced sit at **20%** - a
  one-in-five event, and no evidence at all. Ten runs is chosen to sit near that bar; the exact
  rate for *this* tail is not measured, because the failures are known and the total runs in the
  window have never been counted, so treat the window as the shape being fixed rather than as a
  calibrated number.

  The earlier reasoning that produced "three" is kept because it was right about the direction and
  wrong only about the instrument: run `31823157259` was green and the next failed three tests
  with no code change touching the lane, and **one** green had already been read here as "the lane
  is green" when it was not.
