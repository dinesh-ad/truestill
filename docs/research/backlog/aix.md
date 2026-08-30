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
2b. ✅ **The drive's decisions document** - `authored_decisions` (schema v23), a per-key
   **lease** carrying the value the renamer expects the drive to hold, recorded in the same
   transaction as the name flip and read once per publish. See below. *(P161)*
3. ✅ **The app control** - `/api/rename/{preview,run}`, and the card's `ev-named` branch now
   offers Rename instead of refusing in words. **Preview before commit**, gated in the DOM.
   *(P162)*
4. **The record**, and `(abw)` finding (3) revisited - the *"already-named trip is re-asked"*
   feature question a rename is the answer to.

⚠ **NOT IN SCOPE: `(abn)`'s outside-rename repair.** `rescan.reconcile` already reports a folder
renamed outside as `MovedCopy`, matched by content hash, and `unaccounted` already distinguishes
lost. What it cannot know is **intent** - and `MovedCopy`'s own docstring rules that picking is
what the module refuses to do. **The contribution here is the finding that a coherent whole-folder
move is the highest-confidence repair case `(abn)` will ever have**, and the one worth doing first.

## ⚠ THE HALF STAGE 2 DID NOT CLOSE, MEASURED RATHER THAN PREDICTED - CLOSED IN 2b

> ✅ **RESOLVED 2026-08-30 (P161) BY A LEASE, AND THE GUARD BELOW IS UNCHANGED.** The
> diagnosis in this section stands exactly as measured; what follows it is the fix.

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

## ⚠ STAGE 2b: THE FIX IS A LEASE, AND THE ALTERNATIVES WERE REFUSED WITH REASONS

**The shape of the problem has a name.** A rebuilt catalog holding a placeholder against a drive
holding the real name is a **lost update** - two writers, last-write-wins, and the loser's value
gone with no record it existed. It is sharpened here by **tombstone-free rebuild ambiguity**: a
rebuilt catalog cannot distinguish *"this key was never mine"* from *"this key was deleted"*,
because nothing records absence. `(ahz)` step 3 answered it the only way a lone guard can - refuse
every changed value - which is correct and costs the user their own rename.

🔑 **THE RULING: give the guard the missing fact as a LEASE, never as a force flag.** Git names
the distinction exactly: `--force` *"has really no checking"*, while `--force-with-lease` does
*"an atomic compare-and-swap on the branch you are pushing to, based on the last information you
fetched"*. So `authored_decisions` stores `(section, key) -> expected value`, and the publish
overwrites **only if the drive still holds `expected`**. A name changed on another machine fails
the comparison and survives - which a boolean could not have done.

**Per-key rather than global** is the **field mask** pattern (Google AIP-134/161), where a partial
update names the fields it may touch and an unscoped `force=true` is the anti-pattern. The rename
leases one key: the trip's day set, or the event's signature.

| refused alternative | why |
|---|---|
| a `force=True` argument on `save_decisions_to_reachable_drives` | unscoped and un-valued: it would overwrite a name made on another machine, and every future caller inherits the power |
| an in-memory "I authored this" set | dies with the process. A crash between the flip and the publish would refuse the user's own rename **forever** - the state stage 2 shipped with, made permanent |
| version vectors on every key | the general answer, and the honest cost is documented: Riak's sibling explosion, and a design that *detects* concurrent writes but cannot *resolve* them - it would hand a single-user local product a merge UI it has no user for |
| last-write-wins by timestamp | exactly the lost update this entry is about, with a clock added |

⚠ **THE SELF-IDENTIFYING PROPERTY, AND IT IS WHY THIS BEATS A CALLER FLAG.** The lease table lives
**in the catalog**, so a rebuilt catalog leases nothing and is refused in full - without anyone
having to notice it is a rebuild. Proved end-to-end on scratch: rename, publish, delete the
catalog, rebuild from the drive. The new name came back and the rebuilt catalog's lease was
**empty**. `(ahz)`'s data loss stays unreachable by construction rather than by discipline.

**Written in the same transaction as the flip** (`Catalog.rename_row`), so no interruption can
leave a flipped name with no lease. Apple ships a single-user default of this shape -
`NSMergeByPropertyObjectTrumpMergePolicy`, the in-memory writer's properties winning per property
rather than per object - which is the same per-key scoping arrived at from a different direction.

⚠ **WHAT 2b DOES NOT DO.** The *"restore first"* wording is still the sentence every **other**
caller of that guard gets, and it is still the wrong remedy for a rename - it is simply no longer
reachable from one. Reworded when a second caller needs it, not before.

## STAGE 3: WHAT THE SCREEN DOES, AND THE THREE THINGS THE BUILD FOUND

**Preview before commit**, which is the one pattern every tool that moves files on a rename
shares: Bulk Rename Utility's preview pane *"reveals what new file names will appear before making
any changes"*, Finder shows the new name before you confirm, Perforce's Rename/Move *"is not
complete until you submit the changelist"*. ⚠ **Deliberately NOT a confirmation dialog** - HIG
guidance warns against unnecessary ones, and *"are you sure?"* over an unseen change asks less
than a preview answers. The commit button does not exist until a preview returns clean, and **any
edit to the name withdraws it** - a button left standing after an edit would offer to move the
files the PREVIOUS name planned.

⚠ **THE PREVIEW IS A JOB, AND IT WAS WRITTEN AS A PLAIN REQUEST FIRST.** `plan_rename` reads only
the catalog, so "not a job" looked right and was recorded as a decision. It is wrong: rendering
the new path needs `_resolve_migration_routes`, which **re-reads metadata** for ambiguous labels.
`migration_preview_run` is a job for exactly this reason, its own note naming *"the silent phase
that made events/migrate preview look frozen on a network mount"*.

🔑 **AND SKIPPING ROUTE RESOLUTION WAS A REAL DEFECT, MEASURED NOT PREDICTED.** Without it every
`Camera` row is ambiguous by construction, the conservative default fires, and the rename rendered
`Camera/2015/2015-06/` - **dropping the trip folder entirely**, which is the opposite of what a
rename does. Caught because the fixture used placeholder bytes and the test failed; a fixture of
real photographs is what makes the trip exist at all, and that is now written into both test files
rather than left as folklore.

⚠ **A RENAME LEFT NO RUN RECORD, AND A GUARD FOUND IT RATHER THAN A REVIEW.**
`test_no_service_writes_a_record_without_a_row_here` reported a service that moves the user's
photographs and records nothing. It now writes one through the same `_record_migration` migrate
uses, with the `run_id` `apply_moves` already mints, filed under **`kind="rename"`** - a reader
asking *"what moved my photographs"* has to be able to tell a person renaming a trip from the
layout template changing under everything.

**The card had to learn which row it names.** `existing_name` was looked up by identity - a trip
by its day set, an event by its signature - and renaming is **row-keyed by ruling**. So
`catalog.NamedRow` carries id and name out of ONE lookup and the payload gained `existing_id`. A
screen that showed one card's name beside another's id would move the wrong photographs and look
entirely correct doing it.

⚠ **WHAT STAGE 3 DOES NOT DO.** The control lives on the Trips & events review card, which is
where an already-named trip is visible - there is no rename anywhere else, and no way to rename
from the Drives or Settings screens. `(abw)` finding (3) is still open and is stage 4's subject.
