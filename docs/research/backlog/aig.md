# (aig) AN INVALID-UTF-8 POSIX FILENAME MISFILES ON READ: EXIFTOOL'S JSON WRITER ECHOES `?` FOR THE BYTE.

*Body of backlog entry `(aig)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md). **Corrected in place 2026-08-29 (P122's measurements)** - the cause this entry was filed with was wrong, and the candidate fix it carried is falsified.*

- **(aig) AN INVALID-UTF-8 POSIX FILENAME MISFILES ON READ: EXIFTOOL'S JSON WRITER ECHOES `?` FOR THE BYTE.**
  Filed 2026-08-29 (P121) as split from `(aif)`; **cause corrected same day (P122), measured**.
  A file named with raw latin-1 bytes decodes to surrogates via `os.fsdecode`, round-trips to
  exiftool intact over the stdin argfile - and exiftool **finds and reads it correctly**. What
  misfiles is the echo: **exiftool's JSON writer never emits invalid UTF-8 and replaces the byte
  with `?` in `SourceFile`, unconditionally** - measured identical with `-charset filename=utf8`
  present and removed, so the flag this entry originally blamed is not the mechanism. The
  `?`-spelled name misses `by_name` (`exif._cache_records`), the real path gets `{}`, and a file
  whose date lives only in EXIF goes to `Undated/` silently and count-proof - `(aic)`'s shape,
  living one layer deeper, inside exiftool's output stage.

  ## MEASURED 2026-08-29 (ext4, latin-1 `0xE9`, real `read_metadata` at `01dea12`)

  | condition | result |
  |---|---|
  | read, charset present (today) | keys `R?union.jpg` - misfiles |
  | read, charset removed (the filed candidate) | **identical** - the candidate is falsified |
  | read, valid-UTF-8 `é` name, charset removed | keys correctly (so the falsification is specific) |
  | **bake** on the byte name (today) | **correct and honest** - the real file gets the tags, verdict `True`, no stray `?`-named file created |
  | exiftool `-j` given the raw bytes on argv | finds the file; echo still `?` |

  So the defect is **read-only**; the bake half filed with this letter does not exist.

  ## ⚠ THE SURROGATEESCAPE REASONING WAS FALSIFIED HERE, AND WHERE MATTERS

  P119's addendum and P120's `errors=` deliberation both leaned on the hope that
  `surrogateescape` would let the raw byte round-trip and key `by_name`. **The raw byte never
  reaches the output stream** - exiftool sanitizes it before Python decodes anything - so no
  decode policy could ever rescue it, and that supporting argument is dead at this exact step.
  `errors="surrogateescape"` **still stands**, but on the one ground P120 already ruled on for
  its own reason: batch survival - strict turns one undecodable output byte into a crashed
  200-file chunk; name rescue was never available.

  ## THE ONE DIRECTION THAT COULD FIX IT, RECORDED SO NOBODY RE-DERIVES IT

  Product-side and platform-unconditional: exiftool's sanitization is deterministic, so
  `exif._cache_records`'s `by_name` could carry a **computed alias** - for any chunk path whose
  `str()` holds surrogates, add the `?`-sanitized spelling as a second key mapping to the real
  path, and **refuse the alias when two chunk paths collide onto one spelling**
  (`R\xe9union` and `R\xe8union` both alias to `R?union`; an ambiguous alias must fall back to
  today's behaviour, not guess). ⚠ **The caveat that keeps this parked rather than built: the
  `?` behaviour is OBSERVED, not documented.** Building on it means pinning it against the
  exiftool versions the product ships (`packaging/exiftool_source.py` pins 13.59), and a version
  bump could silently change the spelling the alias computes.

  ## REACHABILITY: ZERO, MEASURED - WHICH IS THE PARKING ARGUMENT

  A bytes-level walk of every observable corpus (names only, preserved reproductions skipped):
  **TruestillLibrary 105,125 files: 0 invalid-UTF-8 names. exif-samples: 0.
  metadata-extractor-images, 10,731 files including its 1,461 deliberately fuzzed: 0.**
  **Parked at the bottom of the ranked list, beside `(aib)`**: both have zero observed
  instances, but `(aib)` needs only a ruling while this needs code built against undocumented
  behaviour, for a population measured at zero. Any real instance arriving from use outranks
  this paragraph.

  ## RELATED

  `(aif)` (shipped - argv transit; its body carries a dated pointer here), `(aic)` (shipped -
  reply decode), [`takeout-format.md`](../../takeout-format.md).
