# (aco) A STILL WHOSE CAMERA WROTE UTC INTO `DateTimeOriginal` LANDS ON THE WRONG DAY.

*⚠ **RETIRED 2026-08-24 - this is a RECORD, not an open entry.** `(aco)` is no longer in
[`BACKLOG.md`](../../BACKLOG.md)'s open list and is deliberately **not** in
[`SHIPPED.md`](../../SHIPPED.md): nothing was built, and a shipped row would credit a fix nobody
made (the `(ags)` precedent; `scripts/check_entry_closure.py` enforces the distinction). The letter
is named with its reason in `BACKLOG.md`'s* Item letters *section. **Kept and linked rather than
deleted**, because the measurements below are the evidence for the retirement - deleting them would
delete the argument. **Do not edit it to stay correct**; the header is what a record gets.*

> ## ⚠ RETIRED 2026-08-24 (P50) - the population cannot be produced
>
> **The premise holds and the population does not.** Two independent censuses of both format
> corpora - 1,434 stills - found **no camera with a Make and Model that writes UTC into
> `DateTimeOriginal`**:
>
> - **By tag text** (this entry's own method, re-run): **six** files carry a UTC/offset marker, not
>   the four recorded below. Four have **no Make and no Model** - synthetic and issue-report files.
>   The two that are real cameras (`FLIR Vue Pro 640.jpg`, `FLIR iPhone device.jpg`) declare a
>   **non-zero** offset, which is local-time-plus-zone and **not this defect at all**.
> - **By GPS comparison** (a method this entry did not run, and the only one that can see a
>   *silent* UTC writer): 37 stills carry both `DateTimeOriginal` and GPS UTC. Three sit at exactly
>   0.00 - and coordinates place all three in **London and Cardiff in winter**: iPhone 6 Plus
>   2014-10-31, Galaxy Note 4 2014-12-18, Galaxy Note 8 2018-03-17. **Genuinely GMT.** A photo
>   taken in a UTC+0 zone is indistinguishable from one whose camera wrote UTC, and the corpora
>   hold only the former.
>
> **And every proposed fix was worse than the defect.** Of those 37 comparable stills, **14 (38%)
> have a `DateTimeOriginal - GPS` delta that is not a real UTC offset** - nine NIKON COOLPIX P6000
> files at **-21.97h**, a Nexus 4 at +27.07h. The GPS bullet below calls GPS rare; the sharper
> objection is that it is **wrong 14 times in 37**, and a rule deriving a zone from it would have
> moved nine photographs by twenty-two hours - the wrong day, which is the harm this entry exists
> to prevent.
>
> ## 🔑 THE DOUBLE GATE - worth more than the retirement
>
> **A fix aimed at `dates.py:370`'s `is_video` alone would have done nothing while looking
> correct.** The line is:
>
> ```python
> if embedded.tag in UTC_CONTAINER_TAGS and is_video(path, metadata):
> ```
>
> and **`UTC_CONTAINER_TAGS` (`video_utc.py:21`) holds only `CreateDate`, `MediaCreateDate` and
> `TrackCreateDate`** - `DateTimeOriginal` is not a member. So the still is excluded **twice**, and
> the second exclusion is invisible to anyone who reads the conjunct they were told about.
>
> ⚠ **That is this week's defect class sitting inside a PROPOSED fix rather than a shipped one** -
> a guard that resolves and does nothing, met before it was written. It was found by the
> sixty-ninth member: read to the last thing that can change the answer, rather than stopping at
> the gate somebody named.
>
> ⚠ **What the retirement does NOT claim:** that no camera anywhere does this. It claims the entry
> rested on a population neither the corpora nor the field can produce, and that every fix it
> proposed costs more than the defect.
>
> **REOPEN CONDITION, structural rather than dated:** a real file - with a Make and a Model - whose
> `DateTimeOriginal` is UTC and which carries **no** offset tag. That is the shape no census has
> found, and it is what would restore the population.
>
> ➡ **The live evidence found on the way is `(agz)`**, filed separately rather than recorded here,
> because burying it in a withdrawn entry means the next reader meets a retirement and stops.

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
