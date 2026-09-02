# (ll) Sub-day event identity that survives a changing file set.

*Body of backlog entry `(ll)`, under **Real, but conditional**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ll) Sub-day event identity that survives a changing file set.** The day-event half of the
  identity defect recorded in `trip-grouping-research.md` §6.
  - **The defect.** `EventCandidate.signature` (`events.py:EventCandidate.signature`) is a SHA-256 over the member
    `sha256`s, and that is the `UNIQUE` key `event_by_signature` looks up. Membership *is*
    identity, so ingesting one more photo from an already-named day changes the signature and the
    event is proposed again as new, with the name already given orphaned.
  - **The trip fix does NOT apply here, and this is the point of the entry.** Trips are keyed on
    `trip_days.day` because a day belongs to at most one trip. **Day events are not days.**
    2014-08-16 alone produced two clusters (565 and 157 files) and 2014-08-17 produced three;
    keying on the date would collapse a morning outing and an evening one into one identity and
    silently merge two separately-named events. **Do not apply the day-key remedy to events.**
  - **What is needed instead:** an identity stable under a changing file set that still separates
    several events within one day - a time-anchored key (day plus cluster start, tolerance
    matched) is the obvious candidate and needs its own design pass and its own evidence.

- **Recognize additional real-world video extensions (l).** The metadata-chain corpus surfaced
  container formats truestill's `MEDIA_EXTENSIONS` doesn't recognize, so they are skipped (now
  *reported*, not silent). Recognize the ones that are actually common - **`.vob`, `.ts`, `.m2v`,
  and the `.asf` family at minimum** - with the final list driven by **prevalence evidence, not
  the whole corpus zoo** (`.swf`, raw `.hevc`/`.mjpeg` elementary streams are not "photos to back
  up"). Each extension added must have its **category and date handling verified via the corpus
  probe** before inclusion. **Post-launch, demand-driven.**
