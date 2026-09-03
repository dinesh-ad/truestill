# (aka) A PROSE SWEEP SCOPED TO PROSE FILES MISSES PROSE IN CODE.

*Body of entry `(aka)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aka)** Filed 2026-09-03 (P206), from my own error the commit before. **A record, not work.**
  P204 corrected the falsified claim *"the publish job has never run"* in three places, verified the
  correction, and reported the sweep complete. It was not complete: the sweep's pathspec was
  `*.md`, and a fourth copy lived in a workflow comment.

  ## THE MISS, PASTED

  The sweep that was run, and reported as exhaustive:

  ```
  git ls-files '*.md' | ... grep -nHiE "never (run|fired|been run)|has never|0 tag-triggered"
  ```

  What one command over the whole tree found the next day:

  ```
  $ git grep -nI -e "publish path has never fired" -e "publish job has never" -- . ':!*.md'
  .github/workflows/ci.yml:448:  # ⚠ BEFORE A TAG, RUN IT. The publish path has never fired and this lane is the only thing that
  ```

  Corrected in `0ff18ef`, twelve hours after the commit that reported the class closed.

  🔑 **The claim was load-bearing where it sat.** `ci.yml`'s banner is what a person reads when
  deciding whether to dispatch the browser lane before tagging - so the stale half of the reason
  was in front of exactly the reader it could mislead.

  ## THE HALF THAT DID NOT NEED FIXING, CHECKED RATHER THAN ASSUMED

  ```
  docs/research/backlog/afg.md:56:    page and no audience - which is what a first tag is *for* when the publish job has never run
  ```

  It reads on immediately: *"⚠ **That premise expired 2026-08-30**: the publish job ran on a
  throwaway tag"*. Already corrected, on the day it expired. A grep hit is not a defect, and the
  body had to be read to know that.

  ## WHY THERE IS NO GUARD, STATED RATHER THAN LEFT AS A GAP

  A guard would have to know a sentence is **false**, which is not a property any test in this
  repository can evaluate - `test_live_documents_cite_code_that_exists.py` reads *code citations*
  and cannot see prose at all, which `CLAUDE.md` already records for the quote-the-line rule.
  A duplicate-string detector across `*.md` and code would fire on every shared quotation in the
  repository, of which there are many by design, and `(ago)`'s bar refuses a guard that would have
  gone red on the past on the day it was written.

  ## SO IT IS A RULE FOR THE NEXT SWEEPER, AND IT IS ONE LINE

  **When correcting a factual claim, sweep with `git grep` over the whole tree, not over
  `*.md`.** Prose lives in workflow comments, docstrings, `Makefile` comments and `pyproject.toml`
  comments - all four carry load-bearing argument in this repository - and a pathspec is the one
  part of a sweep that nothing reports back to you. The command is no longer:

  ```sh
  git grep -nI -e "<the claim>" -- .        # every tracked file, code included
  ```

  This extends `CLAUDE.md`'s existing rule - *"a census or a claim is re-run before it is acted
  on"* - with the half it did not say: **re-run it over everything, and read each hit before
  calling it a defect.**
