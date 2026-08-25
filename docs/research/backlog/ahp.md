# (ahp) `truestill ingest --source <archive>` CRASHES ON EVERY ARCHIVE.

*Body of backlog entry `(ahp)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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

  `test_ingest_archives_cli.py:39` does exercise the archive path:

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

  ## RELATED

  `(agu)` (a check aimed beside the defect), `(ahn)` (the typed-boundary work this belongs beside),
  [`soak-five-record.md`](../../soak-five-record.md) (the run that found it).
