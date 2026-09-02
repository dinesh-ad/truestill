# (adg) THE VERIFY RESULT BLOCK MOVES `#bk-preview` BY +92.4px - a bigger mover than `(acw)`, and it cannot be reserved.

*Body of backlog entry `(adg)`, under **Real, but conditional**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adg) THE VERIFY RESULT BLOCK MOVES `#bk-preview` BY +92.4px - a bigger mover than `(acw)`,
  and it cannot be reserved.** Measured 2026-08-12 while closing `(acw)`, which had listed it as
  *"Not covered here and worth the same look... Unmeasured."* Now measured.
  - **The number:** writing a realistic finished-verify card into `#verify-result` moves
    `#bk-preview` **+92.4px**, against the 17.4px at which a centre-aimed click leaves the button.
    That is three times `(acw)`'s worst case.
  - **`(acw)`'s fix does not reach it and could not.** A hint is a bounded string, so bounding it
    made the reserve exact. A verify result is a **card listing problems** - unbounded by
    construction, exactly like `#drives-list` in `(acd)`, which is why that entry moved the region
    instead of reserving it.
  - ⚠ **The only fixes available are ones deliberately refused for `(ada)`'s reasons.**
    `#verify-result` is in card 1 and `#bk-preview` is in card 2, so moving state below its
    control means reordering the two cards - and `(ada)` says **`(abg)` must re-price this region
    rather than inherit it**, because it is about to put more state there. Choosing an arrangement
    now, against a region whose contents are about to change, is the mistake that entry warns of.
  - **Harm is lower than the number suggests and that is stated rather than assumed:** the block
    lands when the user has just clicked *Check now* and is reading the outcome, not reaching for
    *Preview copy* on the card below. Same argument `(acw)` accepted for the create-failure state.
  - **Do not fix this before `(abg)`.** File it against that work.
