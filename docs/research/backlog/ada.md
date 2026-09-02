# (ada) THE BACKUPS SCREEN NOW PUTS STATE BELOW THE FORMS, AND A ONE-COPY WARNING CAN FALL BELOW THE FOLD.

*Body of backlog entry `(ada)`, under **Real, but conditional**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ada) THE BACKUPS SCREEN NOW PUTS STATE BELOW THE FORMS, AND A ONE-COPY WARNING CAN FALL BELOW
  THE FOLD.** Split out of `(acd)` 2026-08-11 when that entry moved to `SHIPPED.md`. `(acd)` fixed
  a control that moved under the pointer by rendering `#drives-list` below every control; the cost
  was accepted at the time and is recorded here rather than left inside a closed entry.
  - ⚠ **CORRECTED 2026-08-12: THE PREMISE BELOW WAS ALREADY FALSE WHEN IT WAS WRITTEN, AND THAT
    MATTERS MORE THAN ANYTHING THAT MIGHT BE BUILT FOR IT** - a defect resting on a false premise
    gets re-read and re-proposed by whoever finds it next.
    - *"It now points nowhere"* is **wrong**. The banner carries `data-risk-action="copy"`, and
      `app.js` wires it to `$("bk-source").scrollIntoView({block: "center"})`. **The action works.**
    - Its prose reads *"Copy your library to another drive **above**"*, which **became true** when
      `(acd)` moved the forms above it. The sentence is correct as written.
    - **The user is not unwarned, they are inconvenienced**, and the difference is the whole size
      of this item. The rail's custody strip carries at-risk state (`custody-pips` toggles
      `at-risk`) at **every scroll position**, so the warning is on screen permanently - just in a
      different place from the remedy.
  - **What is genuinely left, measured rather than inherited:** at 1280x800 with one drive, the
    banner's top is at **1035px against an 800px viewport**, so it is below the fold. Adjacency,
    not absence.
  - **What was traded:** the Backups pass deliberately put state ABOVE remedy so the at-risk banner
    pointed down at the copy form. The forms now come first, and the banner renders **inside**
    `#drives-list`, so a user whose files are in only one place meets two forms before it.
  - **Why it was accepted:** a control that cannot be reliably clicked is worse than one met before
    its context. That reasoning holds and is not being reopened here; what is filed is the residual.
  - ⚠ **`(abg)` must re-price this rather than inherit it.** It will put more state into exactly
    this region, and the ordering was chosen against a defect that no longer exists.
  - **NOT REORDERED while closing `(acw)` 2026-08-12, on this entry's own reasoning.** Choosing an
    arrangement now - against a defect that no longer exists, for a region whose contents `(abg)`
    is about to change - is the mistake the line above warns of. `(adg)` is filed against the same
    constraint.
