# (ahz) RECOVERING A LOST CATALOG DESTROYS THE NAMES IT IS RECOVERING, AND THE GUARD AGAINST IT IS BLIND.

*Body of backlog entry `(ahz)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahz) RECOVERING A LOST CATALOG DESTROYS THE NAMES IT IS RECOVERING, AND THE GUARD AGAINST IT IS BLIND.** Filed
  2026-08-26 (P106a), measured. **Unrecoverable, and `--discard` makes it permanent.**

  ## 1. THIS IS TERRITORY THE REPO ALREADY CLAIMED, AND THE CLAIM DOES NOT HOLD

  `would_lose` (`decisions.py:1282`) exists for exactly this, and says so:

  > A re-attached drive carries names a rebuilt catalog has never seen; writing over them destroys
  > the only copy, **which is precisely what this feature exists to prevent**.

  [`aci.md`](aci.md) records it as the ruled protection for the rebuilt-catalog case, its deletion
  false positive accepted as the price.

  🔑 **It cannot see this.** `_LOSS_KEYS` keys events on **signature**, not name -
  `decisions.py:1275`. Identical signatures make `of(existing) - of(fresh)` empty
  (`decisions.py:1294`), `would_lose` returns `()`, and the write proceeds. **Nothing anywhere rules
  on a name regression under an unchanged signature.**

  That is [`../../handoff-2026-08-25.md`](../../handoff-2026-08-25.md) §1's first defect class - a
  guard that resolves and does nothing - sitting under the one place it was ruled to hold.

  ⚠ **What `(aia)` closed here, and what it did not** (2026-08-26, so neither reader thinks the
  other letter covers it). `(aia)` owns the *wording*: the `"were older"* sentence is now three
  sentences chosen by `SupersededReason` (`decisions.py:168`), so a **tie** and an **undated**
  document are no longer called "older". **This entry owns the ruling**: in the measured case the
  recovery document genuinely *is* newer, the sentence is now accurate, and the loss still happens.
  Wording it correctly does not stop it.

  ⚠ **And the trip half is ruled the other way, deliberately.** `_trip_key` (`decisions.py:392`):

  > A trip's identity is its DAY SET, not its name. `(ack)` ... **same days with a different name
  > is a RENAME** - the newer name wins - rather than two trips or a conflict to escalate.

  Correct for a human renaming a trip. In recovery the "newer name" is a placeholder the recovery
  run published, and it wins by the same rule.

  ## 2. ⚠ `--discard` CONVERTS A RECOVERABLE STATE INTO A PERMANENT ONE

  **Read this before the fix shapes.** It is the action a stuck user takes: it is the only other
  flag `restore` has, and its help (`cli.py:614`) reads *"DESTRUCTIVE: overwrite the drive's
  decisions with this catalog's"* - which a user whose names came back wrong will read as *"make
  the drive agree with me"*.

  - **Its direction is catalog -> drive** (`cli.py:1564`). It never writes a catalog row, so it
    **cannot** push the real names back: they are on the drive, not in the catalog.
  - Run in this state it does the opposite. It overwrites the drive's document - **the last
    surviving copy of the real names** - with the catalog's wrong ones, stamped `written=now`
    (`cli.py:1407`), making them the newest document anywhere and **unbeatable by any later
    reconcile**.
  - ⚠ **Its guard misreads the situation, because it uses a different identity than the merge
    does.** `_LOSS_KEYS` keys trips by **name** (`decisions.py:1274`); `reconcile_documents` keys
    them by **day set** (`_trip_key`, `decisions.py:392`). So a drive holding *"Grandma's 90th"*
    for the days the catalog calls *"Trip 2019"* registers as a loss, and the preview prints
    *"These sections exist there and NOT here, and will be gone: trips"* (`cli.py:1555`) - which
    reads as a warning about the drive when it is a description of a rename.

  🔑 **Two keyings of one concept in one module is the third instance of one shape in a week**, and
  it is a `ENGINEERING_STANDARD.md` §4 **member candidate**, recorded here rather than claimed:
  *one concept with two or more independent definitions, where a search shaped like the known
  instance cannot see the others.* `(ahu)`'s grep for `set_setting(` was blind to
  `set_local_setting(`; `(ahw)`'s grep for `TIMELINE_RULES` cannot see a string inside SQL; this
  guard keys by name against a merge that keys by day set. In each the definitions agreed **until
  they did not**, and in each the census that would have caught it was written in the shape of the
  instance already known. ⚠ **Proposed, not added** - canon is its own decision with its own
  evidence bar, and filing a rule where nothing enforces it is `(agc)`'s shape.

  ## 3. THE SEQUENCE - evidence for 1 and 2, not the finding

  Measured 2026-08-26 on `5226126`. 353 files from `Input/IV Bangalore`, ext4, 16 cores / 30 GiB.
  One trip and three events named through the app's HTTP routes.

  | document | `written` | names |
  |---|---|---|
  | `dest/` - the user's drive | **14:07:32.372899+00:00** | `Bangalore Dec 2009`, `Morning Market`, `Temple Visit`, `Rooftop Nine` |
  | `rebuilt/` - the recovery copy | **14:08:27.359874+00:00** | `placeholder A`, `placeholder B`, `placeholder C`, `placeholder D` |

  **55 seconds apart, and the event signatures are byte-identical in both** - `562ed6c8291b`,
  `f41e03ca6184`, `51aee3db0d41`. Second restore, verbatim:

  ```
    - 1 trips on dest were older and were not used.
    - 3 events on dest were older and were not used.
  ```

  Five steps, each observed:

  1. Catalog lost. `truestill organize <drive> <recovery> --apply` to rebuild.
  2. That run **registers the recovery folder as a drive**, and the dirty close **publishes a
     decisions document to it**.
  3. `truestill restore <drive>` - all three event names dropped, at the time with a false reason.
     The names are `(ahv)`; the sentence was `(aia)`, fixed 2026-08-26 (`decisions.py:573`).
  4. The user re-names the groups in review. Those names **auto-publish to the recovery drive**,
     now stamped newer than the original.
  5. `truestill restore <drive>` again - the user's real names are reported *"older and were not
     used"* and are permanently outranked.

  **No way out**: `restore ROOT` has only `--db`, `--apply`, `--discard`.

  ## ⚠ DATED CORRECTIONS - 2026-08-26 (P111/P112)

  **§4's *"a field no surface prints"* is FALSE as of `(ahx)`.** It was true when filed, and P107
  closed it: `_print_omissions` loops `fields(ApplyReport)`, `REPORT_FIELD_NOTE` carries
  `conflicting_trips`, the sentence is `actionable=True` so it prints with `!`, it counts into the
  withheld half of the summary, and `test_restore_cli.py` pins it behaviourally.

  🔑 **What survives is narrower and more defensible: the loss happens ONE STAGE EARLIER than the
  field that would report it, so the field never fires.** `_merge_section` runs first and hands
  `_apply_trips` the *placeholder* name; the catalog already holds that placeholder over those
  days, so `holders == {name}` and `_apply_trips` takes the **silent `continue`**. The user gets
  only the `-`-markered "were not used" line. The trip half's silence is in the merge, not in the
  apply - and **there is no `rename_trip`**: every write to `trips`/`trip_days` was enumerated, and
  a trip name is write-once for the life of the row, on both surfaces.

  ⚠ **Option E is dead for THIS sequence, measured.** Widening `_LOSS_KEYS` cannot fire here: the
  drive holding the real names has no `path_hint` (restore writes none), so it reads
  `DriveReach.UNKNOWN` and is skipped *before its document is opened*; and the recovery drive's
  document holds nothing to regress from. The measurement proves it - `dest`'s stamp stayed
  **14:07:32** throughout, so no write to it was ever attempted. **E still lands, for a different
  and worse hole**: if the original drive WERE reachable, today's signature keying returns `()` and
  the save silently *overwrites* the real names rather than outranking them. ⚠ And E must ship with
  a fix to `_discard_to_drive`, which treats a non-empty `would_lose` as **permission to proceed**.

  ## ⚠ STEP 2 SHIPPED 2026-08-26 (P113) - THE NAMED ROOT IS AUTHORITATIVE

  `_merge_section` lets the drive the user named claim its keys **ahead of rank**; other drives
  fill only what it does not carry. **Per KEY, not per section** - per-section authority would let
  the named root answer for decisions it does not hold, discarding every trip another drive has
  that it has never heard of. A mutation proves it.

  **Step 5, re-run end to end and measured.** Recorded when filed:

  ```
    - 1 trips on dest were older and were not used.
    - 3 events on dest were older and were not used.
  ```

  Today, same five steps, recovery document 37 seconds newer:

  ```
       3  events

    ! 3 events on rebuilt were written later and were still not used:
      'placeholder B' -> 'Morning Market', 'placeholder C' -> 'Temple Visit', ...
      The drive you named holds the ones on the right, and a drive you name wins.
      If the newer copy is a change you made on another machine, restore from THAT
      drive instead - this run would replace it.
  ```

  **The three real names come back**, the overruled placeholders are named in the actionable
  register, and the direction is reversed. With the authority reverted, the same run says
  *"3 events on dest were written earlier and were not used"* - the defect, restored.

  ## ⚠ WHAT STILL LOSES, NAMED RATHER THAN IMPLIED

  **Step 2 is not the whole of this entry, and a partial fix on this path must say which part it
  does not cover.**

  - ⚠ **Events cannot be CREATED.** A rebuilt catalog whose `events` table is empty still drops
    every event name at step 3, whichever document wins - `apply_decisions` renames an event found
    by signature and cannot make one. That is `(ahv)`, and the re-cluster-then-match path already
    exists shipped. In the run above, step 3 reported *"2 restored, 3 not restored"*; the names
    only returned at step 5 **because step 3's re-naming had put the rows there first.**
  - ⚠ **Trips cannot be RENAMED.** There is no `rename_trip`; a trip name is write-once for the
    life of the row, on both surfaces. Where the named root's trip name differs from one the
    catalog already holds for those days, step 2 converts a silent supersede into a **loud, honest
    dead end** - `_apply_trips` refuses it into `conflicting_trips`, which now prints. Strictly
    better, and clearly not sufficient.
  - **Step 3 is unbuilt**: `_LOSS_KEYS` still keys events on signature, so a reachable original
    drive can still be *overwritten* rather than outranked - and it must ship with the
    `_discard_to_drive` polarity fix.

  ## ⚠ THE INDUSTRY MODEL, AND MY FIRST READING OF IT WAS BACKWARDS

  Microsoft's default is **NON-authoritative**: a restored replica loses to replication and does
  **not** become the source of truth. **That is today's Truestill behaviour** - the names on the
  drive you restore FROM lose to whatever the surviving copy says. It is the default, not a defect.

  🔑 **What Truestill lacks is the other half: an AUTHORITATIVE restore** - the explicit, opt-in act
  that marks specific data as current and stops replication overwriting it, scopeable to individual
  objects. **`restore <root>` IS that explicit act**: the user typed that path. Step 2 is a
  per-object authoritative restore, and that is a stronger justification than *"the industry
  settled on non-authoritative"*, which is the opposite of what AD does.

  ⚠ **And step 2 inherits the risk AD names**: *you lose all changes to the restore object that
  occurred after the backup.* If a user renamed a trip on a **second machine** after the named
  drive's document was written, the named root will beat that legitimate newer change. **Stated
  here so step 2 does not discover it** - and the report built in step 1 is what makes it visible,
  because naming both values is what lets a reader tell the two cases apart.

  ## 4. THE TRIP HALF IS WORSE, AND WAS NEARLY MISSED

  Events rename on a signature match (`decisions.py:943`). **Trips never rename at all.**
  `_apply_trips` finds every day already claimed by a differently-named local trip, so
  `holders != {None}` (`decisions.py:534`) and the trip lands in `conflicting.append(name)`
  (`decisions.py:550`) - reaching `conflicting_trips`, **a field no surface prints**. Checked:
  `grep -rn "conflicting_trips" packages/*/src` returns its definition and construction only.

  🔑 **The measurement's most reassuring result was an artefact of the setup, not a property of the
  product.** *"The trip came back"* held only because the rebuilt catalog had no trips yet. The
  moment a user names one during recovery, the trip half fails harder than the event half and more
  quietly. **A measurement's good news deserves the same suspicion as its bad news** -
  `handoff-2026-08-25.md` §5's *"suspect your instrument"*, pointed at a pass rather than a failure.

  ## 5. THE RANKING IS CORRECT. DO NOT LOOK FOR A BUG IN THE SORT

  `_ranked` (`decisions.py:245`) does exactly what it documents: `written` descending,
  `drive_uuid` ascending as a deterministic tiebreak. 14:08:27 really is later than 14:07:32.

  🔑 **The defect is that recency is a proxy for AUTHORITY, and a recovery copy breaks the proxy.**
  The recovery document is newer by the clock and **causally older** - it descends from the drive
  it outranks. That is textbook **Last-Write-Wins**, whose documented failure mode is lost updates
  exactly when the timestamp does not track causality.

  ⚠ **The sibling case was anticipated and solved; this one is its inverse.** `_merge_section`
  (`decisions.py:306`) rules *"per decision, never per document"*, because per-document merge
  *"would let a freshly formatted drive - whose empty document is by definition the newest - erase
  a full one."* That answers a freshly-created drive with an **empty** document. This is a
  freshly-created drive with a **populated** one, whose values are derived from the drive it beats.

  **Outside evidence - the same failure in another product**: Syncthing-android #1389, where
  downloaded files take the *download's* modification time and *"wrong modification times are then
  distributed (being the most recent date) to other devices, thus annihilating the original
  information everywhere."*

  ⚠ **A null, reported as a finding.** Searched for an established anti-pattern name for *"the
  restore target becomes a source and clobbers the original"* across the backup literature - Veeam,
  NetBackup, Azure Backup, Kaseya. **There is none.** The failure is named in sync and replication
  (last-write-wins, lost updates) and unnamed in backup - which is why a backup tool's author would
  not find it by looking where they would naturally look.

  ## 6. THE LOSS IS REPORTED IN THE WRONG REGISTER - ⚠ HALF CLOSED BY `(aia)`, 2026-08-26

  As filed: `Superseded` rendered with a leading `-`, the marker used for *"Nothing to do"*, rather
  than the `!` reserved for actionable items - and it **never names the value**, so the user was
  told *"3 events on dest were older and were not used"* and never **which names** they lost. The
  one line that could have alerted them was styled as reassurance and withheld the only detail that
  would make it alarming.

  **`(aia)` closed the register half the same day.** The marker is now derived from
  `RestoreWording.actionable` (`decisions.py:531`) in one place (`cli.py:1457`) rather than typed
  at each site, so a loss can no longer be printed in the "nothing to do" register by accident.
  ⚠ **The value half is still open and belongs to this entry**: `Superseded` carries
  `section, drive_label, count, reason` and no values, so no surface can name which trip or event
  was lost. That is a `Superseded` shape change, not a wording one.

  ## 7. FIX SHAPES - NONE CHOSEN

  | | shape | verdict |
  |---|---|---|
  | **A** | the recovery destination is not registered as a drive | ⛔ **RULED OUT.** `IMPLEMENTATION_STANDARDS.md` §3.1 binds creation on **both** surfaces; `cli.py:2606` rules that an identity minted afterwards *"leaves the run's own files unattached"*; `(aei)` makes destination identity an input to dedup. An opt-out flag was already refused at `cli.py:2552` |
  | **B** | suppress publishing while the catalog is known-rebuilt | ⚠ **PARTLY RULED OUT, and needs a concept that does not exist.** No rebuilt/young/age notion anywhere; `test_catalog_session.py` rules the trigger deliberately coarse and calls the refreshed organize stamp intended; `decisions-on-drive-research.md` states every reachable drive is meant to hold every decision. And `(aci)`/`would_lose` is the already-recorded remedy - B would be a second one |
  | **C** | `restore` reads one root only, behind a flag | ✅ **NOT RULED ON.** The ruling is only *"the named root is read from the PATH, never from a lookup"* (`cli.py:1408`). Reading the others is stated as a **convenience**, justified by *"on a fresh machine that list is simply empty"* - which this scenario falsifies. Constraint: `apply_documents` owns the per-drive loop structurally; a flag must not move it |
  | **D** | creation-date-aware ranking | ✅ **NOT RULED ON, but needs new data.** A per-section override precedent exists - `_merge_confirmations` (`decisions.py:344`) resolves on the row's stamp, not the document's. ⚠ But drive age is **not derivable**: `marker.created` exists (`drive.py:947`) and is never written to the catalog or read during reconcile, and `drives.first_seen` is when *this* catalog first saw the drive, so on a rebuilt catalog it is the rebuild day - **actively wrong in the one case restore exists for** |
  | **E** | widen `_LOSS_KEYS` so a name regression under an unchanged signature is a loss | ✅ **NOT RULED ON.** Repairs the guard already ruled to cover this case rather than adding a mechanism. The evidence points here; it is written down, not chosen |

  ## RELATED

  `(aci)` (the guard this defeats), `(ahv)` (the event names, and its two-step remedy measured not
  to work), `(ahs)` (re-organize as the recovery path), `(ack)` (trip identity is the day set),
  `(aei)`, `(ahu)` and `(ahw)` (the member candidate's other two instances).
