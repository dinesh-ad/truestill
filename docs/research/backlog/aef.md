# (aef) THE BACKLOG CANNOT ANSWER "WHAT MUST SHIP BEFORE v1", AND 57 OF 64 ENTRIES ARE SILENT.

*Body of backlog entry `(aef)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aef) THE BACKLOG CANNOT ANSWER "WHAT MUST SHIP BEFORE v1", AND 57 OF 64 ENTRIES ARE SILENT.**
  Recorded 2026-08-19, from a state check rather than from a defect. **This is a decision about the
  backlog's SHAPE, not 57 small decisions about entries.**

  ## THE FINDING, AS A PROPERTY RATHER THAN A GAP

  Counted from `BACKLOG.md`'s **Approved - still to build** section: **64 open entries, and only
  seven carry any release marker in their own text.**

  ⚠ **Re-counted 2026-08-22: 81 entries, still 7 matches.** The 2026-08-19 figures above are kept
  as the dated measurement they were - the table below is that measurement, not a live reading.
  ⚠ **And this is the entry's own thesis biting it**: a prose count went stale in three days and
  was quoted as current in `PROJECT_STATUS.md` until it was 17 out. So the number is a command
  from here on, not a figure, and one of the seven matches is this entry's own title:

  ```
  sed -n '/^## Approved - still to build/,/^## Settled technical stances/p' docs/BACKLOG.md \
    | grep -cE '^ *- \*\*\([a-z]+\)'
  ```

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

  ## ✅ BUILT 2026-08-22 - THE MECHANISM, AND THE LIST STAYS A RULING

  `PROJECT_STATUS.md` §2b carries **THE RELEASE LIST**, guarded by
  `test_the_release_list_is_answerable.py`. What shipped is the *shape*; what did not, on this
  entry's own instruction, is a populated list.

  🔑 **THE STATE COLUMN IS DERIVED, NEVER TRUSTED.** Every letter is resolved against
  `BACKLOG.md` and `SHIPPED.md` and compared with what the row declares, so **a letter that ships
  without the row changing is a red test.** That is the exact class the 2026-08-22 whole-backlog
  re-read found and nothing automatic could see - `(abo)` open for two weeks after shipping,
  `(ach)` for thirteen days, both closed by commits naming a **different** letter, so the closure
  gate was blind by construction. On this list that failure is a release plan blocking on finished
  work.

  **Five assertions, four mutations, all caught**: a gate that opened, a letter that exists
  nowhere, a state the guard does not understand, and a reshaped row the parser would otherwise
  read as an empty list (§4's fifty-second member, and the one that matters most here because the
  subject is a markdown table).

  ⚠ **SEEDED WITH ONE ROW, AND THE SHORTNESS IS THE RULING BEING HONOURED.** `(aad)` is on it
  because the backlog's own text calls it *"LAUNCH-BLOCKING"* - not a judgement, its own words.
  Nothing else was added, because this entry rules that the list *"is a ruling the maintainer
  makes"* and that populating it from the backlog as it stands *"would encode today's guesses as
  the answer - the same mistake in one file instead of 57"*. **The mechanism now exists so that
  ruling has somewhere to land and cannot silently rot once it does.**

  ⚠ **B's honest limit is restated in `PROJECT_STATUS.md` where a reader meets it**, not left
  here: this makes the **list** answerable, not the **backlog**. *"Is `(aci)` needed for v1?"*
  still returns silence.

  ## ⏳ NOT POPULATED - BUT NO LONGER BLOCKED (re-ranked 2026-08-22)

  **The list itself is a ruling the maintainer makes after the first soak**, because the soak is
  what will say which things actually break under real use. Populating it from the backlog as it
  stands would encode today's guesses as the answer - the same mistake in one file instead of 57.

  ⚠ **THAT CONDITION FIRED ON 2026-08-20 AND THIS ENTRY DID NOT MOVE FOR TWO DAYS.** Four soaks
  have now run; they produced twelve entries and all twelve are closed. The evidence this was
  waiting for exists. It is the maintainer's ruling to make and nothing blocks it.

  ## ⚠ THE PATTERN, RECORDED HERE BECAUSE THIS ENTRY IS ABOUT IT AND WAS AN INSTANCE OF IT

  **A deferral whose condition nobody re-reads is indistinguishable from one that never expires.**
  Both look like a line in a list saying *"later"*; only re-reading the condition separates them,
  and nothing in this repository re-reads conditions.

  Measured on 2026-08-22, in one pass over the 80 open entries:

  | what was found | count |
  |---|---|
  | entries **already closed** by work that named no letter | **3** - `(ace)`, `(aak)`, `(abi)` |
  | deferrals whose **gate had opened** unnoticed | **2** - `(aaw)`, and this entry |
  | entries whose **title overstates** what remains | **9** |

  ⚠ **All of it was found by READING, none by anything automatic**, and that is the finding rather
  than the numbers. The closure gate keys on a commit message saying `Closes (xyz)`, so it sees a
  letter leaving on purpose and is structurally blind to the three cases above: work that closes an
  entry without naming it, a condition that expires on the calendar, and a title that ages past its
  body. **This entry was filed because the backlog cannot answer *"what must ship before v1"*. It
  turns out it also cannot answer *"is this still true?"*, which is the cheaper question and the
  one that rots first.** Whatever shape option B takes should carry a re-read date, not only a
  release marker - a marker says whether an entry matters, and says nothing about whether it is
  still real.

  ## ⚠ THE PASS ITSELF, RUN 2026-08-22 - AND IT IS THE ARGUMENT FOR A CADENCE

  Ruled by the maintainer and run once, properly: **every open entry re-read against current
  code**, asking one question per entry rather than re-auditing what it says - *is its named cause
  already closed, is its evidence still reproducible, does its remedy still make sense given what
  has landed.* 77 entries.

  **What it cost.** Three mechanical passes and then reading. The mechanical half is cheap and
  reproducible, and it is worth writing down because it is not what found the defects:

  ```sh
  # 1. do the entries' code citations still resolve?
  # 2. which entries already cite the letters that shipped since?
  # 3. which bodies predate the work that could have moved them?
  git log -1 --format=%ad --date=short -- docs/research/backlog/<letter>.md
  ```

  ⚠ **All three came back nearly clean, and the pass still found eight things.** Only six entries
  cited a file or symbol that had vanished, and most of those were prose. **The mechanical passes
  are a filter, not a detector** - what they cannot see is an entry whose every citation still
  resolves and whose *conclusion* stopped being true, which is every finding below.

  | found | |
  |---|---|
  | **closed in fact**, entry still open | **2** - `(abo)` (2 weeks), `(ach)` (13 days) |
  | a **consequence** closed inside a live entry | **1** - `(abd)` item 3, by `(aei)` |
  | **diminished** - premise moved under it | **4** - `(acc)`, `(aau)`, `(aeg)`/`(aeh)`, `(act)` |
  | a **shipped invariant carried to one of two surfaces** | **1** - `(afu)`, from `(afl)` |

  🔑 **NOT ONE OF THESE WAS REACHABLE BY ANY GUARD THIS REPO HAS OR COULD WRITE.** Each closing
  commit was correct and each named the letter it was working on:
  `8af88dc` is `fix(core):` and names none; `b1d52a3` correctly declares `(abx)` and knows nothing
  of `(ach)`; `e20dbf5` declares `(aei)` and knows nothing of `(abd)`. The closure gate keys on a
  commit **declaring a letter**, so it is blind by construction to work that closes an entry
  *someone else filed*. That is not a gap in the gate - it is the gate's subject being a different
  question.

  ⚠ **`(abo)` is the sharpest, and it is not a stale document.** `IMPLEMENTATION_STANDARDS.md` §8
  has read *"Closed 2026-08-07 at cache schema v3"* since the day it shipped, while `BACKLOG.md`
  carried the entry as open work. **Both files were current.** They answered opposite questions
  about one thing, and the 2026-08-01 split that created `SHIPPED.md` exists precisely so those
  two questions live in two files - which is what let them disagree without either being wrong.

  **So the cadence is the deliverable, not the list.** A re-read is the only instrument that has
  ever found this class; it costs one session; and the interval that matters is not a calendar one
  but **after a burst of closures** - this pass followed twenty entries shipping in three days, and
  every finding traces to one of them. ⚠ **Option B should therefore carry a re-read date per
  entry, not only a release marker**: a marker says whether an entry matters and says nothing
  about whether it is still real, and *still real* is the cheaper question and the one that rots
  first.

  **The precedents this pass was ruled from**, all found the same way and none by tooling:
  `(adt)`'s cause closed by `(adu)` three days after filing with neither citing the other; `(vv)`
  half-shipped by `(aaw)`; `(aeo)` shipped four hours before it was ranked fifth on a build list;
  `(aac)` residue 3 closed by `(aev)`. Four before this pass, eight during it.
