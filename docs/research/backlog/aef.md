# (aef) THE BACKLOG CANNOT ANSWER "WHAT MUST SHIP BEFORE v1", AND 57 OF 64 ENTRIES ARE SILENT.

*Body of backlog entry `(aef)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aef) THE BACKLOG CANNOT ANSWER "WHAT MUST SHIP BEFORE v1", AND 57 OF 64 ENTRIES ARE SILENT.**
  Recorded 2026-08-19, from a state check rather than from a defect. **This is a decision about the
  backlog's SHAPE, not 57 small decisions about entries.**

  ## THE FINDING, AS A PROPERTY RATHER THAN A GAP

  Counted from `BACKLOG.md`'s **Approved - still to build** section: **64 open entries, and only
  seven carry any release marker in their own text.**

  | | |
  |---|---|
  | **blocks a first release, by its own text** | **1** - `(aad)` desktop installers, *"LAUNCH-BLOCKING for the paid product"* |
  | **post-launch, by its own text** | **6** - `(aax)`, `(aaw)` (POST-SOAK), `(aas)`, `(abd)`, `(ll)`, `(r)` |
  | **silent** | **57** |

  ⚠ **So the release question is not stored anywhere. It is RECOMPUTED from judgement every time it
  is asked, which is why it comes out different.** Every catalog-integrity entry is in the silent
  group - `(ady)`, `(aea)`, `(adt)`, `(ads)`, `(adn)`, `(adx)`, `(aed)`, `(aci)`, `(aba)`, `(abe)`,
  `(abf)`, `(abg)`, `(aai)` - and so are the three shell/UI programs, `(adi)`, `(adh)`, `(adj)`.

  `(adz)` is the odd one and does not fit the three buckets: it neither blocks nor defers, it
  **expires**. Its rule holds *until the first release tag*, at which point the entries it justifies
  stop being justified.

  ## THE EVIDENCE THAT DECIDES THE SHAPE: A CONVENTION WITHOUT A GUARD DECAYS

  **Only 23 of 72 entries carry a `Recorded` date.** Nothing enforces it, and it is now at under a
  third. Meanwhile `test_backlog_letters_are_unique`, `test_closed_entries_leave_the_backlog` and
  `test_backlog_references` are all enforced and all hold - the last two written *because* a rule
  that lived only in prose had already been broken.

  ⚠ **The discriminator is not the convention. It is whether a guard runs it.** Any option below
  that is not guarded will read like the `Recorded` date within a month.

  ## THE OPTIONS, WITH COSTS

  **A - a marker on every entry** (`RELEASE: blocks | after | neither`), guarded for presence.
  - *Cost:* 64 classifications now, and every future entry must decide at filing time.
  - *Risk:* the honest answer for most is *"nobody has thought about it"*, and a required field
    turns that into a guess that then reads as authoritative - history reported as state, which is
    `(abg)`'s defect one level up.

  **B - one curated list in `PROJECT_STATUS.md`**, naming the letters that must ship before the
  first tag. Everything else silent by default.
  - *Cost:* one decision, revisited deliberately.
  - *Guardable* by the `test_backlog_references` pattern already proven here: every letter named
    must resolve to an open entry, so a closed or renamed one cannot rot on the list.
  - *Limit:* silence stays ambiguous - *"not on the list"* means both *considered and excluded* and
    *never considered*.

  **C - mark only exclusions**, default unknown.
  - *Cost:* near zero; seven entries already carry markers.
  - *Risk:* the default is "unknown", which is honest and answers nothing.

  ## ✅ RULED: OPTION B (the maintainer, 2026-08-19)

  A curated list in `PROJECT_STATUS.md`, guarded by the `test_backlog_references` pattern, **keeping
  the six existing POST-LAUNCH markers where they are** rather than migrating them.

  **Why A is rejected, and the reason is `(adz)`.** Per-entry markers are **57 judgements about
  users who do not exist**, made at the moment of least information, and `(adz)`'s standing rule
  says that reasoning expires at the first release tag anyway. Filing 57 low-confidence guesses to
  answer one question is a worse trade than making the one question answerable in one place.

  🔒 **B'S HONEST LIMIT, RECORDED SO IT IS NOT DISCOVERED LATER AS A DEFECT: it makes the LIST
  answerable, not the BACKLOG.** Asking *"is `(aci)` needed for v1?"* still returns silence. That is
  the state the project is actually in, and a shape that admits it beats one that manufactures 57
  answers.

  ## ⏳ NOT POPULATED YET, DELIBERATELY

  **The list itself is a ruling the maintainer makes after the first soak**, because the soak is
  what will say which things actually break under real use. Populating it from the backlog as it
  stands would encode today's guesses as the answer - the same mistake in one file instead of 57.
