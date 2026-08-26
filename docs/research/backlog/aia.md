# (aia) RESTORE SAID WHY WHEN IT ONLY KNEW THAT - SIX SENTENCES, ONE WORDING HOME.

*Body of entry `(aia)`, **shipped 2026-08-26** - the closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(aia) RESTORE SAID WHY WHEN IT ONLY KNEW THAT - SIX SENTENCES, ONE WORDING HOME.** Filed and
  fixed 2026-08-26 (P106). The census is its own evidence; there was nothing to rule.

  ## THE CENSUS

  Every sentence `truestill restore` prints, against what the code had actually checked.

  | | sentence | what was checked | verdict |
  |---|---|---|---|
  | 1 | *"its photos have changed"* | only that `event_by_signature` returned `None` | **asserted a cause** |
  | 2 | *"nothing this catalog does not already have"* | only that `applied` is empty - also true when **everything was refused** | **asserted a cause** |
  | 3 | *"were older and were not used"* | ranked lower and disagreed. Ties break on `drive_uuid`, and `_ranked` calls ties *"ordinary, not exotic"* | **asserted a cause** |
  | 4 | *"were older than this machine's"* | the comparison is `>=`; ties count as already-held | **asserted a cause** |
  | 5 | *"These sections exist there and NOT here"* | a set **difference** of identity keys - the catalog may hold some | **asserted a cause** |
  | 6 | *"The drive now matches this catalog."* | nothing. `merge_onto_drive` **preserves** unknown sections, and `test_restore_cli.py` asserts captions survive | **asserted a cause, contradicted by its own test** |

  🔑 **A test pinning any of these would have passed throughout.** Each was a **correct string**
  about a situation nobody had checked - which is why the fix is a structure, not six edits.

  ## THE WORST ONE, MEASURED

  `_restore_documents_for` (`cli.py:1413`) says the command exists for the machine where *"the
  catalog is empty"*. In that case - the designed one - **every** document event misses and the
  sentence is false for all of them. Measured on 353 files: byte-identical, all still `Camera`,
  and the re-derived signatures matched the document exactly. The photographs had not changed.

  ## ONE WORDING HOME

  `RESTORE_WORDING` (`decisions.py:474`), `STOP_WORDING`'s shape: a `Final` dict keyed by
  `RestoreNote`, `RestoreWording` values, and **each entry's comment names what the code checked**.
  A table rather than a derivation, for `migrate.py:160`'s reason - a member added tomorrow raises
  `KeyError` rather than being worded by an `else` nobody wrote for it. Two pure choosers beside
  it, `nothing_to_write_reason`'s shape: `nothing_applied_note` and `unmatched_events_note`.

  ⚠ **CORE'S OWN PROSE WAS SEEDED WITH THE SAME CAUSES, which is why one home is the fix rather
  than five edits.** `ApplyReport.unmatched_events` documented *"so membership changed"*;
  `apply_decisions` commented *"Membership changed, so this is not that event"*; and `Superseded`'s
  docstring **offered a model phrasing** which the CLI had copied verbatim. Fixed at all three, or
  the next surface copies them again.

  ## THE DISCRIMINATOR THAT DID NOT EXIST

  Nothing recorded that the catalog holds **zero** events, so *"no events here at all"* could not
  be worded differently from *"this one group is missing"*. `ApplyReport.events_here`
  (`decisions.py:435`) is `BakePlan.confirmed_anywhere`'s equivalent, fed by
  `Catalog.event_count` (`catalog.py:2642`). With none here the reason **is** knowable and is now
  said; with events here it is genuinely unknown and the wording says so instead of picking one.

  ⚠ **Both arms name the event.** A first draft aggregated the zero-events case to a count - it
  said the knowable reason and **dropped the names**, which are what the user came for.
  `test_restore_cli.py` caught it.

  ## THE MARKER IS DERIVED, NOT TYPED

  `RestoreWording.actionable` decides `!` against `-` in one place (`cli.py:1457`). A real loss
  printed with the marker used for *"Nothing to do"* is reassurance where a warning belongs - which
  is how it read, and what [`ahz.md`](ahz.md) recorded. That half of `(ahz)` closes here; **the
  value half does not** - `Superseded` still carries no values, so no surface can name *which*
  trip or event was lost.

  ## WHICH HALF OF SENTENCE 3 IS WHOSE

  ⚠ **Split deliberately, so neither reader thinks the other letter covers it.**

  - **Here**: the sentence was false on **ties** and on **undated** documents.
    `SupersededReason` (`decisions.py:169`) records which of `_ranked`'s three orderings applied,
    `_why_it_lost` classifies it, and there are now three sentences. An undated document also
    stopped being told so **twice in one output** - once as "older", once by `undated`.
  - **`(ahz)`**: in the recovery case the losing document genuinely **is** older, the sentence is
    now accurate, and the loss still happens. **Wording it correctly does not stop it.**

  ## THE TEST ASSERTS STRUCTURE, AND SAYS WHAT IT CANNOT SEE

  `test_restore_states_only_what_it_checked.py`. **Mechanical and asserted**: the table covers every
  `RestoreNote`; `SUPERSEDED_NOTE` covers every `SupersededReason`; no retracted claim appears in
  either home; both choosers return the right arm; the classification itself is exercised through
  `reconcile_documents`; a lost name prints in the actionable register.

  ⚠ **A human read, and NOT asserted**: whether a sentence asserts a cause **at all**. A regex over
  *"because"* / *"so"* / *"have changed"* was considered and refused - it would **miss** sentences
  5 and 6, which assert causes with no connective, and **cry wolf** on the two clean ones, which
  use *"so"* correctly for a mechanism the code enforces. Shipping it would be a guard-shaped
  object. The comment beside each table entry names what the code checked; keeping the wording
  inside that is review.

  ## FIVE MUTATIONS, AND TWO OF THEM FOUND REAL GAPS

  | | mutation | first result |
  |---|---|---|
  | 1 | put the causal claim back into the table | ⚠ **SURVIVED.** The forbidden-phrase guard read `cli.py` only; the sentence had moved to core and the guard had not. **A guard shaped like the old location cannot see the new one** - `(ahu)`'s and `(ahw)`'s shape a third time. Widened to both homes, then caught |
  | 2 | an enum member with no wording | caught |
  | 3 | `_why_it_lost` returns `OLDER` always | ⚠ **SURVIVED.** Asserting only that the three sentences *differ* never checked that the right one is *chosen*. A behaviour test through `reconcile_documents` was added, then caught |
  | 4 | drop the `events_here` discriminator | caught |
  | 5 | force every marker to `-` | ⚠ **SURVIVED**, so the claim that `(ahz)`'s register half was closed was unproven. Asserted on real CLI output, then caught |

  ## RELATED

  `(ahz)` (the recovery inversion - the ruling this wording cannot fix), `(ahv)` (restore cannot
  create an event), `(ahx)` (three report fields printed by nobody - still open), `(ahc)` and
  `(ahd)` (the wording-home precedents), `(aci)`.
