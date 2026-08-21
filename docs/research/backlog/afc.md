# (afc) `verify` TELLS A USER TO RE-REGISTER A DRIVE THAT IS MERELY UNMOUNTED, AND FOLLOWING IT BREAKS THE DRIVE.

*Body of backlog entry `(afc)`, **CLOSED 2026-08-21**. The closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(afc) `(aap)`'s DEFECT, REACHED THROUGH THE ONE STATE ITS GUARD CANNOT SEE.** Found 2026-08-21
  by **soak three, step R4** - the first step of the first soak aimed at refusal.

  ## MEASURED, end to end, on a real FUSE-mounted drive

  A drive with 40 organized files, cleanly unmounted (`fusermount3 -uz`), so the mountpoint is
  **there, a directory, and empty**:

  ```
  $ truestill verify <mount>
  error: <mount> isn't a Truestill drive yet.
         Register it with:  truestill drives --init <mount>
  ```

  Following the product's own instruction:

  ```
  $ truestill drives --init <mount> --label SoakDrive
  Drive 'SoakDrive' initialised at <mount>  (uuid 2867a45f...)

  $ truestill drives
  SoakDrive    40 files   offline     <- the real drive, uuid 12631118
  SoakDrive     0 files   connected   <- a phantom, minted by following the advice
  ```

  ⚠ **And the drive can now never be remounted at that path.** `--init` wrote
  `.truestill-drive.json` and `.truestill-decisions.json` **into the mountpoint directory**, so it
  is no longer empty and the mount fails outright (`RuntimeError: 1` from libfuse; the same is
  true of any automounter, which will pick `MyDrive1` or refuse). Verified: the remount failed and
  `verify` then reported *"Drive 'SoakDrive' has no recorded copies in the catalog"* about a drive
  holding forty.

  ## ⚠ THE CORRECT WORDING ALREADY EXISTS AND FIRES ON THE OTHER HALF

  Kill the FUSE daemon instead of unmounting - the drive vanishes **uncleanly**, so the path
  returns `ENOTCONN` - and the same command says:

  ```
  error: <mount> is not there.
         If this is an external drive, is it plugged in and mounted? Check the path, then try again.
         Do NOT register the folder again while the drive is disconnected - that creates a second
         drive id for a library you already have.
  ```

  **The product already knows.** `cli.py:1084-1088` carries the argument verbatim: *"A path that
  is not there and a folder that is not a drive are different states with OPPOSITE remedies, and
  this printed the register suggestion for both… so the two must never share wording again."*

  ## WHY THE GUARD MISSES IT

  The branch is `if not path_is_usable_dir(path):` (`cli.py:1083`). That function answers *there*
  versus *not there* - and a cleanly unmounted mountpoint is **there**. It is a real, readable,
  empty directory. `(aap)` fixed the two states it knew about; this is a **third**: *present,
  readable, and not the thing it looks like.*

  ⚠ Exactly `(aey)`'s shape one level up - **the case with no errno takes the wrong branch, and
  the branch with an errno is correct.** Three instances now (`(aey)`, `(afb)`, this).

  ## WHAT IS **NOT** WRONG, checked because R4 existed to check it

  **No automatic path keys off the "gone" verdict**, which was R4's central question:

  - `undo.forget_organized` (`undo.py:215`) is gated on `step.current.is_file()` **and** a
    successful `rename`. On an unmounted drive the file is not there, so the step is skipped.
  - `migrate.forget_migration_move` (`migrate.py:786`) is gated on a successful `relocate` **and**
    a re-hash.
  - `reclaim`'s two gates fail safe and are now pinned (`(aez)`).
  - `drives` reports **`offline` with 40 files and `NOT FOUND -`**, which is exactly right: the
    drive is unplugged, not empty.

  The destructive step is the one the **user is told to take**.

  ## READ-ONLY INVESTIGATION, 2026-08-21 - three questions, answered

  ### 1. The three states, and whether they can be told apart

  **Not from the filesystem. Measured:**

  | | `os.path.ismount` | `st_dev` vs parent | in `/proc/mounts` |
  |---|---|---|---|
  | empty dir, never a mountpoint | `False` | same | no |
  | empty dir, **stale mountpoint** | `False` | same | no |
  | mountpoint with something mounted | `True` | *differs* | yes |

  **An unmounted mountpoint is byte-for-byte an ordinary empty directory.** The state exists only
  while the mount does. macOS behaves the same way (`getattrlist`/`statfs` describe what is
  mounted *now*; an unmounted point is a plain directory). Windows has no equivalent state at all
  - a removed volume takes its drive letter with it, so the path fails to resolve rather than
  becoming empty, and a mounted folder that is emptied is likewise indistinguishable.

  ⚠ **The product already measured this and wrote it down.** `drive.ghost_drive_at`'s docstring:
  *"`os.path.ismount` is true only while something IS mounted, so it returns False for exactly
  this case; the mount table and `/etc/fstab` keep no record once a FUSE mount is gone; and
  matching the drive LABEL against the directory name is a coin toss."*

  **But they CAN be told apart from the catalog.** `settings` holds
  `path_hint.drive.<uuid>` - where each drive was last seen - and `ghost_drive_at` reads it:
  *"Only a recorded path discriminates it… the answer has to come from outside it."* Verified in
  R4: the hint for the real drive was **exactly** the mountpoint path.

  So the states are: **there / not there / there-but-not-what-it-looks-like**, and the third is
  answerable **for any drive whose path was recorded**. The residual is a drive with **no** hint -
  `DriveReach.UNKNOWN`, which `drive.py:145` calls *"the normal state"* for a CLI-only user.

  ### 2. Why one absence path got the correct wording and the other did not: **inherited**

  Not a reasoned exclusion. The machinery exists, is complete, and is wired to the wrong commands:

  - `ghost_drive_at` (`drive.py:597`) and `ghost_drive_refusal` (`drive.py:699`) exist, with the
    full three-fact wording **including the data-loss warning** nobody could discover alone:
    *"Anything written here now would go onto THIS computer's disk, and would DISAPPEAR from view
    the moment the drive comes back - while still using the space."*
  - **Two callers, both on the `organize` registration path**: `cli.py:2285`
    (`_approve_registration`) and `service/organize.py:1009`.
  - ⚠ **`drives --init` is not one of them.** `_init_drive` (`cli.py:1026`) guards by **content** -
    `drive_adoption` samples files - and its docstring already claims the property:
    *"refusing to mint a second identity for a known library"*. An empty mountpoint holds no
    content, so the sample is empty and it proceeds. This is exactly what `ghost_drive_at`'s own
    docstring predicts: *"`(aap)` arriving through the one door `(aap)`'s content-based guard is
    blind to - it recognises a folder that HOLDS a known library, and this one holds nothing."*
  - And the resolver at `cli.py:1099` - used by `verify`, and the source of the bad advice -
    consults neither.

  **So it is two gaps in a chain: the message points at the one registration command that is not
  ghost-guarded.** §4's fifty-sixth member, with the guard written and the surfaces uneven.

  ### 3. What the message should say - OPTIONS, for the maintainer to rule on

  Framed by the fact above: for a drive **with** a hint this is a solved problem; the dilemma is
  only the **no-hint** residual.

  **A. Wire the existing guard into both places.** `_init_drive` calls `ghost_drive_at`; the
  resolver does too and prints `ghost_drive_refusal` instead of *"register it"*.
  *Cost:* nothing new to design - it is the wording already written and already shipped on the
  organize path. *Residual:* a no-hint drive still gets today's message, and a user who
  registered from the CLI and never organized has no hint.

  **B. A, plus the no-hint case stops instructing.** Where nothing discriminates, the message
  offers both readings rather than one: *"If this is a new folder, register it with `--init`. If
  this is where a drive should be mounted, connect it first - registering now creates a second
  identity."* *Cost:* a longer message on the ordinary new-drive path. *Residual:* none, but it
  puts the burden on the reader in the case the product genuinely cannot resolve.

  **C. A read command never instructs registration.** `verify` reports what it found and stops;
  `--init` is only ever something the user chooses. *Cost:* a real new-drive user loses a helpful
  pointer and must find the command. *Residual:* none, and it removes the whole class - no read
  command can send anyone toward a destructive write.

  **D. `--init` refuses an EMPTY directory unless told otherwise**, independent of hints, on the
  ground that a drive being registered normally has files. *Cost:* the genuine
  register-a-blank-new-disk case needs a flag; `--force-new-identity` already exists and could
  serve. *Residual:* none for empties, but it is a blanket rule where A is a targeted one, and it
  changes a command that is behaving correctly today for non-empty folders.

  **E. Shrink the residual instead of changing the message**: record `path_hint.drive.<uuid>` at
  registration and at every command that resolves a drive, not only where it is recorded now.
  *Cost:* none to wording. *Residual:* helps only after the first sighting - a freshly registered
  drive still has no history the first time it goes missing.

  ⚠ **A and E compose; C and D are exclusive of each other in spirit** (one removes the advice,
  the other guards the command it points at). **B is A plus an answer for the residual.**

  ## PRIOR ART - recorded as something a user can do, not as something we implement

  The pattern is **refusal against a recorded expectation, not filesystem detection**, and it is
  not ours. Administrators set the **immutable flag on an empty mountpoint by hand** -
  `chattr +i /mnt/backup` - precisely so that a backup run cannot write into it while the drive is
  absent and fill the local disk with files that vanish behind the mount when it returns
  ([j7k6, *Prevent Writes to Local Disk when NFS Mountpoint is not Mounted*](https://docs.j7k6.net/nfs-mountpoint-prevent-unmounted-write/)).
  Borg users do the same on repository mountpoints.

  ⚠ **It has a known cost, which is why it is recorded and not adopted**: `chattr +i` breaks
  `borg mount`, because Borg checks that the directory is writable before mounting a FUSE
  filesystem that never writes there ([borgbackup/borg#4948](https://github.com/borgbackup/borg/issues/4948)).
  A tool that hardened the mountpoint for its user would break every other tool's mount.

  **Truestill does not set it, and should not.** What the practice confirms is the *diagnosis*:
  the system cannot tell an unmounted mountpoint from an empty folder, so people compensate with
  an out-of-band record of intent. `path_hint.drive.<uuid>` is Truestill's version of that record.
  A user who wants belt-and-braces protection can still set the flag themselves - and if they do,
  Truestill's refusal fires first and explains why, which is strictly better than a write that
  fails with `EPERM`.

  ## NOT DECIDED

  - **Whether `path_is_usable_dir` should learn the third state**, or whether the caller should
    ask a different question - *is this the drive I recorded?* - before offering to register it.
    The catalog knows a drive with copies was last seen at this path; nothing consults that.
  - **Whether `drives --init` should refuse an empty directory that the catalog knows as a drive
    root**, independent of the message. A remedy that cannot be followed wrongly is better than a
    message that says not to.
  - **Whether writing a marker into a mountpoint should be prevented at all** - it is the step
    that makes the damage permanent rather than merely confusing.
