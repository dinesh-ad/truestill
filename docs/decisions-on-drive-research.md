# Decisions on the drive: surviving a lost catalog

> **LIVE DESIGN, not a frozen record. Status as of 2026-08-09.**
>
> **Built:** the document itself (`truestill_core.decisions`) - the dataclass, the serialiser,
> the forward-compatible parser, the catalog gather and apply, an atomic drive write, and the
> multi-drive save with its read-merge-replace and its upgrade gate
> (`save_decisions_to_reachable_drives`, `ensure_decisions_on_drives`).
>
> **Wired since 2026-08-09.** `catalog_session.open_catalog` is how both surfaces open a catalog -
> all **56** sites, 15 in the CLI and 41 in the app - and it saves the decisions when the work
> finishes, plus once on the first run after upgrading. So documents do now reach drives in
> ordinary use.
>
> **NOT built, and nothing here should be read as claiming otherwise:** **restore**, the
> multi-drive reconciliation, `(acc)`'s discoverability, and every surface. The app is **silent
> about a failed save** until the drive card is built - a named gap, not a covered one.
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

**Human decisions only.** Everything else - hashes, dates, GPS, camera, categories, paths - is
recomputable from the files, and is most of what makes the catalog 6.4 MB.

```
drive        uuid, label, notes
settings     layout templates and UI prefs - NOT path hints (see privacy)
trips        name, slug, start, end, and the trip's own days
events       name, slug, start, signature
skipped      dismissed cluster signatures
dates        sha256 -> corrected captured_at, confirmed_by
albums       name (membership NOT yet carried - see (abw))
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
gave the first trip every other trip's days. `(abv)` in `SHIPPED.md` has the full record; the fix
is that a trip carries its **own days**, which works because `trip_days.day` is a primary key, so
days are disjoint across trips and a day list identifies a trip exactly.

**The general rule, and it is the one to apply to albums next:** a key that only means something
inside this catalog cannot be the thing that carries identity out of it. `(abw)` records that
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

**The 1,353 is smaller than the 1,508 measured before `(abv)`, while carrying strictly more.**
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
guessed at - `(aby)`. Guessing which side is intentional is how the other direction loses data.

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
than a repair, and one field standing for two situations that need opposite words is `(abx)`.

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
username, a folder layout and the existence of a Crypto Folder onto a drive the user may lend or
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

**A trip's identity is its day set** (`(abv)`), so the same days under a different name is a
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

## What the tests are worth, and one honest gap

The privacy exclusion is asserted against a **real catalog read**, not only against a constructed
document: a format test only ever sees what a test built. The round-trip has been run against a
copy of the real 6.4 MB catalog through a real file on disk.

**The gap, recorded rather than glossed:** the real catalog holds **zero events and zero date
confirmations**, so until `(abv)` the restore path had only ever met *seeded* examples of the
decisions it exists to protect. Its one trip is why the fixture had one trip, and why a defect
that only appears at two survived - see `ENGINEERING_STANDARD.md` §4's seventeenth member.
