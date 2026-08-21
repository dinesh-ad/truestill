# (aeu) ON HEIC THE PAYLOAD AND THE PIXELS DISAGREE ABOUT ORIENTATION.

*Body of backlog entry `(aeu)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aeu) `(adp)`'s DEFECT SURVIVES ON THE FORMAT MODERN PHONES USE.** Found 2026-08-21 by soak
  two, S12.

  ## MEASURED, THROUGH THE PRODUCT'S OWN FUNCTIONS

  `Issue 437 (dotnet).heic`:

  | | |
  |---|---|
  | exiftool `Orientation` | **6** (Rotate 90 CW), stored 4000x1848 |
  | `service/organize._tile_shape` -> the **payload** the grid gets | `{'w': 1848, 'h': 4000}` - **portrait** |
  | `thumbnails.render` -> the **pixels** the grid gets | `320x148` - **landscape** |

  **4 of 20** HEIC/HEIF/AVIF files disagree, every one `exiftool=6 / PIL=1`, and one of them is
  `iphone_13_pro_max.HEIC`.

  ## ROOT CAUSE - ONE RULE, TWO CALLERS, **TWO INPUTS**

  `_tile_shape`'s docstring: *"`upright_size` is imported from `thumbnails` rather than
  reimplemented here so the payload and the pixels cannot drift apart - one rule, two callers."*

  The **rule** is shared. The **input** is not. `_tile_shape` reads `tags["Orientation"]`, which
  comes from **exiftool** (6). `render` applies `ImageOps.exif_transpose`, which reads the tag
  **PIL** exposes - and for HEIF, `pillow_heif` applies the container's rotation at decode and
  presents `Orientation` as **1**, so `exif_transpose` correctly does nothing.

  Both readers are self-consistent. HEIF expresses rotation twice - the container transform and the
  EXIF tag - and they disagree about whether it has already been applied.

  ⚠ **Sharing a helper does not make two callers agree when they feed it different facts.** That is
  the lesson worth more than the fix.

  ## WHY THE ORIGINAL CORPUS COULD NOT HAVE FOUND THIS

  `(adp)` measured **31.7%** of a 4,108-photograph corpus carrying a transposing tag and fixed
  rendering for it - on JPEG. The maintainer's library is 2013-2014 and overwhelmingly JPEG. HEIC
  is the iPhone default since iOS 11, so on a modern library this is **the whole rotated class**,
  and the grid would mis-shape every one.

  ## NOT DECIDED

  - **Which reader wins.** `render`'s output is what the user sees, so the payload arguably must
    follow the pixels - but `_tile_shape` is documented as *free* precisely because it reads tags
    already in hand, and decoding to find out would cost a pass.
  - **Whether `upright_size` should take the SOURCE of the orientation** rather than the integer,
    so a caller cannot silently supply a different one.
  - **Not measured**: whether AVIF and HEIF behave as HEIC does here, and whether other
    container-transform formats (some TIFF, some RAW) split the same way.
