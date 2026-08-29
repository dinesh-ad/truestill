# (aie) A COPY ONTO FUSE OR VFAT WRITES THE BYTES, FAILS ON THE TIMESTAMP, AND BLAMES THE DRIVE.

*Body of backlog entry `(aie)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aie) A COPY ONTO FUSE OR VFAT WRITES THE BYTES, FAILS ON THE TIMESTAMP, AND BLAMES THE DRIVE.** Filed
  2026-08-26 (P118), read from source. `safe_copy` stages through a temporary and calls
  `shutil.copy2` (`safe_copy.py:189`); `copystat`'s `utime` is unguarded and its `chmod` catches
  only `NotImplementedError`, never `EPERM`. On a FUSE mount or a vfat stick the bytes land, the
  metadata copy raises, and the **complete** staged file is discarded. ⚠ **And the message is
  false**: `EPERM` maps to *"the drive is read-only, or this account cannot write to it"* - the
  drive was writable, and the product just proved it. The stop predicate narrows to `EROFS`, so
  the run does not halt: **one identical false line per file**, for as many files as there are.
  `moving-machines.md` documents organizing into a cloud FUSE mount and `BACKLOG.md`'s *What
  works* lists SMB/NFS/mounted-cloud, so this is a supported path, not an exotic one.

  ## THE SEQUENCE

  `safe_copy` stages through a temporary file and calls `shutil.copy2(source, temp)`
  (`safe_copy.py:189`). `copy2` is `copyfile` **then** `copystat`, and `copystat`:

  * calls `os.utime` **unguarded** - a FUSE mount that does not implement it raises `EPERM`;
  * calls `os.chmod` inside a `try` that catches **`NotImplementedError` only**, never `EPERM`.

  So on a FUSE mount or a vfat stick: the bytes are written completely, `copystat` raises, the
  exception propagates, and the **complete** staged file is discarded.

  ## ⚠ AND THE SENTENCE IS FALSE

  `EPERM` maps to *"the drive is read-only, or this account cannot write to it"*. The drive is
  **not** read-only and the account **can** write to it - the product had just finished proving
  both by writing the whole file. A user reading that line goes and checks permissions that are
  already correct.

  🔑 **And it does not stop.** The run-stopping predicate narrows to `EROFS` alone, so `EPERM`
  keeps going: **one identical false line per file**, for as many files as there are, none of them
  true. That is `(afa)`'s shape - a per-file message that should have been one refusal - slipping
  under the guard built for exactly it.

  ## THIS IS A SUPPORTED PATH, NOT AN EXOTIC ONE

  [`moving-machines.md`](../../moving-machines.md) documents organizing into a cloud FUSE mount,
  and `BACKLOG.md`'s *What works* row lists SMB, NFS and mounted cloud storage. A vfat stick is
  what a photograph arrives on.

  ## WHAT IS NOT ESTABLISHED

  Whether the right answer is `copyfile` plus a best-effort `copystat` (keeping the file, losing
  the mtime, **saying so** - never silently), or a destination probe at preflight. The first is
  smaller; the second is the shape the 4 GB preflight already established, and this product's rule
  is that a refusal belongs before the run rather than during it. **Not ruled here.** Whichever
  wins, an unpreserved mtime must be **counted and named**, never dropped - the never-silent rule,
  which is what `(ahq)` was amended for on the same day this was filed.

  ## RELATED

  `(aic)` and `(aid)`, `(abu)` (the observed defect `safe_copy` was built to close), `(afa)` (one
  refusal, not one line per file), [`moving-machines.md`](../../moving-machines.md).

  ## ⚠ WHY IT SURVIVED - THE LANES STRUCTURALLY CANNOT SEE IT

  Shared by `(aic)`, `(aid)` and `(aie)`, and it is half of why all three are still here. This is
  not *"no test covers it"*; it is *"no lane can reach the state"*. `ENGINEERING_STANDARD.md` §4's
  fifty-fourth member - an instrument silent in the case it exists for.

  | what would be needed | what the lanes have |
  |---|---|
  | a non-en-US locale | **none.** Both non-Linux runners are en-US; nothing sets `LC_ALL` or a code page |
  | a non-ASCII filename **on disk** | **zero in the whole suite.** The one Unicode fixture is lexical - a string in a test, never a file |
  | a path near 260 characters | CI paths never approach it |
  | exFAT, FAT32, FUSE, SMB or NFS | **none.** No lane touches any filesystem but the runner's own boot volume - *which is the product's entire subject matter* |
  | an older exiftool | one version, whatever the image ships |
  | scale | small fixtures only |

  ⚠ **`architecture-excellence-2026-audit.md:198-200` already said this** about the lock design
  pass: the filesystems the product exists to write to are the ones nothing runs on. It is advisory
  and no implementation was authorized; this is the same gap arriving from a different direction.

  ⚠ **ALREADY GUARDED, so none of this is re-filed**: the 4 GB preflight, exFAT permission
  handling, reserved device names for **typed** values, timezone handling, WAL-is-moot, stale
  locks, and a missing exiftool. The three entries are the complement of that list, not a claim
  it is empty.

  ## ⚠ REPRODUCED 2026-08-29 (P140) - EVERY CLAUSE HOLDS

  ⚠ **The environment was NOT staged, and that distinction is the honest part.** No FUSE or vfat
  mount is reachable on this machine: `bindfs` and `mount.cifs` are absent, no Python FUSE binding
  is installed (`fuse`/`pyfuse3`/`fusepy` all absent), and adding one is a dependency this does not
  earn. So the **errno was injected at the exact syscall a network mount refuses** - `os.utime`
  raising `EPERM` - and the run was real: real files, real organize, real destination.

  **What the user sees, verbatim, for three files:**

  ```
  FAILED: IMG_0000.jpg: could not copy IMG_0000.jpg to
  'Saved/2019/2019-07/20190711_103000_IMG_0000.jpg': the drive is read-only, or this account
  cannot write to it
  FAILED: IMG_0001.jpg: ... (identical)
  FAILED: IMG_0002.jpg: ... (identical)
  ```

  | claim | measured |
  |---|---|
  | one identical false line per file | ✅ **3 files, 3 identical lines** |
  | the message is false | ✅ **the destination accepted a write immediately afterwards** - the drive was writable throughout |
  | the run does not stop | ✅ all three processed, `3 failed` at the end, exit 1 |
  | the complete staged file is discarded | ✅ **0 files landed**, and 0 `.partial` debris - the cleanup is correct, the discard is the defect |

  ⚠ **One thing found that this entry did not name**: `SUMMARY` reports *"organized (unique): 3"*
  while `EXECUTED` reports *"3 failed"*. The summary describes the plan and the executed block
  describes reality, so a reader who stops at the summary sees three files organized that are not
  there.
