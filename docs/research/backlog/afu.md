# (afu) THE RUN RECORD IS CLI-ONLY, AND THE SURFACE IT MISSED IS THE ONE §1'S OWN REASONING NAMES.

*Body of backlog entry `(afu)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afu)** Found 2026-08-22 by a whole-backlog re-read against current code, four commits after
  `(afl)` shipped. **Not a defect in `(afl)`** - what it built is correct and tested. This is the
  rule reaching one of two surfaces, which is `ENGINEERING_STANDARD.md` §4's **fifty-sixth
  member**: *a rule applied to two of three surfaces reads as settled, and the third disagrees
  silently.*

  ## THE MEASUREMENT

  ```
  record_path_for      -> ONE caller: cli.py:2787
  RUN_RECORD_FILENAME  -> defined in app_paths.py, used nowhere else
  grep 'last-run|last_run' packages/truestill-app/src  -> no match
  ```

  `(afl)`'s own commit touched `truestill-cli/src/truestill_cli/cli.py` and
  `truestill-core/src/truestill_core/app_paths.py`, and nothing else. **The app writes no run
  record at all** - not for organize, not for backup, not for migrate, not for bake, not for
  undo. Every one of those is a run that changes the library.

  ## ⚠ WHY THIS IS THE SHARPEST FORM OF THE FIFTY-SIXTH MEMBER YET RECORDED

  The usual shape is a rule discovered locally and never generalised. Here the rule is **stated as
  a product invariant in the binding contract**, in `IMPLEMENTATION_STANDARDS.md` §1, quoted
  rather than paraphrased:

  > *"**A run that changes the library writes down what it did, beside the catalog, without being
  > asked**… **Automatic because the user who most needs it is the one who did not know to ask**;
  > `--report PATH` says only *where* it goes."*

  🔑 **The user who did not know to ask is the app's user.** A person driving `truestill organize`
  from a terminal is, by construction, the one who could have passed `--report`. The buyer D9
  launches for - Windows, an installer, a double-clicked icon - is the one the sentence is about,
  and is the only one the feature does not reach. **The invariant's own justification names the
  surface it was not carried to**, which is what makes this worse than an ordinary gap: a reader
  who checks the contract finds the rule, finds it reasoned, finds it shipped, and has no way to
  learn it stops at the terminal.

  ⚠ **And `(afl)`'s title is *"a run writes down what it did"*, unqualified.** Nothing in the entry,
  the contract row or the commit says *the CLI's* run. Two thirds of this repo's re-read findings
  are titles that read as whole features when a surface remains - the same correction `(aac)`,
  `(aap)` and `(abe)` all carry.

  ## IT ALSO COVERS `(aac)` RESIDUE 2, AND THAT IS NOT A COINCIDENCE

  `(aac)` residue 2 is *"the app's **run** completion has no `unreadable_files`. Preview only…
  The CLI reports on both."* A run record built **from results** carries every file's outcome,
  and an unreadable source is an outcome. So the two are one remedy seen from two sides:

  - `(aac)` asks for the **screen** to name unreadable sources after an app run;
  - this asks for the **record** to exist for an app run at all.

  A record that carries outcomes satisfies the durable half of `(aac)` residue 2 without touching
  a payload key or a renderer - which is the cheaper half, and the one that survives the terminal
  scrolling or the tab closing. ⚠ **It does not close `(aac)` residue 2 outright**: a file on disk
  is not a sentence on screen, and §9's never-silent rule is about what a user *reads*. Whoever
  builds this should say which half they took.

  ## WHAT IS NOT DECIDED

  - **Where the writing belongs.** `(afl)` put it in `cli.py`, after `execute` returns. The app's
    equivalent seam is `service/`, and `IMPLEMENTATION_STANDARDS.md` §2 already rules that
    `service/` is where state and work cross the boundary - so a record written from a route
    handler would be the violation, not the fix. **The strong candidate is core**, with two
    callers, because `(afl)`'s builder currently lives in the CLI and a second copy is the
    duplication §4 warns about - *"the remedy for any instance is usually to delete one of the
    two copies, not to add a second assertion."*
  - **Which app runs write one.** Organize and backup obviously. Migrate, bake and
    `undo-organize` all change the library too, and `(afi)` already ruled that both journals keep
    their own promises - so "every mutating run" is the consistent answer and also the largest.
  - **Whether one rolling file per catalog still holds with a job runner.** The app can have a
    job in flight while a user starts another on a different drive; `(aaw)`'s lock makes that
    safe per drive but does not serialise *different* drives. One rolling file would then be
    overwritten by whichever finished last, which is the concurrency question `(afl)` never had
    to answer because a CLI runs one command at a time. **This is the part to design first.**
  - **Whether the app surfaces its existence.** The CLI says where the file went; the app has no
    equivalent line, and a record nobody can find is `(acc)`'s shape.

  ## RELATED

  `(afl)` (the record, shipped 2026-08-22 - this is the surface it did not reach), `(aac)`
  residue 2 (the same gap from the screen's side), `(aaw)` (whose per-drive lock is what makes
  the concurrency question above answerable), `(aem)` (`organize_runs`, which covers the *killed*
  run from the other side and is already cross-surface).
