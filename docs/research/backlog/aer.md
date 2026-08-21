# (aer) ORGANIZE'S SKIPPED REPORT DROPS HIDDEN FILES AND HIDDEN FOLDERS.

*Body of backlog entry `(aer)`, **CLOSED 2026-08-21**. The closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ⚠ CORRECTIONS, 2026-08-21 - beside the finding rather than into it
>
> **1. *"the count is of folders not files, so 1 understates 18"* is WRONG.** It is not an
> understatement, it is a refusal to invent. `c027dd3` states the rule: **files are counted,
> folders are named without a count**, because the walk never descends into a hidden or unreadable
> folder and *the number of files inside is precisely what is unknown*. `_print_unreadable` says
> the same for its own case. The honest output is *"1 hidden folder, contents unknown"* **plus the
> remedy** - which `analyze` printed and `organize` did not. Had this correction not been made,
> the fix would have "improved" the folder line into a fabricated file count.
>
> **2. *"analyze right, organize wrong"* was TOO BROAD.** Measured per surface:
>
> | | hidden FILES | hidden FOLDERS |
> |---|---|---|
> | CLI `analyze` | ✅ census | ✅ |
> | app organize | ✅ census (`_skipped_summary`) | ❌ |
> | CLI organize | ❌ four raw fields | ❌ |
>
> **One surface of three** for files - the app already read the census - and **two of three** for
> folders. The soak report's phrasing implied a clean split that did not exist.
>
> **3. The omission was INHERITED, not deliberate, and there is no recorded reason for it.**
> `c027dd3` - the commit that added hidden counting - edited `cli.py` at `@@ -1827` only, which is
> `_print_inventory_skipped`. It never touched `_print_skipped`. Its own message calls the defect
> *"`(aac)`'s shape on a third surface"*, so the author was thinking in surfaces and still updated
> the one they were looking at.
>
> **4. `(aac)` is a NEIGHBOUR, not this entry reopening.** It is still open at `BACKLOG.md:294` -
> *"residues 2 and 3 keep this entry open"* - and its subject is *unreadable* files, where the
> fact is **destroyed** by `FileHashes(None, None)` rather than merely unrendered. `(aer)` is the
> third member of that family: nothing is destroyed here, it was simply never printed.
>
> **6. ⚠ THE BROWSER LANE CAUGHT A THIRD, AND `make check` COULD NOT.** Sharing the wording meant
> picking one of two phrasings, and the CLI's was **wrong**: it printed *"folders that could not
> be read"* directly above its own *"files that could not be read: 2"* - **one phrase for the
> counted fact and the uncountable one**, which is the exact confusion the no-count rule exists to
> prevent. The browser had the right verb all along (*"could not be opened"*) and
> `test_unreadable_sources_are_visible.py` **asserts the folder block does not contain the file
> phrase**, with the reason written at the assertion. Unifying on the CLI's wording would have
> carried its collision to all three surfaces, and 2,648 pytest cases stayed green through it.
> Adopted the browser's verb; corrected the CLI. **Two more surfaced in the same run**: the shared
> remedy is a clause, so it opened a sentence in lower case (the CLI brackets it), and the heading
> became `label: count` rather than the browser's hand-built *"1 folder could not be opened"* -
> the form every other skipped group already used.
>
> **7. Three e2e stubs hand-wrote the field that was replaced**, and three more carried it as
> `[]`. The first three went red - correctly, and loudly, at 30 s each. `make gate` was run because
> the maintainer ruled that a loop plus a mapping is more than reading a field; **it was, and this
> is what it bought.**

> **5. TWO MORE FOUND ON THE WAY, fixed in the same commit because they are the same class.** The
> unreadable remedy existed **three times** - verbatim at `cli.py:2713` and `:2872`, and a third
> time in `app.js` **worded differently** (*"then preview again"* against *"then run again"*). And
> `analyze` capped its folder list at 20 while `organize` printed the list uncapped: one list, two
> behaviours.

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
