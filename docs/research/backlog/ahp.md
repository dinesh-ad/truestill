# (ahp) `truestill ingest --source <archive>` CRASHES ON EVERY ARCHIVE.

*Body of backlog entry `(ahp)`, now in [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahp) `truestill ingest --source <archive>` CRASHES ON EVERY ARCHIVE.** Filed 2026-08-25
  (P95, the full-library soak). **Shipped, unconditional, and reached by the feature's own
  documented invocation** - `--source PATH` is helped as *"folder of photos, or an archive (.zip,
  .tar, .tgz)"*.

  ## THE CRASH

  ```
  File "packages/truestill-cli/src/truestill_cli/cli.py", line 1683, in _source_root_or_none
    report = precheck_archives(archives_at(given) or [given], destination)
  File "packages/truestill-core/src/truestill_core/archive_ingest.py", line 198, in precheck_archives
    facts = facts_for(destination)
  File "packages/truestill-core/src/truestill_core/filesystem.py", line 139, in facts_for
    resolved = target if target.exists() else _nearest_existing(target)
  AttributeError: 'str' object has no attribute 'exists'
  ```

  A traceback, not a refusal: no message a person can act on, exit 1, nothing written.

  ## THE CAUSE, AND IT IS A BOUNDARY

  `cli.py:373` declares the positional `destination` with **no `type=Path`**, so argparse hands a
  **`str`** to code annotated `Path`. `precheck_archives(paths, destination: Path)` then calls
  `facts_for(destination)`, which calls `.exists()`.

  ⚠ **A folder source works and an archive does not**, measured: `truestill ingest DEST --source
  <folder>` completed normally in the same session. Only the archive branch reaches
  `precheck_archives`, which is why the defect is invisible on the path most runs take.

  ⚠ **mypy cannot see it.** `args.destination` comes off an `argparse.Namespace`, whose attributes
  are `Any`, so strict mode type-checks the call and learns nothing. The boundary between argparse
  and typed code is where `Any` enters this program.

  ## WHY NO TEST CAUGHT IT - AND IT IS THE INTERESTING PART

  `test_ingest_archives_cli.py:40` does exercise the archive path:

  ```python
  assert _source_root_or_none(extracted, tmp_path / "dest") == extracted
  ```

  🔑 **It passes a `Path`. The real caller passes a `str`.** The test constructs its input
  differently from the caller it stands in for, so it proves the helper works on an input the
  product never gives it. That is the same shape as `(agu)` - a check aimed at the thing next to
  the defect - and no amount of coverage on that file would have found this.

  ## ⚠ THE FIX IS NOT ONE LINE, AND THAT IS THE RULING

  Adding `type=Path` to `cli.py:373` stops this traceback and leaves the boundary unguarded.
  **One instance means the boundary is unguarded, not that one argument is wrong.**

  **What this entry asks for**: a census of **every** `argparse` argument whose value is consumed
  by something annotated `Path`, checking each declares `type=Path`. Derived from `cli.py`'s AST
  against the handlers' annotations, in the shape `(ahj)` and `(ahn)` stage 2 already use - loop
  the derived inventory, assert into the declaration. Until that census exists, the count of
  arguments in this state is **unknown**, and this letter does not guess it.

  ## ⚠ THE CENSUS RAN FIRST, AND IT CHANGED THE FIX

  **Shipped 2026-08-25 (P97).** The entry asked for a census before a fix, and the census is the
  reason the fix is not `type=Path`.

  **83 `add_argument` calls in `cli.py`**: 35 already declare `type=Path`, 5 `int`, 1 a custom
  parser, and **42 declare no type**. Of those 42, only **8** are non-action arguments, and of
  those eight only **one - `destination` - is path-like**; `label`, `pool`, `preset`, `run_id`,
  `set_template`, `term` and `uuid` are genuinely strings.

  🔑 **So this is a defect, not a class.** One argument, ten uses, five of which already wrap it in
  `Path(...)`.

  ⚠ **AND `type=Path` WOULD HAVE BEEN WRONG ON IT.** `destination` is *"a local directory path, or
  an rclone remote spec"* (`cli.py:373`). Converting in the parser would wrap `remote:bucket` in a
  `Path`, and `extract_archive_set` would unpack into a local folder **named after the remote** -
  a crash turned into silent wrong behaviour. `_build_destination(spec: str, ...)` is correctly
  typed and already handles both.

  **The fix**: convert at the call site, where which one it is is known, and pass `None` for a
  remote - the `rclone -> None` convention `_shas_on_destination` already uses (`cli.py:1944`).
  The archive route refuses on `None`, because unpacking needs a filesystem to stage into, ask for
  free space, and read a per-file size limit from.

  ## ⚠ CAN A GUARD CLOSE THE CLASS? RULED: NOT THIS ONE

  An AST check that *"every `add_argument` consumed as a `Path` declares `type=Path`"* is
  buildable - the census above is most of it - but it would assert a rule that is **false for the
  only instance it has**. `destination` must stay untyped.

  **The check that would actually work is typing the Namespace**, so mypy sees the call sites at
  all: `argparse.Namespace` attributes are `Any`, and that is the whole reason this shipped. That
  is a real change across 83 arguments and belongs in its own turn, not in a commit whose subject
  is one crash. **Recorded rather than guarded**, and the census number is why: one instance does
  not pay for a mechanism that would have to be wrong about it.

  ## WHAT SHIPPED, AND THE PROOF

  Two tests that drive `main()` end to end - an archive ingest that must exit 0, and an archive to
  an rclone remote that must be refused rather than staged. **Reverting the fix turns both red and
  leaves all four pre-existing tests in the file GREEN**, including
  `test_a_directory_is_passed_straight_through`, which is the measured proof that a helper-level
  test could never have caught this class.

  Verified on the real archive too: **1.61 GB, 534 entries, 14.25 s** on ext4, exit 0 - 534
  analysed, 520 dated from embedded EXIF, staging under the destination at
  `.truestill-staging/` per `(ags)`, and the source archive byte-identical afterwards.

  ⚠ **One thing this did NOT fix, found while reading the artifact**: the staging tree is **left
  behind** - 535 files, 1.6 GB beside the 1.6 GB organized copy - and nothing anywhere removes it
  (`grep` for `rmtree|unlink|clean` against `archive_ingest.py` returns nothing). Consistent with
  copy mode never deleting a source, and still a doubling of space after every archive ingest.
  Not this commit's subject.

  ## RELATED

  `(agu)` (a check aimed beside the defect), `(ahn)` (the typed-boundary work this belongs beside),
  [`soak-five-record.md`](../../soak-five-record.md) (the run that found it).
