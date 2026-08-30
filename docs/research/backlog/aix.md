# (aix) A TRIP OR EVENT CANNOT BE RENAMED, SO THE ANSWER IS THE FILE MANAGER.

*Body of backlog entry `(aix)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-30 (P158/P159). **A feature with a design and a staging plan**, not a defect and not
polish. Stage 1 ships with this entry.

## THE PREMISE, VERIFIED FROM CODE RATHER THAN ASSUMED

| claim | check | result |
|---|---|---|
| no rename on any surface | `grep -c "def rename_"` over core · `truestill --help` · `grep rename server.py` | **0 / 0 / 0** |
| a trip cannot be renamed at all | `create_trip` (`catalog.py`) has **no `ON CONFLICT`**; `update_trip_days` says *"`trip_id`, `name` and `slug` are untouched"* | confirmed |
| an event can be, but only by accident | `record_event`: `ON CONFLICT(signature) DO UPDATE SET name = excluded.name, slug = excluded.slug` | confirmed |
| the UI does not offer it | `app.js:3502` renders *"already named - renaming is not available here"*, and `syncEvNamesFromDom` collects `.ev-name` inputs a named card never renders | confirmed |

**So it is unreachable from every surface, which made it latent rather than live** - and is why it
had no entry until now.

## WHY IT MATTERS: THE ABSENCE HAS A DEFAULT, AND THE DEFAULT IS DANGEROUS

Nobody treats renaming as advanced. **Photoshop Elements**: right-click an album → Rename.
**digiKam**: the right-click menu, plus an open pixls.us request (#25771) asking for it in *more*
places from a user doing bulk organizing. **Immich #1775** asks for it so photos are findable
later.

⚠ **A user who cannot rename in the tool renames in their file manager**, which is the one action
that breaks a catalog quietly. In a user's own words (Adobe community, Dec 2023):

> *"Changed file names in Windows File Explorer. The organizer still shows old names. Restarting
> the organizer does not help."*

**Lightroom's Folders panel exists precisely to prevent that** - so *"the folder name and stored
catalog path update together, avoiding the missing-photo problems caused by renaming outside
Lightroom."*

🔑 **And digiKam's failure mode is the one to copy**: *"Failed to rename Album"* when Windows holds
the folder. **A loud refusal, never a divergence.**

## THE RULING: A RENAME IS A FILE OPERATION, AND IT IS MIGRATE-SHAPED

`trips.slug` renders the directory through `layout.py`'s `event_dirname`, so **changing a name
moves photographs**. The machinery already exists in `migrate.py` and must not be duplicated:
`Move`, `migration_journal` written before the move, `_apply_move` (*"idempotent… from whatever
state it is in"*), `resume_migration`, and `migration_runs` for reversal.

**A rename is a migration whose cause is a one-row change rather than a template change.**

⚠ **Refused: a catalog setter with a lazy folder move.** It manufactures a three-way divergence
between the catalog, the folder and the drive's decisions document - and **nothing would detect
it**: `verify` keys on `file_copies.relative`, which a name change does not touch, and `rescan`
never reads a slug.

## 🔑 THE ORDERING, WHICH IS THE WHOLE DESIGN

> open a run → journal every `(sha, old_relative, new_relative)` computed from the **new** slug →
> apply each move → **flip `trips.name`/`slug` LAST** → close the run.

At every interruption point the state is honest: **the name is the old name until every
photograph is at the new path.** A half-moved folder under the old name is recoverable and tells
the truth; a flipped name over half-moved photographs is the *"worse than no rename at all"* case,
and this ordering makes it unreachable rather than unlikely.

**It works because `migration_journal` stores `new_relative` as a PATH.** A template or a slug
reference would invert the guarantee silently, because a resumed run would then need the flipped
row to know where things go. That dependency is recorded **on the schema**, where someone changing
it will meet it.

## NAMING IS IDENTITY-KEYED; RENAMING IS ROW-KEYED

`service/trips.py`'s `ExistingNames` records the asymmetry: a trip is its **days**
(`trip_days.day` is a primary key), an event is its **membership** (`events.signature`). Renaming
by **row id** sidesteps it entirely and leaves `record_event`'s signature semantics untouched.

⚠ **An event whose membership changed since it was named is a DIFFERENT event** by the schema's
own definition - the originally-named row still exists with its original members. *"Rename it"* is
incoherent as stated, so a rename renames **the row that exists**, and the new cluster is offered
a name normally. The surface must say which set it is renaming.

## STAGING

1. ✅ **The plan, read-only** - `migrate.plan_rename`, `RenameRefusal`, `RENAME_WORDING`, a CLI
   preview. Writes nothing. *(P159)*
2. ✅ **Apply** - `migrate.apply_moves` (extracted from `run_migration`, one mechanism two
   callers), `migrate.apply_rename`, `Catalog.rename_row`, CLI `--apply`. **The name flips last**,
   proven by an injected failure AND by a killed process. *(P160)*
2b. **The drive's decisions document** - see below. *(open)*
3. **The app control** - replaces `app.js:3502`'s refusal text. Touches a screen.
4. **The record**, and `(abw)` finding (3) revisited - the *"already-named trip is re-asked"*
   feature question a rename is the answer to.

⚠ **NOT IN SCOPE: `(abn)`'s outside-rename repair.** `rescan.reconcile` already reports a folder
renamed outside as `MovedCopy`, matched by content hash, and `unaccounted` already distinguishes
lost. What it cannot know is **intent** - and `MovedCopy`'s own docstring rules that picking is
what the module refuses to do. **The contribution here is the finding that a coherent whole-folder
move is the highest-confidence repair case `(abn)` will ever have**, and the one worth doing first.

## ⚠ THE HALF STAGE 2 DOES NOT CLOSE, MEASURED RATHER THAN PREDICTED

**The drive's decisions document keeps the old name, and the user is told.** Measured on scratch:
a real rename moved the files, flipped the catalog, and `verify` passed clean - **6 verified, 0
missing, 0 mismatch** - while `.truestill-decisions.json` still said `Holiday`.

`would_lose(existing, fresh)` returns `('trips',)`. That is `(ahz)` step 3 working as built:
`_LOSS_KEYS` counts a **changed** value, not only a missing key, because a drive holding a real
name while the catalog held a placeholder was once silently overwritten.

🔑 **The guard is right and must not be weakened.** It cannot tell *"this catalog is a rebuild
that never knew the name"* from *"the user just renamed it deliberately"*, and **only the caller
knows which**. Supplying that fact is stage 2b, in its own commit - loosening a guard written
after measured data loss does not belong in the same change as the apply path.

⚠ **What is actually wrong today is the REMEDY, not the refusal.** The note reads:

```
note: decisions were not saved to Scratch: this drive names 1 trips differently; restore first
```

**Following that advice would restore the OLD name over the rename.** The sentence is correct for
every other caller of that guard, which is why it is recorded here rather than reworded in place.

⚠ **RESUME'S LIMIT.** `resume_migration` runs from `apply_rename` and `run_migration`, **not from
an ordinary catalog open**. A rename abandoned mid-flight is replayed by the next rename or
migration on that drive; until then the drive holds a partly-moved folder under its old name.
`truestill rescan` reports the moved copies by content hash, so it is **discoverable but not
surfaced**. Filed as a limit, not a gap this stage fills.

## RELATED

`(abw)` (the already-named trip re-asked; finding 3 is the feature question this answers),
`(abn)` (the outside-rename repair), `(ahz)` (whose open residual is *"`rename_trip` is
unbuilt"*), `(agk)` (intent before the irreversible step).
