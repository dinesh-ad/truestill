# (afn) A DRIVE WHOSE SAMPLE CANNOT BE READ IS REGISTERED AS A NEW ONE, SILENTLY.

*Body of backlog entry `(afn)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afn) SPLIT OUT OF `(afa)` ON 2026-08-22.** ⚠ **A data-integrity defect, not a reporting gap**,
  and it outranks the two entries it was filed beside. `(afa)` was about a fact the product holds
  and does not render; this is about a *guard that a refusal bypasses instead of triggering*.

  ## THE PRODUCT STATES THE HARM IT IS FAILING TO PREVENT

  `cli.py:1002-1005`, the refusal a recognised drive gets:

  ```
  error: {path} already holds the library recorded as {names}.
         Registering it again would create a SECOND drive id for one library, and Truestill would then
         count one copy of your photos as two. Nothing was written.
  ```

  That refusal never fires when the sample could not be read.

  ## MEASURED, END TO END

  A **perfect** drive - every recorded file present and byte-correct - with 30 of its 40 sampled
  paths behind a `chmod 000` folder:

  ```
  offers returned by inspect_root : []
  _init_drive sees `offers` as    : empty
  refusal printed?                : no
  registration proceeds?          : YES - a second drive id

  control, same drive fully readable: [('proven', 40, 40)]
  ```

  ## THE CHAIN, AND EVERY LINK IS ORDINARY

  1. **`drive_adoption.py:173-174`** - a refused path `continue`s, *"not evidence either way"*.
  2. **`drive_adoption.py:178`** - but the threshold is `len(present) < PRESENCE_THRESHOLD *
     len(sample)`, and `len(sample)` **still counts the refused ones**.
     ⚠ **So the `continue` changes nothing.** Falling through to `if found is Reach.FILE` would
     give False and also skip the append: **refused and absent are arithmetically identical here**,
     which is precisely what the comment at `:169-171` says the fix prevented. `(aey)` made the
     intent explicit without changing the behaviour.
  3. **`drive_adoption.py:147`** - `inspect_root` returns only offers that are **not** `NO_MATCH`.
  4. **`cli.py:1044`** - so `offers` is empty.
  5. **`cli.py:1062`** - `if offers and not args.adopt_existing` never fires, and registration
     proceeds.

  With the real constants (`STAT_SAMPLE = 40`, `PRESENCE_THRESHOLD = 0.5`) the tipping point is
  **21 refusals out of 40**:

  ```
  refused=20  present=20/40  -> passes to hash proof
  refused=25  present=15/40  -> NO_MATCH   (and therefore invisible)
  ```

  ## ⚠ WHY THIS IS NOT `(afa)`

  `(afa)` asks *"how should refusal be worded?"*. Here, wording is the last of the problems: even a
  perfect sentence has nowhere to appear, because `NO_MATCH` is filtered out before any surface
  sees it. **Adding an unreadable count beside the presence tally would change nothing until
  `NO_MATCH` is reportable at all**, which is the reverse of the order a reporting entry implies.

  ## NOT DECIDED - and the read-only on this is the next step, not the fix

  - **Report `NO_MATCH`**, so a drive the product could not read is named rather than dropped.
  - **Change the denominator** to the paths actually examined, so refusals stop counting as
    absences.
  - **Refuse to register at all** when too much of the sample could not be read - treating "I could
    not look" as a reason to stop, the way `reclaim` and `cleanup` already do.

  These are not alternatives to each other in the obvious way, and the third has a cost the other
  two do not: it can stop a genuinely new drive being registered.

  ---

  # FIXED 2026-08-22. A + C. B refused, with its reason recorded.

  ## The ruling

  **C - do not mint an identity on evidence the product could not gather.** `source_repoint`
  already refuses on the identical empty list, and `reclaim` will not delete what it cannot read:
  **the registration paths were the outliers, not the standard.**

  **A as prerequisite**, because C cannot explain itself while `NO_MATCH` reaches no surface. ⚠ And
  A had the trap: `test_an_unrelated_folder_produces_no_offer` pinned the filter, so **the filter
  was load-bearing for a reason nobody had written down.** A had to separate *no offer because
  nothing matched* from *no offer because nothing could be read* - the two states the empty list
  conflates. A fix that did not separate them would reproduce the defect one layer up, refusing
  every new drive.

  **B refused, and this is the reason.** Changing the denominator to the paths actually examined
  means that with 39 of 40 refused, **one readable matching file carries a verdict that authorises
  attaching catalog rows - which `reclaim` later deletes on.** And `HASH_PROOF` samples from
  `present`, so the backstop shrinks exactly when it is needed. A false positive on the dangerous
  side, traded for a false negative on the safe one.

  ## The discriminator

  ```
  present >= PRESENCE_THRESHOLD * len(sample)   -> proceed to the hash proof   (unchanged)
  present + refused >= that bar                 -> UNREADABLE   (the answer is unknown)
  otherwise                                     -> NO_MATCH     (genuinely not this drive)
  ```

  ⚠ **It fires only where the refusals were enough to have changed the answer**, never where the
  sample settles it either way. That is what keeps it from crying wolf over one odd file, and it is
  why the trap is avoided rather than worked around: an unrelated folder has nothing refused, so it
  is still `NO_MATCH`, still filtered, still registers.

  ⚠ **And a cancelled run may not produce it.** `break` leaves the sample part-examined, and *"we
  stopped early"* is not *"the drive would not answer"* - calling that `UNREADABLE` would fabricate
  a verdict out of the user's own interruption.

  ## What each caller says, in each of the three states

  | | matched | nothing matched | **could not read** |
  |---|---|---|---|
  | `_init_drive` | refuses, names the drive | registers | ~~registers silently~~ → **refuses, counts what would not open, names `--force-new-identity`** |
  | `attach_drive` | `blocked_by`, not registered | registers | ~~registers silently~~ → **`blocked_by`, not registered** |
  | `source_repoint` | `PROVEN`/`CONTENT_DIFFERS` | `NO_MATCH`, refuses | refused already - **now says which refusal it was** |

  `source_repoint` was the control and stayed green **unedited**: its diff is 40 insertions, 0
  deletions. Its message previously said *"0 of 0 sampled files matched by content"*, which
  describes a mismatch where nothing was compared.

  ## What the refusal says

  ```
  error: /path could not be read well enough to say whether it is a drive Truestill already knows.
         12 of 12 sampled files would not open, so this folder may be 'Photos HDD'
         with an unreadable mount, or somewhere new. Registering it now could give one library two
         drive ids, and Truestill would then count one copy of your photos as two. Nothing was written.

         If the drive is not fully mounted, or a folder is
         still syncing:            fix that and run again
         If this really is a new place:
                                   re-run with --force-new-identity
  ```

  ⚠ **`_print_adoption_refusal` needed this branch regardless of taste.** With neither a proven nor
  a differing offer it fell through and printed *"already holds the library recorded as ."* - a
  nameless sentence offering `--adopt-existing`, which cannot work because `_init_drive` requires
  exactly one proven match. The new state is exactly that state.

  **The cost is real and is a message, not a dead end**: a genuinely new drive on an odd mount is
  refused, and `--force-new-identity` registers it. Pinned by a test.

  ## ⚠ Two things the tests found that reading did not

  **1. A precondition that could not fail.** The refusal tests skipped silently, because
  `os.stat` on a mode-000 **directory succeeds** - it needs execute on the *parent* - and `glob`
  has to *read* the directory, so it returns `[]` rather than raising. The probe has to be a
  **constructed** path to a known child. Five of eight tests were skipping before this was noticed.

  **2. A mutation survived, and the survival was the finding.** The first cancellation test set the
  flag before the loop began, so `refused` was 0 and the verdict was `NO_MATCH` whether the guard
  existed or not - green for a reason unrelated to the branch it named. §4's **sixtieth member**,
  in a test written to prove a guard. Reaching it needs the cancel to arrive *after* refusals have
  accumulated.

  ## Left alone, deliberately

  `test_an_unreadable_file_is_not_counted_as_proof` classifies an unreadable **hash** as
  `CONTENT_DIFFERS`. That is the same family one stage later - a read that fails is not evidence -
  and it is **not** changed here: the hash stage only runs once presence has already cleared the
  bar, so it cannot produce the silent registration this entry is about. Worth its own look.
