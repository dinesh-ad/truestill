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
