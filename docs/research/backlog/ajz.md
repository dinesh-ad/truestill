# (ajz) `gh run view --log` SUCCEEDS WITH ZERO BYTES, AND A JOB'S LOG IS `BlobNotFound` UNTIL THE JOB ENDS.

*Body of entry `(ajz)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ajz)** Filed 2026-09-03 (P206). Two distinct behaviours in the tool this repository reads CI
  with, both of which return *"nothing is wrong"* when the honest answer is *"I could not tell
  you"*. This is the class `IMPLEMENTATION_STANDARDS.md` already rules against in its own tooling -
  *"an empty result means 'could not read' and 'nothing changed' alike - the old shape would have
  reported the reassuring one"* - and `(ajs)` is the same shape one layer up.

  ## BEHAVIOUR 1 - EXIT 0, ZERO BYTES

  The 2026-09-03 nightly `33731353952` went red on the e2e job. Reading it:

  ```
  $ gh run view --job=100571788576 --log > out.txt 2>err.txt ; echo "rc=$?"
  rc=0
  $ wc -c < out.txt
  0
  $ cat err.txt
  (empty)
  ```

  **Exit 0, no output, no stderr.** `gh run view --log-failed` behaves the same way. A caller that
  checks the exit code learns nothing; a caller that greps the output concludes the log is empty.
  In this session it converted a readable, decisive log into *"the lane's failures cannot be
  read"*, which is what P203 reported.

  The same job, through the REST endpoint, in one call:

  ```
  $ gh api "repos/{owner}/{repo}/actions/jobs/100571788576/logs" | wc -c
  318638
  ```

  And the answer was in it - the failing test, its locator, and the alert that named the defect:

  ```
  FAILED tests/e2e/test_archive_ingest_ui.py::test_cancelling_leaves_a_staging_tree_the_next_run_can_clear[webkit] - AssertionError: Locator expected to be visible
    - waiting for locator("[data-testid='rc-cancelled']")
  - alert: "Something went wrong /api/jobs/55993ed4f26c42b8b2da40b508100e9a/cancel did not return JSON:"
  ```

  ⚠ **Not retention and not permissions.** The run was hours old, and the same token read the same
  job through the API immediately afterwards.

  ## BEHAVIOUR 2 - `BlobNotFound` WHILE THE JOB IS STILL RUNNING

  A completed step's output cannot be read until the whole **job** finishes. Run `33796360000`,
  with `Runner spec` already `completed success` and `E2E` still `in_progress`:

  ```
  $ gh api "repos/{owner}/{repo}/actions/jobs/100784888253/logs"
  <?xml version="1.0" encoding="utf-8"?><Error><Code>BlobNotFound</Code><Message>The specified blob does not exist.
  ```

  This one at least **fails loudly**, which is the correct half. Its cost is latency, not a wrong
  answer: a four-line diagnostic step placed before a twenty-minute step is unreadable for twenty
  minutes.

  ## WHAT A CALLER MUST DO INSTEAD

  - **To read a finished job's log, use the REST endpoint**, not `gh run view --log`:
    `gh api "repos/{owner}/{repo}/actions/jobs/<job_id>/logs"`. Get `<job_id>` from
    `gh run view <run_id> --json jobs -q '.jobs[] | select(...) | .databaseId'`.
  - **Never treat empty output from `gh run view --log` as evidence.** Check the byte count, and
    if it is zero, re-read through the API before concluding anything.
  - **A diagnostic step's output is not available until its job ends.** Put a value you need
    quickly in a job that finishes quickly, or accept the job's full latency.

  ## WHY NO GUARD IS PROPOSED

  `(ago)`'s bar: a guard is an artifact that has to earn itself. Nothing here is our code - it is
  a third-party CLI's exit contract - and a test asserting that `gh` behaves would go red on
  `gh`'s schedule, not ours, which is the *"guard that goes red on the past"* shape
  `ENGINEERING_STANDARD.md` refuses. **This is a practice, and it is written where a reader of CI
  results will meet it.**
