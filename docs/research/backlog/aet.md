# (aet) ONE UNDECODABLE FILE ABORTS THE WHOLE RUN WITH A TRACEBACK.

*Body of backlog entry `(aet)`, **CLOSED 2026-08-21**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aet) `perceptual_hash` LETS TWO EXCEPTION CLASSES ESCAPE.** Found 2026-08-21 by soak two, S12 -
  the format-variety step, and **unreachable by any corpus of one person's devices**.

  ## MEASURED

  `organize` over 1,428 media files from `exif-samples` + `metadata-extractor-images`: **exit 1, a
  full traceback, nothing organized, no summary.**

  ```
  scan.py:119 _hash_one -> hashing.py:105 perceptual_hash -> imagehash.dhash
    -> PIL Image.convert -> pillow_heif load
  EOFError: Decoder plugin generated an error: Unexpected end of file
  ```

  Swept the whole corpus for what escapes:

  | outcome | count |
  |---|---|
  | hashed | 915 |
  | returned `None` (declined cleanly - correct) | 505 |
  | **escaped as an exception** | **8** |
  |   `SyntaxError` - malformed PNG `zTXt` chunk | 7 |
  |   `EOFError` - truncated HEIC | 1 |

  **Any one of the 8 aborts the entire run.** Quarantining exactly those 8 made the same command
  exit 0 and organize 1,398 files - so they were the only blockers, and the failure is per-file.

  ## ROOT CAUSE

  `hashing.perceptual_hash` catches
  `(UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError)`.
  **`EOFError` and `SyntaxError` are neither `OSError` nor `ValueError`** - both are direct
  `Exception` subclasses - so both escape. `scan._hash_one` catches only `OSError`.

  The docstring says *"Videos, audio and **unreadable files** return `None`"*. A truncated HEIC is
  an unreadable file and does not return `None`.

  ⚠ **`SyntaxError` is the one nobody would predict**: PIL raises the *builtin* for malformed image
  structure. That is exactly why a curated format corpus finds this and a list of exceptions
  someone thought of does not.

  ## THE RULE IT BREAKS

  §1 **Errors**: *"Partial-failure policy: one bad file never aborts a batch - it is logged,
  counted, and reported at the end."* And §4's *"exceptions typed and specific"* has a mirror
  failure - a typed `except` that is too **narrow** - which this is.

  ## DECIDED 2026-08-21

  - **Inverted, not widened**, and the argument is above: a boundary defined by enumeration is not
    one. `except Exception` at that one call, argued in place per §5, with `BaseException`
    deliberately excluded so Ctrl-C keeps working. The escaped file is reported as
    `UnreadableReason.UNDECODABLE` - its own reason, because *"could not be opened"* is false about
    a file whose bytes read perfectly.

  ## WHAT WAS NOT DECIDED, AS FILED

  - **Whether to widen the tuple or invert it.** Widening keeps the typed-except discipline and
    will be wrong again for the next decoder. Catching `Exception` at this one call site is the
    shape §1's partial-failure policy actually asks for, and would need a stated exemption from
    the no-bare-except rule rather than a quiet one.
  - **Whether an escaped decode should be reported as `unreadable`** - it currently cannot be,
    because it never reaches `models.UnreadableReason`. The run reported `could not be read: 0`
    while 8 files could not be read.
