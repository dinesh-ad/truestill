# (afc) `verify` TELLS A USER TO RE-REGISTER A DRIVE THAT IS MERELY UNMOUNTED, AND FOLLOWING IT BREAKS THE DRIVE.

*Body of backlog entry `(afc)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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

  ## NOT DECIDED

  - **Whether `path_is_usable_dir` should learn the third state**, or whether the caller should
    ask a different question - *is this the drive I recorded?* - before offering to register it.
    The catalog knows a drive with copies was last seen at this path; nothing consults that.
  - **Whether `drives --init` should refuse an empty directory that the catalog knows as a drive
    root**, independent of the message. A remedy that cannot be followed wrongly is better than a
    message that says not to.
  - **Whether writing a marker into a mountpoint should be prevented at all** - it is the step
    that makes the damage permanent rather than merely confusing.
