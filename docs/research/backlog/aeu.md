# (aeu) ON HEIC THE PAYLOAD AND THE PIXELS DISAGREE ABOUT ORIENTATION.

*Body of backlog entry `(aeu)`, **CLOSED 2026-08-21** - both halves. The closure is in [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

> ## ⚠ CORRECTIONS AND OUTCOME, 2026-08-21 - beside the finding, not into it
>
> **1. THE POPULATION WAS OVERSTATED. It is 1 of 20 drawn sideways, not 4.** The finding measured
> *tag disagreement* - exiftool 6 vs PIL 1, true of four files - and read it as four wrong
> pictures. Only **one** actually rendered sideways. The other three were correct all along, and a
> fix aimed at all four **broke them**. Measuring the proxy instead of the property is
> `ENGINEERING_STANDARD.md` §4's *"when a census measures a PROXY, ask what the proxy cannot
> distinguish"*, and this is that member catching its author.
>
> **2. THE ROOT CAUSE IS NOT "pillow_heif zeroes the tag" ALONE.** HEIF expresses rotation
> **twice**: the container property `irot`, which libheif applies while decoding, and the legacy
> EXIF `Orientation`. Apple writes both. Measured on the four:
>
> | file | `irot` | decoded | needs the tag applied |
> |---|---|---|---|
> | `Issue 437 (dotnet).heic` | absent | flat | **yes** - this is the defect |
> | `iphone_13_pro_max.HEIC` | present | already upright | no - applying it again turns it sideways |
> | `Issue 263 dotnet.heic` | present | already upright | no |
> | `Issue 487.heic` | present | already upright | no |
>
> **3. FIXED: the pixels half.** `thumbnails._pending_heif_orientation` restores the stashed
> orientation **only when EXIF's own `PixelXDimension`/`PixelYDimension` match the decoded size**,
> which is exactly the case where libheif did not transform. No container parser, no exiftool call,
> nothing the module did not already hold. All 20 HEIC/HEIF/AVIF in the corpus now render with
> payload and pixels agreeing except the one below.
>
> **4. ALSO FIXED, same session: the payload half, the MIRROR of the first.**
> `HMD_Nokia_8.3_5G.heif` carries the rotation **only** in `irot`, with EXIF `Orientation=1`.
> libheif applies it, so the **pixels are right** (portrait) - and `_tile_shape` asks exiftool,
> which reports the **stored** extent plus orientation 1 and never surfaces `irot`, so the
> **payload is wrong** (landscape). Same disagreement, opposite direction, different surface.
> exiftool **does** surface the container turn as `QuickTime:Rotation`, so `upright_size` now
> takes it and applies an **OR** - the two signals are one rotation written twice, and composing
> them would double it on every Apple HEIC. ⚠ The bare tag name collides with `[Panasonic]
> Rotation`; requesting it unqualified transposed landscape JPEGs, so it is group-qualified.
>
> **5. KNOWN GAP, pinned rather than hidden.** Orientations 2, 3 and 4 leave both dimensions
> unchanged, so the stored-vs-decoded comparison cannot tell an applied turn from a pending one -
> `(adp)`'s own blind spot, *"a 180-degree rotation leaves width and height alone"*. An EXIF-only
> HEIC turned 180 therefore still renders wrong. Asserted by
> `test_an_exif_only_heif_turned_180_is_a_known_gap`, **`xfail(strict=True)`**, so widening the
> condition turns it into a failure and whoever does it must confront the double-rotation risk.
>
> **7. AND THE FIRST FIX WAS INERT ON exiftool 12.76.** The rule read `{1, 3}` - the quarter-turn
> index 13.50 reports - while 12.76, which Ubuntu noble ships and the CI lane installs, reports
> the same tag in **degrees**. Correct on one, matching nothing on the other, silent either way.
> Now a union of both encodings, which is unambiguous because they are disjoint except at 0.
> ⚠ Caught by the three-OS matrix on a **dependency-version** difference rather than an OS one,
> and by a PRECONDITION assertion rather than an outcome: an outcome assertion cannot distinguish
> *"correctly not transposed"* from *"never consulted"*.
>
> **6. A MUTATION SURVIVED UNTIL THE CRY-WOLF TEST EXISTED.** Mutating the condition to apply the
> stash *unconditionally* killed nothing - the suite covered "never rotate" and not "rotate twice",
> which is the direction that broke the three real files. §4's thirty-first member: mutate to
> *always* and to *never*, or you have measured whichever half you picked.

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
