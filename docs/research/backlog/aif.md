# (aif) A NON-ASCII FILENAME MAY NOT SURVIVE ARGV TO EXIFTOOL ON WINDOWS.

*Body of backlog entry `(aif)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aif) A NON-ASCII FILENAME MAY NOT SURVIVE ARGV TO EXIFTOOL ON WINDOWS.** Filed 2026-08-29
  (P120), split out of `(aic)` when the reply-side fix landed: `(aic)` was the OUTPUT decode and
  is shipped; this is the INPUT transit, and no decode fix can touch it. The read path passes
  every filename to exiftool **as a command-line argument** (`exif._read_chunk`, cited by
  symbol). exiftool's own documentation says filenames otherwise pass *"straight through to the
  standard C I/O routines"*, and Windows argv reaches a Perl process through the ANSI code page -
  so a character outside cp1252 (Indic scripts, CJK - the maintainer's own library is the
  relevant case) is destroyed **before exiftool sees it**, and even a cp1252-representable `é`
  arrives as cp1252 bytes while `-charset filename=utf8` declares them UTF-8.

  ## WHAT IS ESTABLISHED, AND BY WHAT CHECK

  - exiftool's POD (`-charset` option; *WINDOWS UNICODE FILE NAMES*) and FAQ, fetched
    2026-08-29: `filename=utf8` triggers wide-character I/O and expects the given name to be
    UTF-8; the documented reliable route for non-ASCII names on Windows is a **UTF-8 argfile**
    (`-@`) with that charset - which is exactly the shape `exif.write_metadata_batch` uses, so
    **the bake path is the one already on the documented route** since P120 put
    `-charset filename=utf8` in every argfile block.
  - ⚠ **Measured 2026-08-29 (ext4, POSIX, so input-side, recorded here):** a file whose name is
    invalid UTF-8 (latin-1 `0xE9`) does not key `read_metadata`'s result under ANY `errors=`
    policy, because with `filename=utf8` exiftool replaces the undecodable byte with `?` in its
    own `SourceFile` echo - the raw byte never reaches Python's decode. Such files have always
    misfiled quietly; the reply-side fix neither caused nor cures it.

  ## WHAT IS NOT ESTABLISHED - AND THE ONE MEASUREMENT THAT SETTLES IT

  Whether the pinned 13.59 Windows launcher (`packaging/exiftool_source.py`) passes the wide
  command line through to the script cleanly. **The instrument already exists and runs on the
  Windows `check` lane**:
  `test_the_reply_survives_the_machine_locale.py::test_a_non_ascii_filename_keys_the_result_by_its_real_path`
  is `xfail(strict=False)` on Windows citing this letter. **An XPASS there settles the transit as
  safe** for the code-page-representable case and narrows this entry to characters outside the
  code page; an XFAIL means the read path must move to the argfile route the bake path already
  uses. Read the lane's xfail/xpass summary rather than rerunning by hand.

  ## SCOPE, SO THE FIX IS NOT HALF

  Moving the read path to an argfile must also note the argfile's **own path**: it is created
  under the temp directory, which on Windows lives under `C:\Users\<name>\...` - a non-ASCII
  Windows user name puts this class in front of the argfile itself. The bake path shares this
  residual today.

  ## RELATED

  `(aic)` (shipped - the reply side), `(aid)`/`(aie)` (same filed-from-source batch),
  [`takeout-format.md`](../../takeout-format.md).
