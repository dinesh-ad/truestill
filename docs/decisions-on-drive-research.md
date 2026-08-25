# Decisions on the drive: surviving a lost catalog

> **Letter reallocation, 2026-08-10.** The items this document cites as `(abw)`, `(abx)`, `(aby)`
> and `(abv)` are now `(acg)`, `(ach)`, `(aci)` and `(ack)`. Those four letters had each been
> assigned twice -
> once on 2026-08-08 and again during this work - so the citations below had stopped resolving.
> The 2026-08-08 entries keep the letters, per `BACKLOG.md`'s rule that a letter is a permanent
> identifier. The pointers are corrected rather than the findings; nothing about what was
> investigated has changed.

> **LIVE DESIGN, not a frozen record. Status as of 2026-08-09.**
>
> **Built:** the document itself (`truestill_core.decisions`) - the dataclass, the serialiser,
> the forward-compatible parser, the catalog gather and apply, an atomic drive write, and the
> multi-drive save with its read-merge-replace and its upgrade gate
> (`save_decisions_to_reachable_drives`, `ensure_decisions_on_drives`).
>
> **Restore shipped 2026-08-09: `truestill restore <root>`.** Preview by default, `--apply` to
> act, typed word `restore`. Works with an empty catalog and no registered drives, which is the
> whole case: the drive is found by the path the user typed, never by a catalog lookup.
> `--discard --apply` is the destructive branch, word `discard`.
>
> **Wired since 2026-08-09.** `catalog_session.open_catalog` is how both surfaces open a catalog -
> all **56** sites, 15 in the CLI and 41 in the app - and it saves the decisions when the work
> finishes, plus once on the first run after upgrading. So documents do now reach drives in
> ordinary use.
>
> **Discoverability, 2026-08-09:** both CLI drive screens and the app's drive card now say what a
> drive is carrying, how old its copy is, when it is behind, and when a save to it failed - which
> closes job 1b's app gap. `(acc)` is corrected in `BACKLOG.md`: the listing was the wrong place
> for the lost-machine case, because it iterates zero rows on a rebuilt catalog.
>
> **NOT built, and nothing here should be read as claiming otherwise:** the app has **no restore**
> - it can say a drive is carrying decisions, and the command to run is a CLI one - and `(acg)`
> album membership is still not carried.
> `(acc)` in `BACKLOG.md` said "Stages 1-3 landed" and was corrected on 2026-08-09 for exactly
> this reason - a status line that claims more than the code is the error this header exists to
> avoid.
>
> Moved out of a plan file in a home directory on 2026-08-09. A plan file does not survive a new
> machine, which is the failure this whole feature is about; `docs/ui-inventory.md` was lost twice
> that way. Precedent for a design record that predates its build:
> [`default-layout-research.md`](default-layout-research.md) - read its header first.

## The problem, and why storage was never it

A catalog can be lost: machine formatted, disk died, file corrupted. The photos survive on the
user's drives; **the decisions do not.** Nothing on disk knows "Wayanad" - a human typed it.

Two findings from the external research are load-bearing:

- **A hosted backup is not the answer.** Adobe has servers, a subscription and the photos, and
  still told a user their catalog was gone: recovering edits and ratings "is not something we can
  do today."
- **The backups Lightroom already takes failed for DISCOVERABILITY, not storage.** Users could not
  find them, believed weekly backups existed when the newest was months old, and found zipped
  files with undecodable names in an obscure folder. **A server would not have fixed one of those
  threads.** That is the design brief: obvious that it exists, obvious how old it is.

**Out of scope, decided rather than deferred:** no server, no hosted catalog, no upload. The
catalog holds GPS and timestamps - personal data under GDPR and a location history in practice -
so "we only take folder names" would have been false.

## What content identity already buys, and it is a differentiator

**Confirmed in code.** `rescan.py:21` defines UNACCOUNTED as *"a record whose path is empty and
whose content is nowhere on this drive"*, `:96` hashes *"the files not at a recorded path"*, and
`dedup.py:113` looks up `self._by_sha`. **Identity is content, never path.** The Lightroom user
who had to relink 4,000 renamed photos one at a time would, here, have them reported as MOVED by
a single `rescan`. Worth stating in the product, not only here.

## What goes in it

**Human decisions only.** Everything else - hashes, dates, GPS, camera and paths - is recomputable
from the files, and is most of what makes the catalog 6.4 MB.

⚠ **THIS SAID "categories" TOO UNTIL 2026-08-25, AND A MEASUREMENT FALSIFIED IT.** Rebuilding a real
organized library from its own files returned **identical dates for 1,127 of 1,127 files and a
different CATEGORY for 3 of them** (`Camera` -> `Saved`, so a different folder). The cause is inside
this product: `naming.py:49` renames to `%Y%m%d_%H%M%S_<original>`, and every name rule in
`categorize.py` is `^`-anchored, so the operation that files a photo destroys the pattern the
categoriser reads. It bites exactly the files with **no capture metadata** - the ones that had only
their filename to go on.

**Corrected in place because this document is a live design, not a record.** The line is repaired
rather than annotated, and the finding it rests on is `(ahr)`; the original name survives as a
suffix, so categories become recomputable again once the categoriser knows its own rename format.

```
drive        uuid, label, notes
settings     layout templates and UI prefs - NOT path hints (see privacy)
trips        name, slug, start, end, and the trip's own days
events       name, slug, start, signature
skipped      dismissed cluster signatures
dates        sha256 -> corrected captured_at, confirmed_by
albums       name (membership NOT yet carried - see (acg))
```

**Corrections to the original list, from the code:** there is **no duplicate-resolution table** -
dedup outcomes are implicit in what was copied and are recomputed by hashing, so there is nothing
to save. And four things were missing: `date_confirmations` (the least recomputable entry in the
catalog - re-reading the file reproduces the wrong answer the human corrected), `skipped_clusters`
(lose them and every declined question is asked again), `albums`, and `files.event_id`.

## Identity has to travel inside the row it identifies

**Events: membership travels as a signature, never as a list.** `events.signature` is already a
SHA-256 over its sorted member SHA-256s, so a restore re-clusters and matches. Identical
membership reproduces the signature and the name re-attaches; a mismatch means membership changed,
which is exactly when the name must **not** be auto-applied.

**Trips: the same rule, learned the hard way.** The original design said *"trips need no
equivalent: they are keyed by day, and `trip_days` is already tiny."* That was the assumption that
failed. `trip_days` maps a day to `trips.id`, and **a rowid is meaningless on a machine that has
never seen this catalog** - the document carried a mapping no reader could resolve, so a restore
gave the first trip every other trip's days. `(ack)` in `SHIPPED.md` has the full record; the fix
is that a trip carries its **own days**, which works because `trip_days.day` is a primary key, so
days are disjoint across trips and a day list identifies a trip exactly.

**The general rule, and it is the one to apply to albums next:** a key that only means something
inside this catalog cannot be the thing that carries identity out of it. `(acg)` records that
`file_albums` is `PRIMARY KEY (file_id, album_id)` - both rowids - so album membership must travel
as sha256s when albums are built.

## How big - measured, not estimated

| approach | size |
|---|---|
| enumerate every event member (2,695 files) | **221-266 KB** |
| **signatures only (chosen)** | **~2 KB** |
| the real catalog's decisions, as written today | **1,353 bytes** |

Against a **6,365,184-byte** catalog: two hundredths of one percent. Enumeration is the only thing
that could have made this megabytes, and the signature removes it.

**The 1,353 is smaller than the 1,508 measured before `(ack)`, while carrying strictly more.**
Dropping the duplicate top-level `trip_days` map more than paid for per-trip day lists: **removing
the second representation was cheaper AND correct.** Two representations of one fact can disagree,
and the one that would have won was the one that caused the defect.

## Where, and in what format

**`.truestill-decisions.json`, beside `.truestill-drive.json` at the drive root.**

**Beside, not inside.** The marker is identity: tiny, stable, read on every reach check, and
already handling a legacy filename (`IMPLEMENTATION_STANDARDS.md` §3.1). Growing it would put a
churning document in the path of every drive detection.

**JSON, indented, sorted keys** - it must be readable in a text editor when Truestill is gone,
which is the whole point. Carries a `written` timestamp and a `format` version. Written
**atomically** (temp in the same directory, flush, fsync, `os.replace`): a truncated file at the
right path is worse than no file, because it looks like a backup.

## The write is a read-merge-replace, never a write

Two ways a write to a drive can destroy the thing it is backing up, both found while building the
save and both closed there.

**1. The unknown-section hole.** `to_document` carries unknown sections back out of a `Decisions`
that came **from a document** - but the trigger's object comes from `gather_decisions`, and the
catalog has never held those sections, so its `unknown` is empty. A user downgrades, restores,
renames one trip, the trigger fires, and the newer version's captions are deleted **by the code
written to preserve them**. Preserving on write-back is not preserving on write. The save reads
what is at the root first and carries its unknown sections forward.

**2. The same rule, applied to sections we understand.** A re-attached drive carries names a
rebuilt catalog has never seen - that is the lost-machine case, and job 1 ships before restore
does. Writing this catalog's decisions over them destroys the only copy. So a write that would
lose `trips`, `events`, `skipped_clusters`, `date_confirmations` or `albums` **does not happen**
and is reported instead. `settings` is deliberately not compared: UI preferences churn per machine
and per version, so a difference there is not evidence of another catalog's work.

**The one false positive, recorded rather than hidden:** a decision the user **deleted** locally
still sits on the drive, so the write refuses until a restore reconciles the two. Reported, not
guessed at - `(aci)`. Guessing which side is intentional is how the other direction loses data.

**An unreadable document is never overwritten either.** Half a JSON file is still someone's names
and a human can often recover them; replacing it because we could not parse it turns a damaged
copy into no copy.

## Where the trigger fires, and why not at the call sites

**One choke point, found one layer below where it was being looked for.** `Catalog` has exactly
one `_tx()` and all eight decision-writing methods go through it, so "did anything change?" is one
line rather than 56 judgements. `catalog_session.open_catalog` reads that flag and saves on a
**clean exit only**.

**The flag is "wrote anything", not "wrote a decision", deliberately.** Telling them apart means
maintaining a list of which writes count, and the day someone adds a decision table and forgets
the list, the drive copy goes quiet with nothing saying so. A refresh after `organize` costs about
a kilobyte and keeps the `written` stamp current, which is what the staleness line reads.

**Not in `Catalog.__exit__`, and the reason is a safety property rather than taste.** Storage does
no drive I/O - but the sharper point is that ~1,200 tests open catalogs, so a save fired from
`Catalog` would fire in all of them. Keeping the trigger in the session wrapper means **tests use
bare `Catalog(...)` and cannot write to a drive at all**. §4 asks for impossible rather than
unlikely, and this one **fell out of the design instead of being remembered** - which is worth
more than a rule someone has to keep in mind.

**Pinned by `test_catalog_opens_go_through_the_session.py`**, which parses every surface module and
fails on a direct `Catalog(...)`, following `test_app_core_import_boundary.py`'s shape including
the half that rots: an allow-list entry for a call that no longer happens also fails. The
allow-list is empty, and it stayed empty on the first attempt - the staleness check refused the
one entry written for it.

## What a restore does with a NEWER document

Decided rather than left to fall out of the code, and it honours `FORMAT_VERSION`'s existing
contract rather than inventing a second rule: *bumped only when a reader must REFUSE.*

- **`format == 1` carrying unknown sections** (an additive newer version): restore everything
  known, leave the rest untouched, and **say what was not touched in the user's terms** - "this
  drive also carries captions, which this version does not understand and has not changed."
  Silence would read as a complete restore.
- **`format > 1`**: refuse, preserve the file, and **name the version to run**. A refusal without
  a remedy is the stranded-names failure this feature exists to prevent.

**Built 2026-08-09, and until then NOTHING READ THE FIELD AT ALL.** `FORMAT_VERSION` was written
into every document and no code path ever read it back, so the rule above existed only as prose.
**The write side was the dangerous half:** a `format: 2` document was read, its unknown sections
carried forward, and its **known** sections overwritten by an older reader - the newer version's
trip names lost while the sections we could not understand survived, which is exactly backwards.
That was live from the day the save shipped.

The gate lives in `read_decisions`, which both the save and the restore go through, so one check
covers both paths. A refused document produces `SaveOutcome.NEWER_VERSION` - a separate member
rather than `FAILED`, because nothing is wrong with the drive and the remedy is an upgrade rather
than a repair, and one field standing for two situations that need opposite words is `(ach)`.

*Missing reads as current*, the same way a missing section reads as empty: a hand-edited document
is not evidence of a newer version. *A non-numeric `format` is refused* rather than crashing -
`int("banana")` raises, and this module's whole contract is that it does not.

## Privacy - and there was a real finding

**`settings` held full local paths including the username.** Shape only - the real values are not
reproduced here, and `test_no_incidental_naming` refused a draft of this document that did, which
is the guard working on the very page that argues for it:

```
path_hint.drive.<uuid>  /home/<username>/<library folder>/Output
path_hint.drive.<uuid>  /home/<username>/<cloud mount>/<an encrypted folder>/<drive name>
```

**Excluded, by prefix, in the gather rather than only in the serialiser.** They would put a
username, a folder layout and the existence of a Vault onto a drive the user may lend or
sell, and they are useless on another machine. The gather also reads column-by-column rather than
`SELECT *`, so a column added to `files` or `settings` later cannot arrive on a drive by default.

**Stated honestly:** the SHA-256s are fingerprints. They cannot reconstruct an image, but they can
confirm whether a specific known file is in the set. Set against the photographs sitting in the
same folder, **nothing in this file is more sensitive than what it sits beside** - with the single
exception of the path hints, which is why they go.

## What this does NOT solve

- **It is not a backup of photographs.** Lose every drive and this restores nothing.
- **It does not survive losing all drives**, by construction - it lives on them.
- **It does not restore a partial catalog.** It restores decisions onto a catalog rebuilt by
  scanning; a drive that has never been scanned still needs scanning.
- **It cannot recover decisions made before it ships.** The 395 Morrowkeep names are not covered.
- **It does not make custody honest.** That is `(abg)`, untouched by this.
- **It will not help a user who never registered a drive.**

## Open work, and the findings that shape it

- **`(acc)`: nothing that touches a drive would notice the file.** `drive.reach_of` reads only the
  settings path hint and the marker - it never looks at drive contents, which is why it is cheap
  enough for every listing - and `rescan`'s walk prunes dotfiles into a skipped census group. The
  smallest honest fix is a **sibling `stat` where the marker read already happens**, not a wider
  `reach_of`: its cheapness is the feature.
- **The upgrade case.** Existing users have decisions in the catalog and no drive copy. A trigger
  of "after a decision changes" protects nobody until they next rename something, and **the user
  most at risk is the one with a finished library who has stopped naming things.**
- **The staleness line.** *"Decisions saved here 9 August"* on the drive card and in `drives`
  output, and a plain sentence when a reachable drive's copy is older than the catalog's newest
  decision. That single line is the entire lesson from the Adobe threads. Not a modal: a one-off
  notice that must be dismissed is a worse version of Lightroom's weekly prompt.
- **Disagreement, when restore is built.** Decisions for files a drive does not contain are
  **kept** - a trip name is not owned by the drive that happens to hold a copy. Event names
  re-attach only where a re-clustered signature matches; the rest are reported as needing review.

## Reconciling several drives (built 2026-08-09)

**Newest wins PER DECISION, never per document**, and that distinction is the whole design. "Take
the newest document's sections" is the obvious implementation, and it is how a freshly formatted
backup drive - whose empty document is by definition the newest - erases a full one. Pinned by a
test that plugs a blank newest drive in beside a full old one and asserts nothing is lost.

**`date_confirmations` is the exception.** Everything else resolves on the document's `written`
stamp, because that is when the drive last heard about it. A corrected date resolves on its own
**`confirmed_at`**: a drive written last week can carry a correction a human made today on
another machine, and it is the only decision with no second source, so resolving it by document
stamp discards it silently. That is the first test in the file, written before the exception
existed and watched to fail.

**A trip's identity is its day set** (`(ack)`), so the same days under a different name is a
**rename** - newest name wins - rather than a conflict.

Three cases decided rather than left to fall out:

| case | rule | why |
|---|---|---|
| same `written` on two documents | lower `drive_uuid` wins | one save writes to every drive with one stamp, so ties are the *ordinary* case; argument order would be dict order wearing a different hat |
| no `written` at all | participates, sorts last | hand-edited or truncated, it is still someone's names - but it cannot be trusted to overrule a dated document, so it supplies only what nothing else has |
| a document that is empty | supplies nothing, overwrites nothing | falls out of resolving per decision rather than per document |

**The loser is reported, never discarded** - `ReconcileReport.superseded` carries section, drive
label and count, so a surface can say *"3 trip names on Backup B were older and were not used"*.
A silent winner is the same defect as a silent skip. **Identical copies are not reported**: one
save writes the same document to every drive, so most reconciles see several, and calling each a
loser would bury the one real disagreement in a list of non-events.

**Settings are the one section whose disagreements are not reported**, because UI preferences
churn per machine and per version - the same reason the write-side loss guard ignores them.
*Which is why the precedence itself needs a test:* a section nothing reports on is a section
where a reversal is invisible to every other signal in the system. That gap was found by a
mutation, not by a failure.

## Applying it: what came back, and what did not

**Two single-meaning fields where there was one** - `(ach)`, closed:

| field | meaning | what the user does |
|---|---|---|
| `already_newer_locally` | this catalog holds a newer form of that decision | nothing; the drive's copy was correctly ignored |
| `awaiting_content` | this catalog has never scanned the photo it belongs to | plug in the drive that holds it, scan, re-apply |

They shared one field and `dict.fromkeys` then collapsed them, so a restore hitting both produced
**one indistinguishable line** for two situations needing opposite words. Counted rather than
named, so a surface can say *"12 corrections are waiting for photos this catalog has not scanned
yet"* - a restore that reports 40 applied and stays silent about 12 unscanned is the same silence
class as a preview that tallies only part of what it organizes.

**Nothing is dropped in the `awaiting_content` case.** The decision stays in the document on the
drive; a later scan plus a re-apply lands it.

### The per-drive loop is structural, not remembered

`reconcile_documents` returns a result with an **empty drive block** - each document describes a
different drive, so there is no single answer - which means drive labels come back only by walking
the documents themselves. A restore command that had to *remember* that loop would one day not,
and the symptom is a drive returning unnamed, indistinguishable from one the user never named.

So `apply_documents(catalog, documents)` does both halves in one call and there is no sequence for
a caller to get wrong. The empty drive block is itself pinned by a test, so nobody later "fixes"
it by populating it from whichever document happened to be newest - that would invent a drive and
quietly make the loop look unnecessary.

## What the tests are worth, and one honest gap

The privacy exclusion is asserted against a **real catalog read**, not only against a constructed
document: a format test only ever sees what a test built. The round-trip has been run against a
copy of the real 6.4 MB catalog through a real file on disk.

**The gap, recorded rather than glossed:** the real catalog holds **zero events and zero date
confirmations**, so until `(ack)` the restore path had only ever met *seeded* examples of the
decisions it exists to protect. Its one trip is why the fixture had one trip, and why a defect
that only appears at two survived - see `ENGINEERING_STANDARD.md` §4's seventeenth member.

## The restore command

`truestill restore <root>` - preview by default, `--apply` to act, typed word **`restore`**.

**The words come from the CLI's existing dialect, not a new one.** Every typed confirm here is the
operation's own verb - `move`, `clean`, `undo`, `delete`, `repoint`, `new` - so `restore` and
`discard` extend a pattern rather than adding a third vocabulary on top of the two `(aca)` already
records.

**It works with an empty catalog and no registered drives, and that is the whole case.** Every
other decisions path starts from a catalog that already knows something; this one cannot, because
the catalog is what was lost. So the named root is read **from the path**, and other registered
drives join the merge only when the catalog happens to have any - on a fresh machine that list is
empty and the command still works.

**What it says before asking.** The counts it would apply, and then the half that is easy to leave
out: unmatched event signatures **by name**, the `awaiting_content` count with its remedy ("plug
in the drive holding them, scan, and restore again"), decisions ignored because this machine's are
newer, and reconciliation's losers. A restore that reports 40 applied and stays silent about 12 it
could not place lets the user confirm on the good half only.

### `--discard`, and how `(aci)` closes

`(aci)` is the loss guard's one false positive: a decision **deleted on purpose** locally leaves
the drive holding something this catalog does not, so every later save refuses with `WOULD_LOSE` -
permanently, because nothing reconciles the two.

`restore <root> --discard --apply` is the user saying *"mine is right"*: **one forced write**,
after which the drive matches the catalog and the guard has nothing left to fire on. **No override
flag is stored**, so there is no state to go stale - which is why this is better than a suppression
setting.

It is the destructive branch and it is spelled that way: it names the sections that exist on the
drive and nowhere else before asking, its word is `discard` and **not** `restore` (a word typed
once, understood to mean one thing, must not authorise another - `clean-empty` learned this), and
it previews by default like everything else that writes.

**It still keeps what it cannot read.** Sections from a newer version are not decisions this
catalog is overruling - they are ones it does not understand - so discard merges them forward. A
second discard finds nothing to do and does not ask again; asking for a destructive word when
nothing is at stake teaches people to type it without reading.

**One interaction worth knowing.** After a restore that could not place everything - corrections
for photos this catalog has not scanned - the drive legitimately holds decisions the catalog does
not, so the ordinary save will report `WOULD_LOSE` for that drive until those photos are scanned.
That is the guard working, not a defect, and the restore output says what to do about it.

## The drive card, and a distinction worth keeping

**Two kinds of fact live on that card and they follow different rules.**

- `last_verified` and `last_seen` are facts about **what Truestill did**. They are recorded here,
  so they are legitimately shown for a drive that is not plugged in.
- The decisions date is a fact about **what is on the drive**, and the drive is the only authority
  for it. So it is read when the drive is reachable and **absent** when it is not - not the last
  value this machine happened to see.

A cached copy would be a second representation of a fact this machine does not own, which is the
defect `(ack)` was and the reason the duplicate `trip_days` map went. **The rule generalises past
this card:** the next time something wants to cache a drive's own state for an offline drive, the
question is which of these two kinds of fact it is.

`decisions.problem.<uuid>` follows the FIRST rule, not the second: a save Truestill attempted and
could not finish is something it did, so it survives the drive being unplugged.

### Staleness is a comparison of copies, not of clocks

*"Is the drive's copy behind?"* is answered by `would_lose(mine, theirs)` - the exact mirror of
the restore offer. **A timestamp comparison was ruled for and then withdrawn on a schema fact:**
`trips`, `events`, `albums` and `settings` carry **no date column at all**, so a `MAX` over the
decision tables covers two sixths of the decisions and would report a drive current while it is
missing a trip renamed the same day. That is a false reassurance in the one direction this feature
must never fail.

Comparing copies is exact, needs no new query, and needs no schema. **Every reachable drive is
meant to hold every decision** - the save writes the catalog-wide set to all of them - so a
difference really is staleness, and there is no "decisions this drive was never meant to hold"
case to filter out.

### One interaction, found by tests failing for a reason that was not their own

Opening the drive screen opens the catalog, and the **first** open of a catalog that predates this
feature writes its decisions to every reachable drive. So the first card a user sees after
upgrading says "saved just now" - the upgrade write doing its job. Pinned by a test, and the other
card tests take it out of the picture rather than working around it.

## Job 3 closed: what the feature is, end to end

**The sentence that started this: restore now works AND something points at it.** For most of
today it did the first only - a rescue file, a working command, and no way to learn either
existed, which is the Adobe failure one step later rather than a fix for it.

**What it does now.**

| | |
|---|---|
| **Writes** | after any work that changed the catalog, to every reachable registered drive, plus once on the first run after upgrading |
| **What** | trip and event names, drive labels, dismissed groups, corrected dates, layout and UI settings - about a kilobyte of plain readable JSON |
| **Where** | `.truestill-decisions.json`, beside the drive marker at the drive root |
| **Reads back** | `truestill restore <root>` - preview by default, typed word `restore`, works on an empty catalog with no registered drives |
| **Says so** | both CLI drive screens and the app's drive card: the date it was saved, whether the copy is behind, whether the drive is carrying names this computer lacks, and why a save failed |

**What it deliberately does not do.** It is not a backup of photographs and restores nothing if
every drive is lost. It does not restore a partial catalog: it puts decisions onto a catalog
rebuilt by scanning. It cannot recover decisions made before it shipped. It does not make custody
honest - that is `(abg)`. It will not help someone who never registered a drive. And it is not a
server: the catalog holds GPS and timestamps, so "we only take folder names" would have been
false.

**Still open, named rather than implied:** the app has **no restore** - it can tell you a drive is
carrying decisions and the command is a CLI one; `(acg)` album membership does not travel, because
`file_albums` is two rowids; `(aci)` is closed by `--discard`; and the Windows Defender exclusion
added for CI is still unmeasured.

### The one report to expect

**"It said my decisions were saved just now and I did not save anything."** Opening the drive
screen opens the catalog, and the first open of a catalog that predates this feature writes its
decisions to every reachable drive. That is the upgrade write doing its job, and the first card
after upgrading will always say so. It is pinned by a test rather than left to be rediscovered as
a bug.
