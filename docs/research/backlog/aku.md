# (aku) VERIFY PROVED A COPY CORRUPT AND THE CATALOG HAD NOWHERE TO PUT IT.

*Body of backlog entry `(aku)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

## THE DEFECT, FOUND BY USING THE PRODUCT

`file_copies` had `last_verified` and `missing_at` and **no column for *checked, and wrong***.
`verify` had exactly two write branches:

```
VERIFIED -> mark_copy_verified      MISSING -> mark_copy_missing      MISMATCH -> (nothing)
```

So on a real library a check read a photograph, found its bytes wrong, reported **"1 changed"**,
named the file - and wrote nothing. The copy recorded as `missing_at IS NULL, last_verified IS
NULL`: *present, never checked*, which is byte-for-byte the state of a copy nobody has ever looked
at.

**Measured consequence**: `/api/where` went on reporting that photograph in **2 places**, and the
custody band, the at-risk count and the custody floor all counted a copy the product had just
proven was garbage.

⚠ **`(abg)`'s argument one column over.** Absence had nowhere to go; **damage had nowhere to go.**

⚠ **NO TEST COULD HAVE CAUGHT IT.** Every test asserted the verify *report*, which was correct.
The defect lived in the gap between two individually-correct components, and only appears if you
corrupt a file and then look at a **different screen**.

## THE FIELD'S FRAMING

- **Ceph** runs two scrub classes with two distinct health states and warns about exactly the
  worst case: *"if a corrupt replica's OSD fails before the next deep scrub runs, recovery can
  rebuild from the corrupt copy and propagate the damage."*
- **CockroachDB**, on a checksum mismatch: *"this is not a transient condition - the database is
  telling you that data integrity is compromised."*
- **Borg**: `check` is read-only by default and reports; repairing is a separate explicit act.
- **rotty**, on bit rot at rest: *"only checks for corruption, not able to repair. You need actual
  backups to replace the corrupted files."*

## THREE STATES, AS RECORDED

| state | on disk | means |
|---|---|---|
| never checked | both NULL | nobody has read these bytes back |
| checked and clean | `last_verified` set | we read them and they were ours |
| **checked and wrong** | **`damaged_at` set** | we read them and they were not |

**Schema v24**, `file_copies.damaged_at`. Additive, NULL on every existing row, **no backfill** -
the DDL/DML rule. A v23 catalog answers every question the same way after the migration as before
it, because NULL means *not known to be damaged*, never *known good*; that claim needs
`last_verified`.

⚠ **The migration is not a compatibility path and CLAUDE.md's no-users rule does not license
skipping it.** That rule is about carrying cost for a *beneficiary who does not exist*. An older
catalog **must** migrate or it cannot be opened at all, and the step is the same ten lines
`missing_at` (v19) and `bake_started_at` (v22) already are.

⚠ **PERSISTENT, which is what separates damage from absence in kind.** An unplugged drive comes
back and `missing_at` clears; rotted bytes do not un-rot. `damaged_at` survives until a later
verify **reads the bytes again** and finds them right (`mark_copy_verified`), or the copy is
written afresh (`record_copy`). **Merely seeing the drive again does not clear it**, and that is
asserted.

## A CORRUPT COPY IS NOT A PLACE

Nine counters answered *how many places does this file have*, and each spelled the rule out for
itself as `missing_at IS NULL`. Adding a second disqualifier meant editing all nine identically -
§4's *a rule applied to two of three surfaces reads as settled*, with the number of surfaces
raised. So the rule is now **one function**, `catalog.a_place(prefix)`, and a fourth state edits
it and nothing else.

With one of two copies proven corrupt, measured before and after:

| surface | before | after |
|---|---|---|
| `single_copy_count` | 0 | **1** |
| `single_copy_shas` | 0 | **1** |
| at-risk total (`single_copy_by_drive`) | 0 | **1** |
| `custody_floor` floor | 2 | **1** |
| `held_floor` | 2 | **1** |
| `one_copy` | 0 | **1** |
| `holder_sets` | 1 | **0** |
| `drives_holding` | 2 | **1** |

⚠ **`/api/where` is the deliberate exception, and it is not a counter.** It lists every *recorded*
copy - it does not filter absent ones either - and its help is *"find which drive(s) hold a file,
even when unplugged"*. Its `total` is a **search-result count**, not a custody count. Hiding the
damaged row would remove the one screen that can tell a user WHICH of their copies is the bad one,
so the row is listed and carries `damaged_at` instead.

## RECOVER REFUSES A CORRUPT SOURCE

Ceph's propagation warning, in this product. `recover` now checks `damaged_at` **before a byte is
read** and skips with `Skipped.DAMAGED_ON_THE_DRIVE`:

> on this drive but damaged - a check read it and the bytes were wrong, so it was not copied into
> your library

⚠ **This is a refusal, not the safety net.** The existing content check - stage, then compare the
written digest against `verify_sha` (`recover.py`) - **already prevented propagation** and is
unchanged; it still catches damage that appeared *since* the last verify. What it could not do is
avoid reading a whole file we already knew was bad, or say why. Borg's split: check reports,
repair is separate.

## RECLAIM NEEDED NO CHANGE, AND THAT IS ESTABLISHED RATHER THAN ASSUMED

`reclaim._verify` **re-hashes the destination copy live at delete time** and compares against the
expected digest - `IMPLEMENTATION_STANDARDS.md` §1's rule, *"never trusts a stale
`last_verified`"*. A corrupt copy fails that comparison however the catalog describes it, so the
source is counted `kept` and **not deleted**. Pinned by
`test_reclaim_keeps_a_source_whose_only_backup_copy_is_corrupt`, because *"reclaim is fine"* is
exactly the sentence that stops being true when somebody optimises the re-hash away in favour of
the new column.

## WHAT IS NOT DONE

⚠ **The damaged chip shares `--warning` with "gaps".** This palette has two negative tokens and no
danger family at all; minting one is a design-system decision (`design-system.md`, the D19/D20
line), not something a defect fix takes on its way past. The distinction is carried by the word -
*"3 damaged"* against *"3 missing"* - and by `data-health`. A distinct colour is the right
follow-up.

⚠ **Nothing offers to repair a damaged copy.** Borg and rotty both say the same thing - *"you need
actual backups to replace the corrupted files"* - and the product has `recover`, which now refuses
the bad copy and could pull the good one from elsewhere. Wiring *"replace this damaged copy from a
drive that has it"* is real work and is not this entry.

## RELATED

`(abg)` (`missing_at` - the same argument one column over), `(aes)` (`was_checked`, the *display*
of a NULL `last_verified`; this is the **count** half), `(akp)` (the remedy naming the right
drive), `(akt)` (the at-risk payload this had to agree with), `(aiy)` (custody counted six ways).
