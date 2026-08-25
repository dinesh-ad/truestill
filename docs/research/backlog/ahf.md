# (ahf) THE THREE APP-ONLY MUTATING RUNS ARE RESOLVED: TWO CLIs AND ONE RECORDED DEFERRAL.

*Body of backlog entry `(ahf)`, now in [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahf) THE THREE APP-ONLY MUTATING RUNS ARE RESOLVED: TWO CLIs AND ONE RECORDED
  DEFERRAL.** Filed 2026-08-25
  (P68); **both backup stages shipped the same day** (P70 the engine, P71 the CLI). ⚠ **The entry
  stays OPEN for `trip apply`**, which has neither a CLI nor a deferral row.

  ## THE RULING

  **Backup gets a CLI.** **Trip apply gets a CLI or a recorded row** in `BACKLOG.md`'s
  *App-surface deferrals* register. Either is a decision; silence is not, and that is the whole
  point of that register - its own words are that *"an undocumented single-surface contract is
  indistinguishable from drift."*

  ## VERIFIED TODAY, NOT CARRIED FORWARD (70th member)

  P64's census was four commits old, so each claim was re-checked:

  | claim | the check |
  |---|---|
  | `backup` is app-only | `backup_run` is defined at `service/backup.py:175` (`:621` before `(ahf)` stage 1 moved the engine out from under it); its **only** reference outside `truestill-app` is a core *test docstring* reading *"its own copy loop, in the app package only"* |
  | `trip apply` is app-only | `apply_event_review_names` (`service/trips.py:479`) has **zero** references outside the app package |
  | neither has a deferral row | the register holds **three**: the date rescue, `reclaim`, and the `{camera_model}` token |
  | no closure ruled on it | zero hits in `SHIPPED.md` for a backup-CLI or trip-CLI ruling |

  ⚠ **The near-miss that check has to survive**: `cli.py` imports `catalog_backup.BackupOutcome`
  and the word *backup* appears in the `drives` help text. Both are the **pre-upgrade catalog
  copy** and the noun for a drive - neither is the library-to-drive backup. A grep for "backup"
  alone answers yes and is wrong; the 69th member applied.

  ## THE ARGUMENTS, RANKED

  1. 🔑 **`PROJECT_STATUS.md` §1b's fourth exit condition.** The engine finishes first, and the
     app is a panel over it. A run the engine cannot perform is a panel over nothing.
  2. 🔑 **An app-only mutating run cannot be tested the way every other one is**, and `(ahd)`
     proved this rather than argued it: removing the confirmation guard from the write left
     **every** CLI test green, because the CLI aborts at its typed prompt before the engine is
     reached. A guard only one surface exercises is a guard the next surface loses. That defect
     was found by a mutation, one commit after the guard was claimed to be correct.
  3. **The field.** Every comparable tool exposes backup on the command line: **restic** and
     **borg** are CLI-only engines with GUIs layered over them (Vorta over borg); **Kopia** ships
     CLI and KopiaUI; **Duplicati** ships GUI, CLI, Server and Agent packages of one engine, its
     docs saying the CLI exists for setups that *"do not benefit from a UI"* and use an external
     scheduler; **PhotoPrism** has `photoprism backup`; **Immich** has a CLI and a REST API. Even
     **Time Machine**, the most GUI-first consumer tool there is, ships `tmutil startbackup` and
     documents `--block` to wait for completion - built for scripts.
     The cautionary case is **Lightroom Classic**: catalog backup runs only on exit, there is no
     supported scripting path, and users have asked for a *"Backup Now"* button for years. That is
     the closest analogue to where truestill stands today.

  ⚠ **THE CAVEAT, and it belongs beside the field evidence rather than under it.** Those tools
  are **server-side or repository** operations, where headless and scheduled use is the normal
  case. **Truestill's backup is a local desktop copy to an attached drive.** The headless/NAS
  argument does not transfer at full strength, which is exactly why it is ranked **third**. The
  two arguments above it are ours and are about this codebase.

  ⚠ **NULL RESULT, and it is the strongest single finding of the search: no maintainer anywhere
  was found publishing a defence of keeping backup GUI-only.** Recorded as a null rather than as
  agreement - nobody arguing for a position is not the same as everybody arguing against it, and
  the difference matters if someone later finds the defence we did not.

  ## WHAT A CLI BACKUP NEEDS - and it is NOT bake's answer

  `(ahd)` step 1 found bake had **two** app-side imports and that almost everything already
  existed. **That does not hold here.** `service/backup.py` imports **four**:

  * `jobs.JobTarget` - the same callable alias bake faced; core can spell it itself;
  * `drive_support.not_a_drive` - a UI payload, the same wrong-direction dependency;
  * `drives.BACKUP_PATH_HINT` **and `attach_drive`** - and `attach_drive` is a substantial app
    service, not a value;
  * `media_support.media_breakdown`.

  So this is a **bigger** core-computes/app-wraps move than bake's, not a smaller one. Said here
  so whoever starts it does not price it from `(ahd)`.

  ## A STALE PIN FOUND WHILE VERIFYING THIS

  ⚠ `backup.py:157` in core - `service/backup.py:266-268` until stage 1 moved it - states the fail-fast policy **changed on 2026-08-23** -
  *"Returned rather than raised, and that is the whole of the policy change"* - while
  `test_the_app_records_what_a_run_did.py`'s `backup` row still asserts *"It still FAILS FAST"*.
  **One of the two is false**, and the test is the one whose stated job is to record each
  surface's state *with its reason*. Recorded rather than fixed: P68 is docs-only and that is a
  test file. It is the `(agc)` shape in the guard written against it.

  ## ⚠ THE WRITE-PATH GUARDS, PROVED RATHER THAN ASSERTED (P71)

  `(ahe)` taught that a guard at "the only caller" is invisible until a second surface exists. So
  each was removed in turn and the suite run:

  | guard | killed by |
  |---|---|
  | verify-after-write (the digest comparison) | the backup suite |
  | the staged copy never taking the real name early | the backup suite |
  | `persists_for_the_run` on a **copy** failure | the backup suite |
  | `_stop_if_ground_moved` | the backup suite |
  | `persists_for_the_run` on a **commit** failure | ⚠ **NOTHING. Survives the whole suite.** |

  ⚠ **AND THE MORE IMPORTANT FINDING: the CLI tests alone kill NONE of them.** Every one survived
  `test_backup_cli.py` on its own. That is **not** because the guards sit at the caller - they are
  inside `copy_to_drive`'s call graph, so the CLI inherits them - but because a happy-path fixture
  never reaches them. It is P70's lesson repeated: **a mutation the fixture cannot reach proves
  nothing**, and a test file that exercises a path is not the same as one that proves its guards.
