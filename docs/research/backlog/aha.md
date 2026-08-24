# (aha) AN EXTERNAL EXIF EDIT PRODUCES A DUPLICATE, OR ADVICE THAT DESTROYS IT.

*Body of entry `(aha)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aha) AN EXTERNAL EXIF EDIT PRODUCES A DUPLICATE, OR ADVICE THAT DESTROYS IT.** Filed
  2026-08-24 (P53) from a traced read, not a reproduction. ⚠ **RECORDS BEHAVIOUR AND PROPOSES
  NOTHING** - whoever picks this up rules first. Ranked **below `(ahb)`**, which is the route that
  keeps people out of this path in the first place.

## What a user does, and why

Every tool in the field tells them to. `porte` sorts undateable files into a folder "to inspect
manually"; `exif-assistant` makes a subfolder of dateless files "so you can easily examine the
images to manually rename files or folders and run again the command only on those folders".
**Editing the EXIF and re-running IS the field's model**, so a user arriving from any of them will
try it here.

## What actually happens - both rows traced

| the user edits | the path | what they get |
|---|---|---|
| **the SOURCE**, then re-organizes | new bytes → new `files.sha256`, which `IMPLEMENTATION_STANDARDS.md` §3's dual-hash rule makes **the dedup identity** → the content is not in this drive's `file_copies` scope → **copied again**. The original undated copy keeps its own row and stays. | **A DUPLICATE.** Two files, one photo, two dates. Wasted space and a count that disagrees with the library. |
| **the LIBRARY COPY** in place | `file_copies.copy_sha256` still holds the pre-edit hash → `verify` re-reads and reports **MISMATCH**, then prints *"(read-only: Truestill never repairs; re-copy the source to restore a bad file.)"* (`cli.py:1607`) | **DESTRUCTIVE ADVICE.** Following it overwrites the edited file with the pre-edit source and discards the user's work. |

⚠ **The hash cache is NOT the mechanism here, checked rather than assumed.** It is keyed on
`path + size + mtime_ns` (`hash_cache.py`), so an edit changes both and it **misses and re-hashes**
correctly. The consequence lives in the dedup identity, one layer up.

⚠ **`rescan` does not catch it either.** It is *"report only"* and its `PLACED` outcome is
**"never read"** - it stats rather than hashes, deliberately, because re-hashing a library to
answer a question about *paths* costs ~15 h against ~14 s. Integrity is `verify`'s question.

## 🔑 IT IS `(agv)`'s COUSIN, NOT ITS SIBLING, AND THE DIFFERENCE IS THE POINT

Both end at the same sentence from `verify`. They are not the same defect:

- **`(agv)`**: the photograph is **intact** and carries exactly the date the user asked for.
  `verify` reports MISMATCH anyway. **`verify` is wrong.**
- **Here**: the content **genuinely differs** from what the catalog recorded, because the user
  changed it. **`verify` is right.**

**What is wrong here is the REMEDY**, and only the remedy: *"re-copy the source to restore a bad
file"* assumes **corruption is the only way a file changes**. A deliberate edit is the other way,
and the sentence has no room for it. That is a smaller claim than `(agv)`'s and the entry says so
rather than borrowing its weight.

## `(ii)`'s reasoning already covers this, and it was written about hand-MOVES

`(ii)` (**SHIPPED 2026-07-31**, [`SHIPPED.md`](../../SHIPPED.md)) ruled the hand-fix workflow out
with a reason that extends to hand-*edits* without needing a word changed:

> **"The problem, precisely.** A hand-move is *undone by the next whole-disk operation*. The
> catalog still records the old location and the old, untrusted date, so `migrate-layout`
> re-renders the file straight back to the bin it was rescued from. The user's correction is not
> merely forgotten - **it is actively reverted, which is worse than not supporting it.**"

> **"A rescue is a CATALOG event, not a file move.** The user confirms the true capture date...
> Nobody drags anything; the tool does the move because the tool owns the placement."

🔑 **The field's tools can afford that hatch because they remember nothing.** `porte` and
`exif-assistant` keep no catalog, so there is nothing to contradict the human. Truestill keeps one,
which is why *"fix the files and re-run"* is not a smaller version of the rescue flow - **it is the
failure mode.** The convergence of two independent tools is evidence about tools without catalogs.

## The supported route, and where a user leaves it

The rescue flow closes the loop end to end - honesty view → `Show these files` →
`POST /api/dates/confirm` → `Catalog.confirm_date` (one transaction: `date_confirmations` **plus**
`files.captured_at`) → *"It has not moved on disk"* → `{"action": "migrate"}` → `plan_migration`
re-renders from `f.captured_at`. `test_confirmation_survives.py` pins it by name against
migrate-layout, re-layout, in-place organize, undo-organize and re-ingest.

⚠ **The point a user is most likely to leave it is the Organize result**, which names the undated
pile and links to nothing. **That is `(ahb)`, and it ranks above this entry** precisely because a
route is worth more than a defect note: it is what stops someone walking into this path at all.

## Not a proposed remedy

Deliberately no fix here. The obvious candidates - detecting that new content matches a
confirmed-date file, widening `verify`'s sentence, offering to adopt an edited copy - are each a
design nobody has costed, and the evidence is one traced path rather than a reproduction. ⚠ **A
reproduction is the first thing this entry needs**, and it should assert the harm a user meets
(the duplicate, or the advice), never the hash arithmetic underneath it.
