# (aic) EXIFTOOL'S OUTPUT IS DECODED WITH THE MACHINE'S CODE PAGE, SO A NON-ASCII FILENAME LANDS IN `Undated/`.

*Body of backlog entry `(aic)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aic) EXIFTOOL'S OUTPUT IS DECODED WITH THE MACHINE'S CODE PAGE, SO A NON-ASCII FILENAME LANDS IN `Undated/`.** Filed
  2026-08-26 (P118), read from source. Every text-mode subprocess in the workspace passes
  `text=True` with **no `encoding=`**, so Python decodes with `locale.getpreferredencoding()` -
  **cp1252 on Windows**, the platform D9 launches on. 🔑 **The INPUT side is armoured and the
  OUTPUT side is not**: `_read_chunk` passes `-charset filename=utf8` (`exif.py:315`) and then
  reads the reply at `exif.py:320` with no encoding at all. A mojibaked `SourceFile` misses
  `by_name` (`exif.py:340`), falls through to `or Path(source)` - **a path that does not exist** -
  so `metadata.get(path, {})` returns `{}` and a correctly-dated photograph takes the handling
  designed for an unreadable one: **`Undated/`**. Silent, and wrong in the direction that looks
  like the product failing at its one job. ⚠ **This repo already knows the rule and applied it
  everywhere else**: three test files carry the comment *"`encoding="utf-8"` IS LOAD-BEARING …
  Windows defaults to cp1252"*, aimed at file reads. **Subprocess is the one seam that was
  missed.** **Four call sites, one home**: `exif.py:270`, `exif.py:320`, `selfcheck.py:169`,
  `destinations/rclone.py:49` - and `binaries.run`/`binaries.popen` is the single door all
  subprocess traffic goes through, so the fix is there, not at four call sites.

  ## THE PATH, STEP BY STEP

  1. `_read_chunk` builds `[binary, "-json", "-q", "-m", "-charset", "filename=utf8", ...]`
     (`exif.py:315`) - **the input is armoured**, deliberately and correctly.
  2. It runs `binaries.run(args, capture_output=True, text=True, check=False)` (`exif.py:320`).
     `text=True` with no `encoding=` means `locale.getpreferredencoding(False)`.
  3. exiftool emits UTF-8 JSON. On a cp1252 machine, `Réunion.jpg` comes back as `RÃ©union.jpg`.
  4. `_merge_batch` builds `by_name = {str(path): path for path in chunk}` from the **real** paths
     (`exif.py:340`). The mojibaked `SourceFile` is not a key.
  5. `path = by_name.get(source) or Path(source)` - the fallback constructs a path **that does not
     exist on disk**, and `collected` is keyed by it.
  6. The caller asks `metadata.get(real_path, {})` and gets `{}`.
  7. No `DateTimeOriginal`, no GPS, no camera. The file is dated `DateSource.NONE` and filed
     **`Undated/`**, next to the photographs that genuinely have no date.

  🔑 **The failure mode is the worst available one.** Not a crash, not a refusal, not a warning:
  a correct photograph quietly filed as undatable, in a batch, while its ASCII-named neighbours
  from the same camera file correctly. *"It filed my whole 'Réunion 2019' folder under Undated.
  The ones in 'Beach 2019' are fine."*

  ## THE CENSUS - FOUR CALL SITES, ONE DOOR

  | site | what it reads | exposure |
  |---|---|---|
  | `exif.py:320` | exiftool JSON for a batch of photos | **the one that misfiles** |
  | `exif.py:270` | exiftool's reply to an argfile write | the bake path |
  | `selfcheck.py:169` | `exiftool -ver` | ASCII in practice; same class |
  | `destinations/rclone.py:49` | rclone output, which carries paths | same class |

  🔑 **`binaries.run` and `binaries.popen` are the single door every subprocess goes through** -
  that is what the module exists for - so the fix has one home and four call sites need no edit.
  Defaulting `encoding` to UTF-8 whenever text mode is requested is the shape; whether to pair it
  with an `errors=` policy is the open question, because **silently substituting characters would
  reintroduce the same class of loss one layer down**.

  ## WHAT IS NOT ESTABLISHED

  Whether exiftool's `-charset` has an **output** counterpart worth setting as well, and what
  should happen when a filename genuinely cannot round-trip. Neither is needed to rule that
  `text=True` without `encoding=` is wrong; both are needed before the fix is complete.

  ## RELATED

  `(aid)` and `(aie)` (filed the same day, same blind spot below), `(abf)` (dates the user can
  see are wrong), [`takeout-format.md`](../../takeout-format.md).

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
