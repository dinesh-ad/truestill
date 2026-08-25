# (ahr) ORGANIZE IS NOT IDEMPOTENT: ITS OWN RENAME DEFEATS THE CATEGORISER.

*Body of backlog entry `(ahr)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahr) ORGANIZE IS NOT IDEMPOTENT: ITS OWN RENAME DEFEATS THE CATEGORISER.** Filed 2026-08-25
  (P98, soak six). Found by deleting a real catalog and rebuilding it from the files.

  🔑 **The sentence is the finding**: **re-organizing an already-organized library gives a
  different answer for some files.** The 0.27% below is the evidence, not the point.

  ## THE MEASUREMENT

  Soak five's library rebuilt from its own files: **1,127 of 1,127 matched by content hash, dates
  identical for every one, and 3 changed category `Camera` -> `Saved`** - so they changed folder:

  ```
  before  2013/2013-10/2013-10 - Everyday/20131007_231928_IMG_20130930_092249.jpg
  after   Saved/2013/2013-10/20131007_231928_IMG_20130930_092249.jpg
  ```

  **3 of 1,127 on the subset measured. Deliberately not extrapolated** to the 10,710-file library:
  the rate depends on how many files lack capture metadata, which varies by folder.

  ## THE CAUSE, REPRODUCED RATHER THAN INFERRED

  `naming.py:49` renames to `%Y%m%d_%H%M%S_<original>`. Every name rule in `categorize.py` is
  **`^`-anchored** (`categorize.py:91`, `:105`, `:117`, `:122`, and the rest), so a date prefix
  defeats all of them. Run directly:

  | input | metadata | result |
  |---|---|---|
  | `IMG_20130930_092249.jpg` | Make/Model present | `Camera` (rule `device`) |
  | `20131007_231928_IMG_20130930_092249.jpg` | Make/Model present | `Camera` (rule `device`) |
  | `IMG_20130930_092249.jpg` | **none** | `Camera` (rule `camera_filename`) |
  | `20131007_231928_IMG_20130930_092249.jpg` | **none** | ⚠ **`Saved`** (rule `fallback`) |

  🔑 **So it bites exactly the files with no capture metadata** - the ones that had only their
  filename to go on, and whose filename the product then rewrote.

  ## ⚠ THE INFORMATION IS NOT LOST, WHICH MAKES THE FIX CHEAP

  Checked before filing, because it decides the remedy: **the original name survives as a suffix**
  (`..._IMG_20130930_092249.jpg`). This is an **anchored pattern meeting a prefixed name**, not
  destroyed evidence.

  **So the remedy is a categoriser that recognises the product's own rename format** - strip a
  leading `%Y%m%d_%H%M%S_` or `%Y%m%d_` before matching, or anchor the rules after it. **Not a new
  catalog column. Not a wider drive document.** Those would be the right answer only if the
  evidence were gone, and it is not.

  ## WHAT IT FALSIFIES

  `decisions-on-drive-research.md` founded the drive document on *"hashes, dates, GPS, camera,
  categories, paths - recomputable from the files"*. **Categories are not**, while the rename runs
  before them. That line is corrected in place - the document is a live design, not a record.

  ## RELATED

  `(ahs)` (the rebuild path itself), [`soak-six-record.md`](../../soak-six-record.md),
  `decisions-on-drive-research.md` (the assumption this corrects).
