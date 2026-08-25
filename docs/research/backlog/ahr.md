# (ahr) ORGANIZE IS NOT IDEMPOTENT: ITS OWN RENAME DEFEATS THE CATEGORISER.

*Body of backlog entry `(ahr)`, now in [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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

  ## WHAT SHIPPED (2026-08-25, P100)

  **`naming.without_own_stamp` - the recogniser lives where the format is written.** `naming.py`
  already carried `_OWN_STAMP_PREFIX` to stop `dated_filename` double-stamping; it is now public
  and `categorize` asks it. ⚠ **The alternative - unanchoring the rules - was refused**: it would
  make every convention match a substring anywhere in a name, a far wider blast radius than the
  defect. And a regex copied into `categorize.py` would be a second definition of one format, free
  to drift the next time the stamp changes - `STOP_WORDING`'s rule applied to a format.

  **Both prefix shapes** are handled by the existing pattern, `^(\d{8})(?:_\d{6})?_`.

  ⚠ **THE STRIP CANNOT LOSE A MATCH, which is why it runs unconditionally.** No rule in
  `categorize.py` begins with a digit, so a name starting with eight digits matches nothing today:
  a name the strip does not change is unaffected by definition, and one it does change could not
  have matched before. **Monotone, not merely tested.**

  ⚠ **The trap, checked rather than assumed.** A genuine `20130930_092249.jpg` is indistinguishable
  from a stamp, and stripping leaves `092249.jpg`. Both categorise `Saved`, so the ambiguity costs
  nothing; what is guarded is the empty remainder - a name that is *only* a stamp is returned
  unchanged.

  ## THE CENSUS: ONE INSTANCE, NOT A CLASS

  The rename changes a name, so everything that reads one was checked:

  | consumer | broken by the rename? |
  |---|---|
  | `categorize.py`'s name rules | ⚠ **yes** - this defect |
  | the date resolver's filename tier | **no**, and the reason is neat: `dated_filename` returns the name unchanged when its stamp is already in it, so a file dated *from its filename* is never renamed. Its evidence protects itself |
  | `is_messenger_filename` | **no** - only reached through that tier |
  | `rule_software` | **no** - its signature is `(_path, metadata)`; it never reads the name |
  | trip and event naming | **no** - `event_review.py` reads the user's typed name, not a filename |

  🔑 **So the categoriser broke and the date tier did not, because the date tier's evidence IS the
  stamp's source.** Nothing protected the categoriser, whose evidence is unrelated to the date.

  ## THE PROOF

  **The test asserts the PROPERTY**: whatever the first organize decided, a second organize over
  its own output decides the same - seven parameters including both cry-wolf halves (a file with
  EXIF, decided by `device` and never affected; a genuinely unrecognised name, which must still
  land in `Saved`). A filename-to-label test would have passed throughout the defect.

  **Two mutations, caught by two different tests**: reverting the strip fails 4 idempotence
  parameters; making it greedy (`^[^_]*_`, eating a real prefix) fails 11 convention tests.

  🔑 **And the closing measurement is not the unit test.** The `(ahs)` rebuild was re-run on the
  same 1,127-file subset: **1,127 of 1,127 matched by content with ZERO differences** in date,
  source or category. Before the fix that run moved 3 files from `Camera` to `Saved`.

  ## RELATED

  `(ahs)` (the rebuild path itself), [`soak-six-record.md`](../../soak-six-record.md),
  `decisions-on-drive-research.md` (the assumption this corrects).
