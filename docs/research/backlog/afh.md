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
