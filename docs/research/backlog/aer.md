# (aer) ORGANIZE'S SKIPPED REPORT DROPS HIDDEN FILES AND HIDDEN FOLDERS.

*Body of backlog entry `(aer)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aer) A HIDDEN FOLDER OF 18 PHOTOS READS AS A CLEAN SUCCESS.** Found 2026-08-21 by soak two.

  ## MEASURED

  A folder holding 21 photos, 18 of them in `.MyAlbum`:

  | surface | what it said |
  |---|---|
  | `organize --apply` | *"files analysed: 3 · organized (unique): 3"* - **success, and no mention of the other 18** |
  | `analyze`, same folder | *"hidden folders (not looked inside): 1 - `.MyAlbum` (contents unknown)"* plus how to include it |

  And on the real corpus, a real `.picasa.ini`: `analyze` names it, `organize` says nothing.

  ## ROOT CAUSE - TWO IMPLEMENTATIONS OF ONE PROMISE, ONE MISSING TWO BUCKETS

  `SourceScan` has `documents, exiftool_backups, hidden, hidden_dirs, markers, media,
  unreadable_dirs, unrecognized`. `cli._print_skipped`, which is what **organize** prints, reads
  **four**: `documents`, `exiftool_backups`, `unreadable_dirs`, `unrecognized`. It never reads
  `hidden` or `hidden_dirs`. `scan.hidden` is read **nowhere** outside core.

  `cli._print_inventory_skipped`, which **analyze** prints, renders the census
  (`skipped_extension_counts`, which *does* include `HIDDEN_LABEL`) plus `hidden_dirs`. Its
  docstring says it *"mirrors `_print_skipped`"* and explains why they cannot be one function -
  counts versus path lists. That explanation is correct **and is how they drifted**.

  ## ⚠ THE CODE ALREADY NAMES THE DEFECT AND THE FILE

  `organizer.HIDDEN_LABEL`'s comment: *"a skip that is never counted is the `(aac)` defect, and
  `.picasa.ini` is real user metadata that used to vanish from the report entirely."* It vanished
  from the organize report entirely. `(aac)`'s fix reached the census and one of the two renderers.

  `_print_inventory_skipped`'s own comment on hidden folders: *"A user with an album in a hidden
  folder used to see nothing at all - not a count, not a name."* On organize, they still do.

  ## WHY IT MATTERS MORE THAN THE FILE COUNT SUGGESTS

  This violates §1 (*"Every source file is accounted for - none silently dropped ... Nothing is
  discarded without appearing in a report"*) and §9's never-silent rule, **on the happy path, with
  a success message**. `(aek)` was a crash and therefore loud. This is quiet, and a hidden folder
  can hold an entire album.

  ## NOT DECIDED

  - **Whether the two renderers should become one.** The stated reason they are separate - one
    keeps path lists, the other counts, so a 33,000-file census never builds a per-file structure -
    is sound. The fix may be to render **organize** from the census too, keeping path lists only
    for the buckets that name files.
  - **Whether `markers` needs surfacing on organize as well.** It is the sixth field and the only
    other one `_print_skipped` ignores; the census keeps it apart deliberately.
