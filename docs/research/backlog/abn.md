# (abn) rescan, beyond the report. `truestill rescan` REPORTS; nothing acts on it yet.

*Body of backlog entry `(abn)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abn) rescan, beyond the report. `truestill rescan` REPORTS; nothing acts on it yet.**
  Recorded 2026-08-07 with the report-only slice. The design note this carries was ruled by the
  maintainer against external evidence: Lightroom's *Synchronize Folder* has been broken since
  LR 6, its 2025 expert advice is "don't use it", and its damage case - a folder capitalisation
  mismatch showing the same images as both missing **and** new, losing all metadata and edits on
  confirm - comes from conflating two operations in one dialog.
  - **THREE CLASSES, not two, and this belongs in `IMPLEMENTATION_STANDARDS.md` when the
    corrective one is built.** *Additive* (new content -> new rows) is safe by construction.
    *Corrective* (known content, wrong recorded path -> `Catalog.relocate_copy`) **overwrites a
    recorded fact**, and is safe **because its evidence is a content hash and not a path** -
    weaken that to name-and-size and the corrective class silently becomes destructive.
    *Destructive* (remove a record) is never automatic.
  - **MEASURED, so the need is not theoretical.** A hand-moved file reaches
    `service/drives.py` line 363 with `sha in attached`: it is hashed, then counted in **no**
    bucket - `attach_drive` returns `linked=0, unmatched=0, unreadable=0, absent=0` about a drive
    whose record names a path with nothing at it. `verify` then calls the same file `MISSING`
    (`(aba)` symptom 1). Detection costs one branch; only the reporting and the repair are new.
  - **THE PROVENANCE-LOSS FINDING, which is our analogue of Lightroom's.**
    `Catalog.forget_organized` drops the copy row and then, when no copy of that content remains
    anywhere, runs `DELETE FROM files` - destroying `captured_at`, `date_source`, `date_tag`,
    `camera_make`/`camera_model`/`lens_model` and `gps_latitude`/`gps_longitude`.
    `date_confirmations` survives only because v15 keyed it on content in its own table.
    **A removal path must never call it.**
  - **EIGHT REFUSALS for whatever acts on the report.** Never write to the drive; never call
    `forget_organized`; refuse removal when anything was unreadable; refuse unless the drive is
    `CONNECTED` (`UNKNOWN` is the normal state for a CLI-only user); never adopt and remove in
    one confirm; never identify by anything but content; never remove the last recorded copy of
    content without naming that consequence; use `relocate_copy`, not `record_copy`, which also
    rewrites `copied_at` and would relabel a 2015 copy as made today.
  - **`(hh)`'s precedent line is wrong and should be corrected when `(hh)` is next touched.** It
    reads *"Precedent: Lightroom's Synchronize Folder, which is the same operation for the same
    reason and is well understood by the audience."* On this evidence it is a **cautionary**
    precedent - the specific thing to design away from - not a model.
  - **`(hh)` and rescan are NOT one feature**, and the line is sharp: `(hh)` runs adopted files
    through the organize pipeline and therefore **writes to the drive**; rescan never does. One
    walk, two consumers - `(hh)` consumes the STRAY list.
  - **STRAY has two sub-cases with different remedies**, deliberately not split in the report-only
    slice: content the catalog has never seen (needs `(hh)`'s full ingest) and content in `files`
    with no `file_copies` row for this drive (needs only a copy row - `(abe)`'s 31 rows).
  - **Not built, with reasons:** directory-mtime filtering (saves at most the ~14 s walk at
    33,000 files, and on a cloud-synced library every folder mtime is the moment the tree was
    uploaded rather than any per-folder history, so it would buy nothing - and confirming a FUSE
    mount updates it on entry add/remove needs a **write** to that mount); an app surface; and
    any repair or removal at all.
