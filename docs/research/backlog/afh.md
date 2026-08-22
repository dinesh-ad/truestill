# (afh) THE CEREMONY IS INVERTED RELATIVE TO THE STAKES: DELETING PHOTOS IS EASIER THAN DELETING EMPTY FOLDERS.

*Body of backlog entry `(afh)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afh) FOUND BY SOAK FOUR, STEP D2, 2026-08-22.** Not a truthfulness defect - both commands
  describe themselves accurately. A **proportionality** one.

  ## MEASURED

  `reclaim --apply` on 161 real files, then a hunt for them:

  ```
  This PERMANENTLY DELETES 161 source file(s), freeing 0.30 GB.
  Type 'delete' to proceed (anything else aborts):
  Freed 161 source file(s), 0.30 GB.

  home trash files   : 0
  /data/.Trash-1000  : does not exist
  ```

  Gone. `run_reclaim` calls `candidate.source_path.unlink()`; there is no trash path in it at all.

  ## THE TWO CEREMONIES, SIDE BY SIDE

  | | what it removes | recoverable? | typed word | warning |
  |---|---|---|---|---|
  | `reclaim --apply` | **the user's original photos** | **no** | `delete` | one line |
  | `clean-empty --apply` | folders the product itself emptied | **yes**, OS trash | `clean` | - |
  | `clean-empty --permanent` | the same folders | no | **`delete forever`** | three lines, capitals, and `rmdir` semantics so a non-empty folder cannot go |

  ⚠ **The most destructive act in the product has the weakest ceremony of the three.** Deleting
  someone's photographs permanently asks for `delete`; deleting an empty folder permanently asks
  for `delete forever` and explains itself three times first.

  ## WHY THIS IS NOT A RULE VIOLATION, WHICH IS WHY IT NEEDS A DECISION RATHER THAN A FIX

  `IMPLEMENTATION_STANDARDS.md` §1 condition **(d)** - *"it goes to the OS trash where the
  platform allows, and a trash refusal leaves the folder in place"* - is written **inside the
  folder-removal paragraph** and is scoped to `clean-empty`. `reclaim.run_reclaim` is named
  separately, as one of the three scoped exceptions to copy-only. So reclaim breaks nothing.

  **The question is whether (d) was ever meant to be about folders.** Its reasoning - a
  destructive act should be recoverable where the platform allows, and an unavailable trash is a
  refusal rather than a licence - does not contain anything folder-specific. It reads like a
  general policy that was written down at the first place it came up.

  ## WHAT THE PRODUCT SAYS IN ITS OWN DEFENCE, AND IT IS A REAL ARGUMENT

  Reclaim's gate is the strongest in the product: the destination copy is re-hashed **immediately
  before** each `unlink`, so a file is only deleted when its content is provably somewhere else.
  Measured in the same run - 161 deleted, and every one of their sha256 values still present on
  the drive. **Deleting a file you have proven is duplicated is not the same act as deleting a
  file.** Trash for such a file is arguably storing a third copy of something already backed up,
  on the disk the user asked to free.

  ⚠ That argument is good and it is **not the same as the ceremony question.** Even granting that
  reclaim need not trash, `delete` versus `delete forever` still ranks the two acts backwards.

  ## OPTIONS, NOT A RECOMMENDATION

  **A. Level the ceremony only.** Reclaim asks for `delete forever`, or names the drive it
  verified against in the prompt. *Cheapest; changes no behaviour; addresses the inversion and
  nothing else.*

  **B. Extend (d) to files.** Reclaim trashes where the platform allows. *For:* one policy, one
  reasoning, no per-feature exceptions. *Against:* directly defeats the feature - freeing 0.30 GB
  by moving 0.30 GB to the trash frees nothing until the user empties it, and a user who runs
  reclaim to reclaim space would reasonably call that a bug.

  **C. Make (d)'s scope explicit either way**, in §1, so the next reader does not have to infer
  it from which paragraph it sits in. *This is worth doing whichever of A or B is chosen, and is
  the fifty-eighth member's shape: the scope is currently unwritten and therefore unfalsifiable.*

  **D. Nothing.** Both commands are truthful; a user who types `delete` after reading
  *"This PERMANENTLY DELETES"* has been told.

  ## NOT DECIDED

  - Whether §1 **(d)** is a folder rule or a product rule.
  - Whether reclaim's proof-of-duplication earns it a weaker ceremony, or a stronger one because
    the files are irreplaceable in a way empty folders are not.
  - Whether `--min-copies 1` should be the default at all, given the run warns that 161 files
    *"would then exist in only ONE place"* immediately before deleting the second-to-last copy.

  ---

  # RULED AND FIXED 2026-08-22. The stronger act gets the stronger word.

  ## The asymmetry, measured from two real runs rather than from the source

  ```
  RECLAIM - removes 161 of the user's own photographs, permanently
    This PERMANENTLY DELETES 161 source file(s), freeing 0.30 GB.
    Type 'delete' to proceed (anything else aborts):
                                          3 lines, one word

  CLEAN-EMPTY --permanent - removes 3 empty folders Truestill itself emptied
    3 folder(s) will be removed.
      3 are empty - nothing in them, so nothing to recover.
    The folder itself is removed outright, not moved to the trash. Removal uses rmdir,
    so a folder that is no longer empty when the removal runs is left alone and reported.
    --permanent: where the trash refuses OR is unavailable, any OS junk in these folders
    is removed OUTRIGHT and is NOT recoverable.
    Type 'delete forever' to remove 3 folder(s):
                                          6 lines, two words
  ```

  Neither was untruthful. The **ceremony was inverted relative to the stakes**, and the fix is to
  raise `reclaim` rather than lower `clean-empty` - lowering the strong word is the cry-wolf
  failure this vocabulary exists to prevent.

  ## What `reclaim` says now

  ```
  This deletes 161 ORIGINAL file(s) from this computer, freeing 0.30 GB.

    These are your originals, not spare copies. Each one is deleted only after its
    content is re-read on 'drive' and matches - but once it is gone, that
    drive is the only place it exists.

    They do NOT go to the trash, and this CANNOT BE UNDONE.

  Type 'delete originals' to proceed (anything else aborts):
  ```

  ## The typed word: `delete originals`, and why not `delete forever`

  `delete forever` was the consistent choice and is **rejected on what it names**. It says *no way
  back*, which a `reclaim` user is unlikely to doubt. What such a user may doubt is **whether these
  are spares** - and the old wording, *"PERMANENTLY DELETES 161 source file(s)"*, never said
  otherwise, because *"source file"* is the catalog's word for it rather than the user's.

  `delete originals` names **what is lost** instead of that the loss is permanent. It is also two
  words nobody types from habit, and it retires `delete` - the weakest-looking word in the product,
  which was guarding its strongest act. The count of phrases is unchanged: `clean`,
  `delete originals`, `delete forever`.

  ⚠ **Pinned as a comparison, not as a sentence.** `test_reclaim_asks_for_at_least_as_much_as_clean_empty_permanent`
  fails if `reclaim`'s ceremony is lowered *or* if the recoverable word ever becomes its ask, which
  a test of either wording alone would not catch. And the retired word is pinned too: typing
  `delete` out of habit now deletes nothing.

  ## ⚠ §1's condition (d) is NOT extended to `reclaim` - a ruling, with the reason

  Recorded in `IMPLEMENTATION_STANDARDS.md` §1 so it cannot be re-derived as an oversight.

  Trashing the originals `reclaim` removes is **not recovery**. It is a second copy of the same
  bytes on the same filesystem, in a command whose entire purpose is to free that filesystem.
  Measured: the library is **117 GB across 55,110 files** on a 916 GB volume with 774 GB free. A
  trashing `reclaim` would free **nothing** until the user emptied the trash, and on a fuller disk
  it would fail outright at the point of maximum need.

  **(d) protects contents that have nowhere else to be.** A reclaimed original has, by
  construction, been re-read and matched on another drive moments before - which is the strongest
  gate in the product and the thing that makes deleting it defensible at all.

  ## NOT DECIDED, still

  - **Whether `--min-copies 1` should be the default.** The run warns that N files *"would then
    exist in only ONE place"* immediately before deleting the second-to-last copy. Raising the
    default would make that warning unreachable, which is either a fix or a feature removal
    depending on what a user wants `reclaim` for.
