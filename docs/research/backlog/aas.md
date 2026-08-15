# (aas) An undated file cannot be assigned to an event the user knows it belongs to.

*Body of backlog entry `(aas)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aas) An undated file cannot be assigned to an event the user knows it belongs to.**
  Recorded 2026-08-02 while ruling on `(aar)`. **Post-launch. A missing convenience rather than a
  defect - nothing here is wrong, something is absent.**
  - **The gap is structural, not an oversight.** `camera_copies_for_events` selects
    `WHERE ... f.captured_at IS NOT NULL`, so Trips & events excludes undated files **by
    construction**: the one screen that could group them cannot see them. No other surface
    assigns a file to an event.
  - **The case that produces it.** A friend sends photos from a shared trip over WhatsApp. A
    normal send strips EXIF, so there is no trustworthy capture date and R1 correctly declines to
    invent one from the sent-date - the file lands in `Undated/`. **The tool is right not to
    guess. The user knows exactly where those photos belong and has no way to say so.** Declining
    to guess is correct; declining to *ask* is the gap.
  - **Scope, now that `(aar)` has shipped.** A document-mode send keeps its EXIF and is dated and
    placed from it, so it never reaches this. What is left is files with genuinely no recoverable
    date - the smaller and harder set.
  - **Shape, unruled:** it is an assignment, so it inherits the event flow's posture - a proposal
    the user confirms, never an inferred date written back as though it were evidence. Whether
    assigning an event also implies a date is the open question.
