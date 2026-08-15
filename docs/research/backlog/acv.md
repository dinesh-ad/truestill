# (acv) THE PRIVATE PATHS IN GIT HISTORY ARE ACCEPTED, NOT OVERLOOKED - and the repository goes private at launch.

*Body of backlog entry `(acv)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(acv) THE PRIVATE PATHS IN GIT HISTORY ARE ACCEPTED, NOT OVERLOOKED - and the repository goes
  private at launch.** Ruled 2026-08-11. `16d7b14` removed the maintainer's cloud-storage and
  private-folder strings from the working tree; **history still carries them and deliberately
  will.** Recorded because an accepted risk that is not written down is indistinguishable from one
  nobody noticed.
  - **What is exposed**, counted rather than characterised - and named by kind, because this entry
    may not reproduce the strings it is about (the widened guard refused its first draft, correctly):
    the **fenced folder's name** in **15 commits**, the **cloud mount path** in **4**, and the
    maintainer's **home-directory path** in **11**. That last appears in **zero tracked files
    today**, which is the reason this entry exists in this form: **a clean working tree is not
    evidence about history**, and it had already been mistaken for exactly that once.
  - ✅ **What `16d7b14` actually achieved, stated precisely: the leak is STOPPED, not removed.**
    Every future commit is clean, and `test_no_incidental_naming` now bans the terms so a
    recurrence is a test failure rather than a discovery. That is the half that mattered - without
    it the exposure kept widening with each commit, which is a different problem from the one
    already in the log.
  - **Why a rewrite was declined.** `git filter-repo` plus a force-push invalidates every clone and
    **several hundred SHAs cited in the docs** as `file:line` and commit references - the
    provenance trail this project is largely made of. GitHub also keeps unreachable objects
    readable after a force-push until support is asked to purge them, so the rewrite is not even
    self-completing. Days of work and a broken citation graph, to close a window that **closes
    itself at launch**.
  - ⚠ **The residual, stated plainly rather than minimised.** Someone who clones the repository and
    reads old commits learns that the maintainer uses a cloud storage service, and can see
    fragments of his folder tree. **No photos, no catalog, no credentials** - the catalog is
    gitignored and was never committed. That is the whole of it, and it is accepted for the
    remaining public window.
  - ✅ **THE MITIGATION IS A REQUIRED LAUNCH STEP, NOT A MEMORY:** *make the repository private*,
    recorded in `PROJECT_STATUS.md` §2. The repository stays public until launch for the Actions
    minutes and goes private then. A rule that depends on someone remembering is not a control
    (`ENGINEERING_STANDARD.md` §4, twenty-seventh member), which is why this is a checklist line
    with a cited reason rather than a resolution.
