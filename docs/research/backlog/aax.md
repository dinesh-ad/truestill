# (aax) `time_known` is derived from provenance, not from the value. POST-LAUNCH.

*Body of backlog entry `(aax)`, under **Records - evidence, explicitly not work**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aax) `time_known` is derived from provenance, not from the value. POST-LAUNCH.** Filed
  2026-08-03 while fixing the stacked date prefix, which this shape is what made possible.
  **Record only - do not build.**
  - **The shape.** `organizer.py:plan` sets `time_known=date_source in (EXIF, INFERRED_LOCAL)`.
    That asks *where did this date come from*, and then uses the answer for *does this date
    have a time*. **Precision is a property of the value; trust is a property of the source**,
    and deriving one from the other is the defect - the two questions have different answers.
  - **Where they already disagree.** `TAKEOUT` is in `_TRUSTED_DATE_SOURCES` (`models.py:DateSource`),
    so a Google `photoTakenTime` is trusted enough to file by without review - yet it is
    **not** in the `time_known` pair, so the copy is named date-only. `photoTakenTime` is a
    real capture instant with a time in it. The time is discarded for no stated reason, and
    `dated_filename`'s own justification ("embedded metadata" vs "filename-derived") describes
    a distinction Takeout falls between and no longer matches either side of.
  - **It is what made the stacking bug reachable.** A Takeout or filename-dated file gets the
    short name; the same content organized again once EXIF is readable derives the long stamp,
    and before 2026-08-03 that stacked. The anchored-prefix fix closes the *symptom* on every
    path. This entry is the *cause*, and closing it would have prevented the class.
  - **Why post-launch and not now.** Changing `time_known` changes the **names of organized
    copies** for every Takeout-sourced file, which is a migration question (existing libraries
    keep their names; new ones would differ) rather than a bug fix. It also needs a ruling on
    whether `TAKEOUT_UPLOAD` - an upload time, genuinely not a capture time - should be
    date-only for the opposite reason: its value has a time and its *meaning* does not.
  - **The shape to aim at, not a design:** resolve a date to a value that knows its own
    precision, so naming asks the value and review asks the source. Do not smuggle this into a
    naming change.
