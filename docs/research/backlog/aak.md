# (aak) The skipped-file summary is written twice.

*Body of entry `(aak)`. **CLOSED 2026-08-04 by `c027dd3`, recorded 2026-08-22.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ⚠ **THE DUPLICATION DESCRIBED BELOW WAS REMOVED ON 2026-08-04** by `c027dd3`, which replaced
> `_skipped_summary`'s copied body with `return skipped_extension_counts(scan)`. The docstring has
> stated that in place ever since - *"A thin alias, deliberately not a second implementation"* - so
> the code and this entry disagreed for eighteen days. ⚠ **Closed as a side effect of a feature
> commit**, which names no letter, so the `Closes (xyz)` rule could not see it. Original below.

- **(aak) The skipped-file summary is written twice.** `organizer._skipped_extension_counts`
  and `service/organize._skipped_summary` are the same logic in two homes - extension counts
  plus the plain exiftool-backup label. **Pre-existing; found while building `(aac)`**, which
  had to thread one new field through both. The companion rule (`ENGINEERING_STANDARD.md` §4)
  says prefer deleting a copy to guarding two, so the fix is one shared helper in core that the
  app calls, not a parity test over the pair. Small, and worth doing the next time either is
  touched rather than as its own errand.
