# (aif) A NON-ASCII FILENAME MAY NOT SURVIVE ARGV TO EXIFTOOL ON WINDOWS.

*Body of entry `(aif)`, **shipped 2026-08-29** - the closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md). The invalid-UTF-8 POSIX residual recorded below is now `(aig)`.*

- **(aif) A NON-ASCII FILENAME MAY NOT SURVIVE ARGV TO EXIFTOOL ON WINDOWS.** Filed 2026-08-29
  (P120) as reasoned-from-documentation; **measured the same day and confirmed**: the instrument
  filed with it - the filename-keying test, `xfail(strict=False)` on Windows - came back
  **XFAIL on the Windows lane, run 33242186610**, with the reply-side decode already fixed and
  both hostile-locale tests passing there. So the argv transit really does lose a filename on
  Windows, for even a cp1252-representable `é`: argv reaches exiftool - a Perl process -
  through the ANSI code page, while `-charset filename=utf8` declares the bytes UTF-8.

  ## THE FIX (P121)

  **No filename crosses argv any more - nothing does.** `exif._run_via_stdin_argfile` ships
  every argument to exiftool as a UTF-8 argfile **on stdin** (`-@ -`, documented), and both the
  read path (`_read_chunk`) and the bake path (`write_metadata_batch`) go through it. Stdin
  rather than a temporary argfile on purpose: a temp file would put its OWN path on argv, and
  under `C:\Users\<name>\...` a non-ASCII user name lands this class in front of the argfile
  itself - the residual this entry recorded at filing, retired by the shape rather than
  mitigated. Both shapes (`-json` + tag list + paths; per-file `-execute` blocks) verified
  against a live exiftool before landing. The acceptance test is the same instrument with its
  `xfail` removed: a plain assertion on every platform, so a Windows failure is a regression,
  not an open question.

  ## WHAT WAS ESTABLISHED ALONG THE WAY

  - exiftool's POD and FAQ (fetched 2026-08-29): `filename=utf8` triggers wide-character I/O on
    Windows and expects the given bytes to be UTF-8; the argfile is the documented route.
  - ⚠ **Measured (ext4, latin-1 `0xE9`):** a file whose name is invalid UTF-8 misfiles under
    every `errors=` policy, because exiftool replaces the undecodable byte with `?` in its own
    `SourceFile` echo before Python decodes anything. Input-side, unfixed by any of this, and
    now **`(aig)`** - which also carries the candidate fix the measurement suggests.

  ## RELATED

  `(aic)` (shipped - the reply side), `(aig)` (the POSIX residual), `(aid)`/`(aie)` (same
  filed-from-source batch), [`takeout-format.md`](../../takeout-format.md).
