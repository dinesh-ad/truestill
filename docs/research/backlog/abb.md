# (abb) The other capture-filename conventions.

*Body of backlog entry `(abb)`, under **Real, but conditional**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abb) The other capture-filename conventions.** Recorded 2026-08-03, when
  `rule_camera_filename` shipped with **one** pattern: Android's `IMG_`/`VID_` plus a full date
  and time, verified against the AOSP Camera commits that introduced it. Deliberately scoped to
  the convention the real library actually held.
  - **What is not covered, and why each is a separate decision rather than more regex.**
    `PANO_`, `MVIMG_` (Google Motion Photo) and `TRIM_`/`VID_TRIM_` share the date-and-time
    shape and are plausibly the same rule. `IMG_1234.JPG` (iPhone, Canon), `DSC_2286.JPG`
    (Nikon, Sony) and `P1010101.JPG` (Panasonic, Olympus) are **not**: they are counters, they
    carry no capture record, and a rule claiming them would put every unlabelled file with a
    camera-ish prefix onto someone's timeline on the strength of three letters. That is the
    cry-wolf `test_camera_filename_convention.py` already pins against, so widening this needs
    an argument, not an entry.
  - **What would make the counter conventions safe** is a second signal - a plausible capture
    date from somewhere, or sibling files sharing the convention in one folder - which is a
    different rule shape from a filename table and should not be smuggled into one.
  - **Cost of being wrong is asymmetric and worth restating**: a file wrongly left in `Saved/`
    is findable, and a file wrongly placed among the owner's own photos is not.

Everything here has work left. **Two entries are partial and say so in their own text:**
`(bbb)` (the safety half shipped, the `_original` recovery offer did not) and `(r)` (the hash
cache shipped, Analyze mode itself did not). A partial entry lives here, not in the built
section, because what is left is the part that still has to be written.
