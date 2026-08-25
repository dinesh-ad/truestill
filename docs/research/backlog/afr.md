# (afr) THE LOCK DIRECTORY GROWS ONE EMPTY FILE PER DRIVE, FOREVER.

*Body of backlog entry `(afr)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afr)** `DriveLock.release` TRUNCATES AND NEVER UNLINKS. Found 2026-08-22 during a state check
  after `(aaw)` shipped, in the maintainer's own data directory.

  ## WHAT IS THERE

  ```
  ~/.local/share/Truestill/locks/   5 files, all 0 bytes, from one afternoon of testing
  ```

  `release` does `os.ftruncate(fd, 0)` and closes the descriptor (`drive_lock.py:208,219`).
  Nothing ever removes the file. So the directory gains **one file per distinct drive key and
  keeps it** - and because a key is `uuid:<marker>` for a marked drive and **`path:<resolved>`
  otherwise**, every destination path ever organized leaves one behind, including one-off folders
  a user will never open again.

  ## ⚠ NOTHING BREAKS, AND DELETION IS SAFE - WHICH IS WHY THIS IS A LETTER AND NOT A DEFECT

  **The flock is the truth, not the file.** An empty lock file is re-locked exactly like a
  populated one; the claim text inside it is advisory content for the refusal message and is read
  only while a holder is live. Deleting the directory while nothing is running costs nothing, and
  deleting it *while* something is running is also safe on POSIX - the holder's descriptor keeps
  its lock, and a new process creates a fresh inode and locks that. ⚠ **That last case is a real
  hole in the exclusion**, not a comfort: two processes on two inodes at one path do not exclude
  each other. It needs a user to delete the file mid-run, which is why it is recorded here rather
  than treated as the entry's subject.

  ## WHY IT NEEDS A LETTER RATHER THAN A COMMENT

  ⚠ **It was neither designed nor recorded.** `(aaw)`'s entry argues at length about where the
  lock file lives and why it is not on the drive, and about there being *"no stale lock to detect
  or clear"* - which is true **of the lock** and was silently read as true of the **file**. Nobody
  chose unbounded accumulation; it is what fell out of binding the lock to a descriptor and
  truncating on release. A comment in `drive_lock.py` would record the behaviour where only
  somebody already reading that file would find it, and the question - *should this be cleaned up,
  and by what* - is a product decision, not an implementation note.

  ## NOT DECIDED

  - **Whether to unlink on release at all.** It is one line and it reintroduces a race: unlinking
    a file another process is about to lock, or has just locked, is the hole above made routine
    rather than accidental. **The safe version is probably not "unlink on release".**
  - **Whether a sweep belongs somewhere already sweeping** - `self-check`, or the startup path
    that already reasons about the data dir - removing files not locked and older than some age.
  - **Whether it matters at all.** A 0-byte file per drive is a few hundred bytes of inode for a
    user with a handful of drives. The `path:` case is the one that grows without a ceiling, and
    the honest question is whether anyone reaches enough distinct destinations for it to show.
    **Measure before building**: nobody has counted what a real user's key set looks like.

  ## RELATED

  `(aaw)` (the lock, shipped 2026-08-22 - this is its residue), `(aeo)` (the data dir's other
  unguarded write), `(acv)` (what the repository leaves behind, a different scale of the same
  question).
