# (aco) A STILL WHOSE CAMERA WROTE UTC INTO `DateTimeOriginal` LANDS ON THE WRONG DAY.

*Body of backlog entry `(aco)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aco) A STILL WHOSE CAMERA WROTE UTC INTO `DateTimeOriginal` LANDS ON THE WRONG DAY.**
  Recorded 2026-08-10, measured in P41. Fixture: `DateTimeOriginal = 2026:07:31 20:30:00Z`,
  taken in India. 20:30 UTC is 02:00 IST on 1 August, so the photo belongs in `2026-08` and
  lands in **`2026/2026-07/`**. One of six midnight fixtures; the other five are correct.
  - **Why it is the only wrong one.** `parse_exif_datetime` strips `Z` and any `±HH:MM` and
    keeps the digits as local wall clock. That is right for every camera that writes local time -
    which is what the tag means - and wrong only for one that writes UTC into it.
  - ⚠ **A fix is not obvious, and this is the substance of the entry: knowing the stamp is UTC
    does not tell us where the camera was.** Converting needs a local zone, and there are only
    three sources for one, each with a real cost:
    - **GPS** - present on 3.6% of this library, and drags in `(acp)`'s historical-rule problem.
    - **A user-supplied zone** - the `--tz` flag already exists for Takeout, and could apply
      here. Honest, but it asks the user a question they may not be able to answer for a photo
      taken years ago on a trip.
    - **Refusal** - send it to `Undated/` and say why. Loses a date we partly have.
  - **The argument for doing nothing:** the digits are only wrong by the shooter's offset, so
    the photo is at most one day out and usually in the right month. `Undated/` is worse for a
    user than a date that is one day off, and the current behaviour is silently *right* for the
    far commoner camera.
  - **The argument against:** it is silent. The user is never told the stamp was UTC-marked,
    which is exactly the "wrong folder, no explanation" shape. **Reporting it costs nothing and
    is separable from correcting it** - the date-provenance view could say *"this file's time is
    marked UTC and was read as local"* without any zone lookup at all. That is probably the
    cheapest honest move and it is not a fix.
  - ⚠ **`OffsetTimeOriginal` does NOT solve this, and the claim that it would was wrong.**
    Measured across both public corpora, **1,434 stills**: only **25 (1.7%)** carry
    `OffsetTimeOriginal` at all, and in every observed case it **confirms what Truestill already
    assumes** - the digits are local - so placement is unchanged. Of the four UTC-marked stills
    found, the one that could be inspected (`exif-samples/jpg/tests/30-type_error.jpg`, a
    deliberately malformed test file) carries **no `OffsetTimeOriginal` at all**. The tag is
    EXIF 2.31 (2016); a camera broken enough to put UTC in `DateTimeOriginal` is not one that
    implements it. **Reading it would change placement in zero observed cases** - it is
    diagnostic only, and absent in precisely the case a diagnosis would help.
