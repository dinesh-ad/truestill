# (aid) THE ORIGINAL FILENAME IS NEVER SANITIZED, AND THEN GAINS SIXTEEN CHARACTERS.

*Body of backlog entry `(aid)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aid) THE ORIGINAL FILENAME IS NEVER SANITIZED, AND THEN GAINS SIXTEEN CHARACTERS.** Filed
  2026-08-26 (P118), read from source. `layout.py`'s four defences - illegal characters, reserved
  device names, trailing dots, the 255-byte cap - apply to **token values only** (the event name,
  the category), which `filename-safety-research.md` scopes correctly as *"user-supplied names"*.
  But `dated_filename` returns `f"{stamp}_{original_name}"` untouched (`naming.py:104`).
  `Trip: day 1.jpg` and `nul.jpg` are legal on ext4 and **refuse on NTFS**; a 248-byte name
  becomes 264 and refuses everywhere. ⚠ **`PATH_LENGTH_WARN` exists (`layout.py:99`) and organize
  never imports it** - the two readers are `layout.py:517` and `migrate.py:623`, so the one screen
  that warns about length is the settings preview, where nothing is being moved.
  `ENAMETOOLONG` and `EINVAL` are not in the errno table, so what the user gets is raw OS words.

  ## WHAT IS DEFENDED AND WHAT IS NOT

  `layout.py` carries four defences and they are good ones - illegal characters, reserved device
  names, trailing dots, a 255-byte cap. **All four apply to token values**: the event name, the
  trip name, the category. [`filename-safety-research.md`](../../filename-safety-research.md)
  scopes itself to *"user-supplied names"* and is **correct about its own subject**.

  The file's own name is not a token. `dated_filename` returns `f"{stamp}_{original_name}"`
  (`naming.py:104`) with `original_name` passed through untouched, and `stamp` adds **sixteen
  characters** in front of it.

  ## WHAT BREAKS, AND ALL OF IT IS LEGAL ON THE SOURCE

  | source name | legal on ext4 | destination |
  |---|---|---|
  | `Trip: day 1.jpg` | yes | `:` is illegal on NTFS - **refuses** |
  | `nul.jpg` | yes | reserved device name on Windows - **refuses** |
  | a 248-byte name | yes | 264 after the stamp - **refuses everywhere** |
  | `photo?.jpg`, `a*b.jpg` | yes | illegal on NTFS and exFAT |

  ⚠ **A user copying a library from a Mac or a Linux box onto an external NTFS drive is the
  ordinary case**, not a contrived one - and it is `moving-machines.md`'s subject.

  ## ⚠ THE WARNING EXISTS AND ORGANIZE DOES NOT IMPORT IT

  `PATH_LENGTH_WARN = 200` (`layout.py:99`) has exactly two readers: `layout.py:517` and
  `migrate.py:623`. **`organizer.py` imports neither the constant nor anything that checks it.**
  So the one screen that warns about path length is the settings preview, where nothing is being
  moved, and the run that actually writes says nothing until the OS refuses.

  `ENAMETOOLONG` and `EINVAL` are absent from the errno table, so the refusal arrives as raw OS
  words with no next step - against `ENGINEERING_STANDARD.md` §4's rule that naming a problem
  without a remedy is half a report.

  ## WHAT IS NOT ESTABLISHED

  Whether to sanitize the original name (changing what the file is called, which a user may
  reasonably object to) or to **refuse in the preview with a named remedy** (leaving the name
  alone and making the problem visible before anything is written). The second is cheaper and
  loses nothing; it is not obviously right, and this entry does not rule.

  ## RELATED

  `(aic)` and `(aie)`, [`filename-safety-research.md`](../../filename-safety-research.md) (correct
  about tokens, silent about this), [`moving-machines.md`](../../moving-machines.md).

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
