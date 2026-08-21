# (aev) 131 RAW LIBRARY WARNINGS REACHED THE TERMINAL, AGAINST A DOCSTRING THAT SAYS NONE EVER DO.

*Body of backlog entry `(aev)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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
