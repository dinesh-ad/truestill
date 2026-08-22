# (afp) A CATALOG ANOTHER PROCESS IS CREATING IS REFUSED AS DEBRIS, AND THE ADVICE IS TO DELETE IT.

*Body of backlog entry `(afp)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afp) TWO PROCESSES, ONE COLD START, AND THE LOSER IS TOLD TO DELETE THE WINNER'S CATALOG.**
  Found 2026-08-22 while measuring `(aaw)`, which was looking for something else.

  ## WHAT HAPPENS, MEASURED

  Two `truestill organize --apply` runs start against a catalog path that **does not exist yet**.
  One creates the file and begins writing; the other arrives in the window where the file exists,
  is **0 bytes**, and has a **rollback journal beside it**. It refuses the entire run, exit **6**,
  and says:

  ```
  <path> is 0 bytes. Something created it and never wrote to it - a copy that failed part-way,
  or a run that stopped before its first write. It holds no photos and no settings, and Truestill
  will not open it: once opened, an empty file and a real library look the same. A rollback
  journal is beside it (<name>-journal), so a write to this catalog was interrupted. Your library,
  if you have one, is untouched. Rename or delete this file and run again, or pass --db PATH to
  point at the catalog you meant.
  ```

  ⚠ **"Rename or delete this file and run again" is being said about a live catalog that another
  process is writing at that moment.** A user who follows it deletes the database out from under a
  running organize. The refusal is loud, correct in its own case, and its remedy is the most
  destructive thing available here.

  **Reproduction rate: 2 of 6 concurrent cold starts**, then reproduced again on demand. It needs
  no unusual timing beyond starting two runs at once, which `(adn)` says a user reaches by
  double-clicking twice, and a third route needs no shell at all - `truestill organize` beside an
  open window.

  ## THE DISCRIMINATOR EXISTS AND IS NOT LOOKED AT

  `catalog_startup.py:116-133` already **finds** the journal and already reasons about it. Its
  docstring is careful and correct as far as it goes:

  > **The journal is evidence in one direction only.** Under `journal_mode=delete` … SQLite
  > removes the rollback journal on commit, so one still on disk means a write did not finish.
  > Its **absence proves nothing** …

  ⚠ **"A write did not finish" and "a write has not finished YET" are the same observation and
  opposite situations**, and the sentence the user reads picks the first: *"so a write to this
  catalog was interrupted"*. The live case is not considered. This is the same shape as `(aac)`,
  `(aer)` and `(afo)` - one signal standing for two states, with the dangerous reading as the
  default - except that here the product is not merely describing the wrong state, it is
  **recommending an action that is only safe in one of them**.

  ## WHY `(adr)` IS NOT WRONG

  `(adr)` shipped this refusal 2026-08-18 and is right about its own case: a `shutil.copy2` that
  died of `ENOSPC` leaves a real 0-byte file, and opening it would build a full schema into it and
  report a healthy empty library. **That defect is real and the refusal must stay.** What `(afp)`
  says is that the *same evidence* is produced by a healthy concurrent start, and nothing
  separates them.

  ## NOT DECIDED, AND DELIBERATELY NOT DESIGNED HERE

  - **Whether the fix is detection or wording.** A live holder is detectable - the winner holds a
    SQLite lock, so an attempt to open read-only would say so - but any detection is itself a race,
    and a wrong answer in the "it is live" direction re-opens `(adr)`'s defect.
  - **Whether the remedy sentence should simply lose its delete clause when a journal is present.**
    Cheapest possible change, no detection, no race: a journal means *either* interrupted *or*
    live, and "delete it" is unsafe under the second. It would leave a user with a genuinely
    interrupted catalog slightly less well served, which is a trade to rule on, not to assume.
  - **Whether this is `(aaw)`'s problem.** A cross-process lock taken before the catalog is opened
    would make the second run wait rather than refuse. That is one more argument for the lock and
    it is recorded in `(aaw)`, not settled here.

  ## RELATED

  `(adr)` (the refusal, shipped), `(adn)` (nothing stops two processes), `(ads)` (`journal_mode`
  is the default, which is what makes the journal a signal at all), `(aaw)` (the lock).
