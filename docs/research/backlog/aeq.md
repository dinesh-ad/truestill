# (aeq) THE INSTALL BOUND WAS CARRIED TO ONE OF THREE LANES, AND THE THIRD MET THE 503 THE FIRST ONE SAYS WE NEVER SEE.

*Body of backlog entry `(aeq)`, **CLOSED 2026-08-21**. The closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ⚠ CLOSED THE SAME DAY, AND WHAT CHANGED BETWEEN FILING AND FIXING
>
> This was filed as a one-instance finding. **It recurred forty-five minutes later, on a
> docs-only push**, with an identical 503 from the same feed and the same package version - two of
> three install attempts in thirty minutes. That moved it from *a transient worth recording* to
> *the lane is down*, and it was fixed immediately.
>
> **The section below headed "What is not decided" is left exactly as written.** Three of its four
> questions were answered by the fix, and one - the rate - was answered by the recurrence rather
> than by any instrument, which is itself the finding that section predicted:
>
> - **"Whether the answer is a bound, a retry, or neither"** → all three, per lane, because the
>   lanes were missing different halves. And the retry is keyed on the **probe**, not the exit
>   code: `chocolatey/choco#1609` confirms choco returns 0 after a feed 503, so a status-keyed
>   retry would be a loop that never loops.
> - **"`ci_bounded.sh` is bash and the Windows step is `pwsh`"** → the warning was right and the
>   answer was **not to port it**. The Windows mechanism keys on a different observable, so
>   sharing the script would have shared the wrong logic.
> - **"Whether macOS gets the same treatment"** → yes for the probe, **no for the retry**. A retry
>   written against a failure nobody has observed is a guess (§4, fifty-second member).
> - **"Not measured: how often this fires"** → still not *instrumented*, and the entry said why:
>   `flake_report` reads uploaded artifacts and a step dying before pytest uploads none. It was
>   measured by hand, from two consecutive pushes, because the instrument that would have answered
>   it is silent about exactly this case.

- **(aeq) `exiftool` IS INSTALLED THREE WAYS AND ONLY ONE IS BOUNDED OR RETRIED.** Found
  2026-08-21 by the Windows lane on run `32464521380`, job `96718196842`, while pushing `(aek)`.

  ## ⚠ THIS ONE HAS AN INSTANCE; `(aeh)` AND `(aeg)` HAVE PREDICTIONS

  Stated first because it is the only thing that distinguishes the three. `(aeh)` argues the
  runner image should be pinned and says plainly that *"pinning fixes nothing by itself"*;
  `(aeg)` proposes caching Playwright's system libraries so `--with-deps` stops invoking apt at
  all, and is the right long answer to `(aee)`. Both are reasoning about failures that **could**
  happen. This one is a log.

  ## THE MEASURED INSTANCE

  ```
  Chocolatey v2.7.3
  Failed to fetch results from V2 feed at
    'https://community.chocolatey.org/api/v2/Packages(Id='exiftool',Version='13.59.0')'
    with following message : Response status code does not indicate success: 503 (Service Unavailable).
  Unable to find package 'exiftool'.
  Chocolatey installed 0/0 packages.
  ```

  A literal `503`, with the status code printed, from a third-party CDN. No test ran: the step is
  `Install exiftool (Windows)` and it sits ahead of pytest. One re-run of the same commit was
  green, which is what a transient outage looks like.

  ## ✅ THE GUARD WORKED, AND MUST NOT BE TOUCHED

  The step is `choco install exiftool --no-progress` followed by `exiftool -ver`, with a comment
  saying why: *"choco can return 0 after a feed timeout, and a silently missing exiftool surfaces
  minutes later as twenty unrelated-looking test errors instead of one clear failure here."*

  That is exactly what happened. PowerShell's error trace names **line 3** (`exiftool -ver`), not
  line 1 (`choco install`), so the probe is what turned a missing binary into one legible failure.
  **A guard is not a bound and is not a retry**, and this entry is only about the two that are
  missing.

  ## THE THREE SURFACES

  | lane | how exiftool is installed | bounded | retried | guarded |
  |---|---|---|---|---|
  | Linux | `./scripts/ci_bounded.sh 180 sudo apt-get install -y libimage-exiftool-perl` | ✅ | ✅ | - |
  | macOS | `brew install exiftool` | ❌ | ❌ | ❌ |
  | Windows | `choco install exiftool --no-progress` + `exiftool -ver` | ❌ | ❌ | ✅ |

  Three ways to install one dependency, three different levels of care. macOS is the least
  defended of the three and has never been the one to fail, which is the reason to say so here
  rather than wait for it.

  ## ⚠ THE PREMISE THAT EXPIRED, AND IT IS THE POINT OF THE ENTRY

  `scripts/ci_bounded.sh` argues in writing why its pause is not exponential backoff, and its
  **first** reason is:

  > **We never see the 503.** The standard advice is "retry only transient errors - 429, 503,
  > 504". apt swallows the status and DEADLOCKS, so our only observable is exit 124, a hang. A
  > rule keyed on status codes cannot be written against a signal we do not receive.

  That reasoning is **correct about apt** and false one lane over. choco printed the 503 with the
  number in it. The clause is a statement about what this project can observe, and it was true of
  the surface it was written for and untrue of the surface beside it -
  `ENGINEERING_STANDARD.md` §4's **thirty-second member**, a clause asserting a state that expires
  in silence.

  **THE TELL, RECORDED BECAUSE IT IS REUSABLE:** a comment explaining why *this* surface needs a
  narrower answer is evidence that a **general** rule was discovered and then applied **locally**.
  When you find one, the question is not *"is this surface correct"* - it is **"which surfaces was
  this never carried to"**. §4's fifty-sixth member states it, `(aei)` is the product instance
  (dedup scoped per destination, written down twice, never carried to the write path), `(aek)` is
  the second (a full disk handled by two of three writes in one command), and this is the third -
  in the build rather than the product. Three instances of one shape in two days is why it is
  worth writing the tell down rather than the three findings.

  ## WHAT IS NOT DECIDED

  - **Whether the answer is a bound, a retry, or neither.** A 503 is *the* textbook retryable
    status, so the case for retrying Windows is stronger than the case that produced
    `ci_bounded.sh` - which had to bound a hang it could not classify. Those are different
    remedies and this entry should not assume the apt-shaped one fits.
  - ⚠ **`ci_bounded.sh` is a bash script and the Windows step is `pwsh`.** Reusing it directly is
    not free, and on 2026-08-20 the three-OS matrix caught *"Windows being unable to execute a
    bash script"*. **Do not assume the existing tool ports**; that assumption is the same shape as
    the entry itself.
  - **Whether macOS gets the same treatment in the same change.** It has no guard at all, so a
    `brew` that half-succeeds is the twenty-unrelated-test-errors case the Windows comment
    describes, with nothing to catch it.
  - **Whether this is worth doing before `(aeg)`.** `(aeg)` removes the largest apt consumer
    entirely; if the exiftool installs were also removed or cached, most of this entry evaporates.
    ⚠ But `(aeg)` explicitly **does not cover the `check` lanes**, which still need exiftool - so
    it cannot close this on its own, and `ci_bounded.sh` stays either way.
  - **Not measured: how often this actually fires.** One instance in one day is an existence
    proof, not a rate. `flake_report` reads uploaded artifacts and a step that dies before pytest
    uploads none, so the existing instrument cannot answer it - `ENGINEERING_STANDARD.md` §4's
    fifty-fourth member, an instrument silent about exactly the situation it would be consulted
    for.
