# (acn) DOES A GPS FIX TIME COUNT AS CAPTURE EVIDENCE? A RULING, NOT A BUG.

*Body of backlog entry `(acn)`, under **Rulings - decided, no work attached**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(acn) DOES A GPS FIX TIME COUNT AS CAPTURE EVIDENCE? A RULING, NOT A BUG.** Recorded
  2026-08-10 from the independent corpus measurement (`format-coverage-audit.md` §0). Three files
  carry `GPSDateStamp` + `GPSTimeStamp` and **no capture tag at all**, so they land in `Undated`
  while holding a satellite-stamped time. **Truestill already reads both tags** - nothing needs
  building to obtain them, which is why this is a question about what the product will assert
  rather than an extension list. Left open deliberately; the maintainer rules.
  - **For:** a GPS fix is **contemporaneous with the exposure** - the receiver stamped it while
    the photographer stood there. It is strictly better evidence than a filename convention,
    which `(kk)` already accepts and flags for review. And `Undated/` is not free: it is the bin
    a user must sort by hand.
  - **Against:** it is **not the camera's own claim about the photo**. Every other accepted source
    is the device asserting when it made this image; a GPS timestamp asserts when the *receiver*
    had a fix, which can precede or outlast the shutter, and on some devices is a cached
    almanac rather than a live fix. Truestill's promise is that a date is evidence, never a
    guess, and the line between the two is what this decides.
  - **Where it belongs:** with the date-provenance program, beside `(aax)` (`time_known` derived
    from provenance) - it would need its own `date_source` value so the honesty view can say
    *"from the GPS fix"* rather than laundering it into "from the file".
  - ⚠ **Also unresolved: GPS time is UTC.** Adopting it means choosing a local wall clock, which
    is the same problem the video UTC ladder (`(uu)`) exists for. Do not adopt one without the
    other.
