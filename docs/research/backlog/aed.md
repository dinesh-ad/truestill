# (aed) THE METADATA BAKER STAGES EVERY BAKED FILE THROUGH THE SYSTEM TEMP DIRECTORY.

*Body of backlog entry `(aed)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aed) THE METADATA BAKER STAGES EVERY BAKED FILE THROUGH THE SYSTEM TEMP DIRECTORY.** Recorded
  2026-08-19, **split out of `(adb)` at the moment `(adb)` was refused** - and the split is that
  entry's own instruction rather than a new idea: *"Do not 'fix' these together. They share a
  `shutil.copy2` and nothing else - one is a correctness hole with a known remedy, the other is a
  placement question with no measurement behind it."* ⚠ **`(adb)` was refused on measurements about
  the catalog copy. None of them touched this**, so refusing it in the same breath would have
  retired a question nobody answered.
  - **What it is.** `organizer._MetadataBaker` (`organizer.py:1245`) stages into the **system** temp
    directory rather than beside the target, so the write to the real destination is the *upload*,
    a filesystem away.
  - ✅ **NOT A SAFETY PROBLEM, and that is the reason it stayed small.** The partial lives inside a
    temp tree that is torn down, and a copy that dies never enters `self._ready`, so nothing
    incomplete is ever uploaded. `safe_copy` would not help even if applied.
  - **The cost is a full second write of every file that needs metadata baked**, onto whatever
    filesystem `TMPDIR` names - which on a small root partition is a place a photo library does not
    fit. Two distinct risks in one: throughput, and running a root partition out of space during a
    long run.
  - ⚠ **MEASURE BEFORE CHANGING ANYTHING. `PERFORMANCE.md` still has no figure for the bake path**,
    which is the same state this was in when `(adb)` first recorded it. That absence is the reason
    it is not actionable rather than a reason to act: this repo's own history is three structural
    hypotheses per arc, each fitting and each wrong, until somebody instrumented the real lane.
  - **What a measurement would have to answer:** what fraction of an organize is bake, how many
    bytes pass through `TMPDIR`, and whether the second write is visible against the copy and the
    exiftool call it sits between (`PERFORMANCE.md` §4 prices exiftool at 2.2 ms/file; nothing
    prices this).
  - **Related.** `(adb)` - where this was recorded and from which it is split, refused 2026-08-19
    on catalog-copy evidence that does not apply here. `PERFORMANCE.md` §4 - the metadata figures
    this one is missing from.
