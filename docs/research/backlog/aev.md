# (aev) 131 RAW LIBRARY WARNINGS REACHED THE TERMINAL, AGAINST A DOCSTRING THAT SAYS NONE EVER DO.

*Body of backlog entry `(aev)`, **CLOSED 2026-08-21**. The closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ⚠ CORRECTIONS, 2026-08-21 - beside the finding rather than into it
>
> **1. THE SUBJECT WAS BACKWARDS.** The warnings are not the defect; they are a **lossy 15%
> proxy** for one. Measured on the same corpus, scoped to what the product organizes:
>
> | | |
> |---|---|
> | image-extension files that produced **no perceptual hash** - no near-duplicate check | **478** |
> | of those, that emitted **any** warning | **71** |
> | of those, **silent today** | **407** |
> | files that warned and hashed perfectly well - no consequence at all | **14** |
>
> Reporting the warnings would have named 71 of 478 and implied the other 407 were fine.
> Suppressing them without reporting the gap would have made the product **quieter about it**.
> §4's forty-second member: a check measuring the cheaper proxy. What ships is derived from the
> decode **outcome** - `organizer.uncompared_photos` - and never from whether a library spoke.
>
> **2. THE C-LEVEL HALF IS ~598 LINES, NOT ONE.** The entry records *"plus a bare
> `OJPEGWriteHeaderInfo` line, which is not even a Python warning"*. Measured: **866 stderr lines
> in one run, of which ~598 are libtiff/libjpeg** - 377 `Fax3Decode2D: Bad code word`, 82
> `Uncompressed data (not supported)`, plus `Bogus Huffman table definition`. **4.5x the noise of
> the thing the entry is named for**, and no `warnings` filter reaches any of it.
>
> **3. THE FOUR "KINDS" ARE THREE SITES, AND ONE IS 94%.** 186 of 197 come from
> `PIL/TiffImagePlugin.py:950` - `except OSError as msg: warnings.warn(str(msg))` - which
> re-emits an `OSError`'s *message* as a bare `UserWarning`. Both *"Truncated File Read"* and
> *"Corrupt EXIF data"* are that one line. The remainder: 7 at `TiffImagePlugin.py:760`, 4 at
> `Image.py:1136`. **Every one is a bare `UserWarning` with no subclass**, so there is no category
> to filter on - only module or message.
>
> **4. THE EXISTING SUPPRESSION WAS UNSOUND, WHICH THE ENTRY DOES NOT MENTION.** It used
> `warnings.catch_warnings`, which assigns process-global module attributes, inside a function
> that runs on a `ThreadPoolExecutor` **by default** (`scan.py` `pool="thread"`). CPython
> documents that as *"the behavior is undefined"*. So *"where the filter goes"* - listed under
> **NOT DECIDED** - had no correct answer in that form: widening it would have widened a race.
>
> **5. AND THE COUNT THE RUN NOW REPORTS IS 189, NOT 133.** `warn_explicit` consults
> `__warningregistry__` **before** dispatching, so the default action drops repeats: 197 raised,
> 133 printed. The fix filters `"always"` so nothing is hidden from the counter, and the number a
> user sees is the true one.
>
> **6. `(aew)` WAS FOUND HERE AND FIXED IN THE SAME COMMIT.** The `Files that could not be read`
> block printed *"fix the permission or check the disk"* under all five reasons, and on this
> corpus **8 of 8** named files were `UNDECODABLE`, where neither is at fault - under a heading
> that contradicted its own rows.

- **(aev) PILLOW'S WARNINGS ARE THE PRODUCT'S OUTPUT.** Found 2026-08-21 by soak two, S12.

  ## MEASURED

  One `organize` over the format corpus put **131 `UserWarning` lines** on the user's stderr:

  | warning | count |
  |---|---|
  | `Truncated File Read` | 109 |
  | `Corrupt EXIF data. Expecting to read 2 bytes but only got 0.` | 9 |
  | `Metadata Warning` | 7 |
  | `Palette images with Transparency expressed in bytes should be converted to RGBA images` | 4 |

  plus a bare `OJPEGWriteHeaderInfo: jpeg_start_decompress() returned image_width = 1205, expected
  1216.` from libtiff, which is not even a Python warning.

  ## ⚠ THE DOCSTRING CLAIMS THE OPPOSITE

  `hashing.perceptual_hash`: *"The decompression-bomb **warning** is suppressed locally so **no raw
  Pillow warning ever reaches the user's terminal**."*

  The suppression is `warnings.simplefilter("ignore", Image.DecompressionBombWarning)` - **one
  class**. Every other Pillow `UserWarning` passes straight through. The sentence was true of the
  warning it was written about and false as a general claim, and nothing can falsify a docstring
  (§4's last member: *a docstring is a claim no test can falsify, so it rots silently while
  everything stays green*).

  ## WHY IT IS A DEFECT AND NOT UNTIDINESS

  §9 rules that no backend vocabulary and no raw `errno` reaches a user, and `models.unreadable_label`
  exists so *"no `errno` name or raw enum value ever reaches a user"*. `Palette images with
  Transparency expressed in bytes should be converted to RGBA images` is advice to a **programmer
  using Pillow**, addressed to somebody who is not there. It is also interleaved with the progress
  output, so it makes a working run look broken.

  ## NOT DECIDED

  - **Suppress or surface.** `Truncated File Read` is real information about the user's file and
    arguably belongs in the unreadable report **in our words**; `Palette images...` belongs
    nowhere. Blanket suppression would discard the first with the second.
  - **Where the filter goes.** Widening the existing `catch_warnings` covers the perceptual path
    only; `render` and `read_metadata` decode too.
  - The libtiff line is written to fd 2 by C code and no Python `warnings` filter reaches it.
