# (akh) ONE WEBKIT LANE RUN LOST A CLICK ON `#rc-cancel` TO THE JOB FINISHING FIRST

**Filed 2026-09-06 (P248). No work attached, and deliberately not investigated.**

## What happened

`make e2e-fast`, both engines under `-n auto`, on the completion-card slice. One case failed:

```
FAILED tests/e2e/test_archive_ingest_ui.py::test_cancelling_leaves_a_staging_tree_the_next_run_can_clear[webkit]
E   playwright._impl._errors.TimeoutError: Page.click: Timeout 15000ms exceeded.
E     - waiting for locator("#rc-cancel")
E       - locator resolved to <button id="rc-cancel" class="btn btn-ghost">Cancel</button>
E     - attempting click action
E       2 × waiting for element to be visible, enabled and stable
E         - element is not visible
```

The element **resolved** and then was **not visible**: the run block had already been hidden,
because the job finished before the cancel could land. That is a click racing a job, not a broken
selector and not a missing wait.

## What is established, and what is not

| reading | value |
|---|---|
| occurrences | **1** |
| same file, both engines, in isolation | **3 of 3 green** (`--browser chromium --browser webkit`, 20 cases each) |
| the next full lane run | **green**, 1029 passed |
| the screen it is on | Import (`rc-*`), which the Organize React arc does not touch |

⚠ **ONE OCCURRENCE IS NOT A DISTRIBUTION.** Nothing here says how often it happens, on what load,
or whether `-n auto` is a factor - and a fix argued from a single sample would be a guess dressed
as a remedy. `ENGINEERING_STANDARD.md` §4's twenty-fifth member is the rule: for an intermittent
failure, repetition is evidence.

## The next step if it recurs, and it is not a fix

**Count the runs since the last red before diagnosing anything** - §4's twenty-sixth member,
which exists because a flake rate is the only thing that distinguishes a real race from a busy
machine. `gh run list --workflow ci.yml --event schedule --event workflow_dispatch` gives the
lane's own history, and the failure is identifiable by the test id above.

Only with a rate in hand is there a question worth answering, and the likely shape of the answer
is a wait the test does not currently have - waiting for the cancel control to be *visible* rather
than merely present - rather than a change to the product. **That is a hypothesis, recorded so it
is not mistaken for a finding.**

⚠ **The lane does not retry, on purpose** (`Makefile`, the `e2e` target: *"a retry-until-green
browser suite launders exactly the nondeterminism this layer exists to expose"*). The second full
run recorded above was a deliberate re-run after the failure was investigated to the point of
knowing it was not caused by the commit under test, and it is reported as a second sample rather
than as the result.
