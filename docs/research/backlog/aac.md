# (aac) Organize must name and count unreadable source files the way verify does.

*Body of backlog entry `(aac)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aac) Organize must name and count unreadable source files the way verify does.** Ruled by
  the maintainer, 2026-07-30, from the Pass 1 F2/F1 asymmetry left after the code-quality audit.
  **Scan tier and residue 1 built 2026-08-02; residues 2 and 3 keep this entry open.**
  - **What shipped.** F1 gave `verify` `CopyStatus.UNREADABLE`, a count, and filenames on CLI
    and app. F2 kept `compute_hashes` alive on an unreadable source (empty hashes +
    `BrokenExecutor` guard) so an organize preview/run no longer aborts the whole pass.
  - **RE-SCOPED 2026-08-01, and the finding is sharper than "unreported": the fact is
    DESTROYED, not merely unsurfaced.** Traced end to end. `scan._hash_one` catches `OSError`
    per file and returns `(path, None, None)`, so an unreadable file becomes
    `FileHashes(None, None)`. That is **the same value** the size pre-filter produces for a file
    it legitimately chose not to hash - `DedupIndex.check`'s own docstring says so: *"`sha256` is
    `None` for a unique-size file the pre-filter chose not to hash"*. The two states are
    indistinguishable downstream by construction, so no consumer can count them apart even if
    one wanted to. Nothing in core or the app reads an absent sha for reporting; grep finds no
    such consumer.
  - **Which surface is still silent, precisely.** The **run** path catches it late and by
    accident: the copy raises and the file is reported `ActionStatus.FAILED`. The **preview**
    path attempts no copy, so there is no status to report and nothing is said at all - the
    user is told the file is fine. A locked or `EIO` file in the source tree is therefore
    invisible in exactly the pass whose job is to say what will happen
    (`IMPLEMENTATION_STANDARDS.md` §9).
  - **Requirement.** Organize preview and run summaries must count and name unreadable sources
    the way verify reports unreadable copies - which first needs the scan to stop conflating
    "could not read" with "did not need to". Do not treat empty hashes as a finished answer.
  - **The docstring that read as though this were already closed: fixed 2026-08-02.**
    `SourceScan`'s docstring said an unreadable file *"surfaces as `ActionStatus.FAILED` when the
    copy raises"* full stop, with no **run only** qualifier, so the comment standing next to this
    code announced a resolution the code had not reached. It now names the run path it is true
    of and cites this entry.
  - **THE SCAN TIER IS BUILT (2026-08-02). THE ENTRY IS NOT CLOSED.** `UnreadableReason`
    (permission / I/O error / missing / other) rides on `FileHashes`, so *"could not read"* and
    *"correctly did not hash"* are no longer one value. `scan._probe_readability` opens every
    path and reads one byte **before the hash-cache split** - `stat` succeeds on an unreadable
    file, so a stale-cache hit would otherwise skip the worker entirely - and `_hash_one` keeps
    its own handler for the late failure a 1-byte probe cannot see. The CLI names the files on
    preview and run with the FAILED set subtracted; the app payload carries `{total, shown}`;
    `app.js` renders it **and the `unreadable_folders` key that had been reaching the browser
    unrendered since it shipped**. A preview that found one now exits `1`. Contract row in
    `IMPLEMENTATION_STANDARDS.md` §9; cost in `PERFORMANCE.md` §3.2.
  - **RESIDUE 1 - BUILT 2026-08-02. Ruled: disjoint buckets, enforced by a conservation law.**
    The shipped build reported *"organized (unique): 5"* and *"files that could not be read: 2"*
    for the same seven files, with both unreadable photos inside the 5. `partition_for_report`
    now splits every scan into four buckets that are disjoint **and** exhaustive, and
    `new_unique + near_dup + exact_dup + unreadable == files` is asserted on both the printed
    summary and the app payload - so a category added later that forgets to be disjoint fails a
    test instead of double-counting the way this one did. Unreadable is tested **first**, because
    a cache hit gives an unreadable file real hashes and it can therefore match the exact or
    perceptual tier; filing it as a routine skip would bury the fact that truestill could not
    read it (the *skipped error* vs *skipped success* distinction AWS DataSync draws).
    **The plan was not touched, and that was the finding rather than a compromise.** `execute`
    never consults `should_upload` - it branches on `exact_duplicate` directly - so the report
    was separable from the plan. It also *should* be: on a run the unreadable file is still
    attempted, the copy raises, and that is what produces the `ActionStatus.FAILED` the user
    sees. `preflight_for_run` must keep sizing the destination for it. Excluding it from the plan
    would have deleted the run's only report of the file. Fixing the tally alone is what makes
    preview and run agree: *"4 organized, 1 unreadable"* predicts *"4 organized, 1 failed"*.
    Applied to all five report sites, `ingest` included - it shares `_run_pipeline` and so
    already printed the unreadable block beside the same contradiction.
  - **RESIDUE 2 - the app's *run* completion has no `unreadable_files`.** Preview only, matching
    the design that was accepted. The CLI reports on both. An unreadable file that was never
    copied - a cached exact duplicate - therefore has no app-side surface on a run, though the
    CLI names it.
  - ✅ **RESIDUE 3 CLOSED 2026-08-21 BY `(aev)`, recorded here 2026-08-22.** Its ask - *"a file
    that is readable but undecodable still returns `None` and is still indistinguishable from a
    video that never had a hash"* - is exactly what `FileHashes.perceptual_computed` now answers,
    and `uncompared_photos` counts and names them in every report. ⚠ **Neither entry cites the
    other**: `(aev)` was raised by soak two over Pillow warnings and arrived at this residue from
    the other side, so the closure went unrecorded for a day. The original text follows, unedited.
  - **RESIDUE 3, and what changed about it: the perceptual tier's overloaded `None`.** Recorded
    2026-08-02 while verifying a proposed HEIC feature that turned out not to exist.
    `perceptual_hash` returns `None` and discards the reason, so one sentinel carried four
    meanings: a video (correct - none exists for it), not an image at all, above the 300 MP
    ceiling, or **could not be decoded**. `DedupIndex.check` skips the tier on `None` and
    `register` omits the file, both silently.
    **The scan fix evacuated the unreadable meaning from those four**: a file that cannot be
    opened is now named by the probe, so its perceptual `None` is no longer the only trace of it.
    What remains is narrower and is the honest statement of this residue: **a file that is
    readable but undecodable** - a truncated JPEG, a corrupt HEIC - still returns `None` and is
    still indistinguishable from a video that never had a hash. That is a *corruption* report,
    with a different remedy from a permission one, which is why it is deliberately not folded
    into the scan fix: `test_a_corrupt_but_readable_image_is_not_called_unreadable` exists to
    keep the two apart. Nothing counts or names a per-file perceptual failure; the whole-library
    case is loud (`heic_perceptual_skipped`, and the CLI's note when `HEIF_AVAILABLE` is false),
    which is exactly what makes the per-file case easy to believe is covered.
