# (aig) AN INVALID-UTF-8 FILENAME ON POSIX MISFILES, BECAUSE ITS NAME IS DECLARED TO BE UTF-8.

*Body of backlog entry `(aig)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aig) AN INVALID-UTF-8 FILENAME ON POSIX MISFILES, BECAUSE ITS NAME IS DECLARED TO BE UTF-8.**
  Filed 2026-08-29 (P121), split out of `(aif)`'s measured residual when `(aif)` closed. A file
  named with raw latin-1 bytes (old cameras, FAT cards, pre-UTF-8 archives) decodes to
  surrogates via `os.fsdecode`; the stdin argfile encodes them back to the original bytes (the
  door's `surrogateescape`), and exiftool is then told `-charset filename=utf8` - so it meets
  bytes that are not valid UTF-8 and **replaces the byte with `?` in its own `SourceFile` echo**
  (measured 2026-08-29, ext4, `0xE9`). The record keys a fictitious name, `metadata.get(path)`
  is `{}`, and the file goes to `Undated/` silently - `(aic)`'s exact failure shape, surviving
  `(aic)`'s fix because it happens inside exiftool, before any decode.

  ## THE CANDIDATE FIX, MECHANISM PART-VERIFIED, NOT BUILT

  The charset declaration is only *needed* on Windows, where it triggers wide-character I/O.
  On POSIX, exiftool's documented default passes filename bytes *"straight through to the
  standard C I/O routines"* - and the decode half of the round trip is already measured to work:
  raw bytes come back verbatim and `surrogateescape` reconstructs the identical surrogates
  `str(path)` holds, so `by_name` would key. Making `-charset filename=utf8` Windows-only in
  `exif._read_chunk` and `exif.write_metadata_batch` is the shape; what it still needs is an
  end-to-end POSIX measurement without the flag, and a test whose fixture is a byte-named file -
  legitimately POSIX-only, since NTFS cannot hold an invalid-UTF-8 byte name (the
  condition-cannot-be-created skip, `PROJECT_STATUS.md`'s unreadable-dir precedent).

  ## CHECKS RUN AT FILING

  The `?`-echo is measured (above). One improvement already landed by construction, not built
  for this: before P121 the bake path would have **crashed** on such a name - the temp argfile
  was written with strict UTF-8 and a surrogate cannot encode - while the stdin route encodes
  with `surrogateescape`, so the batch now survives and the file is reported failed instead.

  ## RELATED

  `(aif)` (shipped - argv transit), `(aic)` (shipped - reply decode),
  [`takeout-format.md`](../../takeout-format.md).
