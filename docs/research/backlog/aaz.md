# (aaz) `ModifyDate < DateTimeOriginal` as a back-dating signal. RECORD ONLY - do not build.

*Body of backlog entry `(aaz)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aaz) `ModifyDate < DateTimeOriginal` as a back-dating signal. RECORD ONLY - do not build.**
  Filed 2026-08-03 alongside the future-date refusal, which found its case on the real library.
  - **The signal.** A file cannot logically be modified before it was created, so
    `ModifyDate` earlier than `DateTimeOriginal` is characteristic of a date that was edited
    after the fact. It would catch back-dating, which the future check cannot: a date moved
    *backwards* is not impossible, merely wrong.
  - **`ModifyDate` is NOT in `REQUESTED_TAGS` today** (checked, not assumed), so this is not
    free. Adding it changes `tags_fingerprint`, which invalidates every cached metadata row and
    forces one cold exiftool pass over the whole library - the same cost profile recorded for
    `GPSAltitude`. That is the reason this is filed rather than built.
  - **And the signal is weaker than it looks.** Any lossless rewrite - our own metadata bake
    included - updates `ModifyDate`, so a true positive and an ordinary edit are the same
    shape. It would need to be reported as a question, never as a verdict.
