# Soak one - the record, reconstructed

⚠ **RECONSTRUCTED 2026-08-22 FROM WHAT SURVIVES. IT WAS NOT KEPT AT THE TIME, AND THIS IS NOT THE
SAME THING AS A RECORD.** Soaks two, three and four each have a plan written before the run and a
record written after it. Soak one - **run 2026-08-20**, the one that overturned the most - has
neither. `ca2f043`, *"the first soak - what 4,111 real photos say the product gets wrong"*, is the
commit that closed it, and it touched **four files: `BACKLOG.md` and three entry bodies.** The
findings were filed; the run was not.

**Rebuilt from:** [`PROJECT_STATUS.md`](PROJECT_STATUS.md) §1, [`SHIPPED.md`](SHIPPED.md) for
`(aei)`/`(aej)`/`(aek)`/`(aem)`, [`BACKLOG.md`](BACKLOG.md) for `(ael)`/`(aep)`,
[`soak-two-plan.md`](soak-two-plan.md) §1 and its V2 correction, and the commits of 2026-08-20.
Everything below is traceable to one of those. **Nothing here is recalled.**

⚠ **What cannot be reconstructed, stated rather than glossed:** `PROJECT_STATUS.md` §1 says
**seven steps** ran; `soak-two-plan.md` §1 says soak one *"left no written step list - its steps
are recoverable only from the findings."* So **five of the seven are visible only through what they
found, and two left no trace at all.** A record written on the day would have named all seven and
what each was looking for. This one cannot, and no later reading will recover them.

## The corpus, and the correction that came a day later

**4,111 files, 11 GB**, counted independently **before the product was allowed an opinion** - the
method `soak-two-plan.md` §1 calls *"the whole design"*, and the reason the five findings were
attributable at all.

⚠ **Those 4,111 included `Input/Testing-new`, which `IMPLEMENTATION_STANDARDS.md` §5 excludes.**
Measured 2026-08-21: `Input/2013` + `Input/2014` is 2,276 files, `Testing-new` is 1,836, and
`2,276 + 1,836 = 4,112` - only `Input` entire matches the recorded figure. §5 was checked rather
than assumed and is **correct**, so the error was soak one's scope, not a stale rule.
**The numbers are not wrong and the five findings stand**; what was wrong is the implication that
the fence held. ⚠ **It cost nothing, and that is why it went unnoticed** - soak one was copy-mode
throughout, so including an unbacked folder had no consequence. It stops being free the moment a
soak relocates or deletes, which is why the fence became a ruling for soak two.

## What it found - five entries, and the one that could not be found any other way

| entry | what it was | state |
|---|---|---|
| **`(aei)`** | `organize` into a fresh second drive copied **0 files**, registered a 0-file drive and reported success - while `status` warned in the same breath that 4,088 files sat on one drive. It deduped against the **catalog**, not the **destination**. | ✅ shipped 2026-08-20 |
| **`(aej)`** | `LAST VERIFIED: never` **sixteen seconds after** a verify that found and named 7 missing files. Three surfaces stated something true of one population as if true of another. | ✅ shipped 2026-08-20 |
| **`(aem)`** | A `kill -9` at 340 of 4,105 files left a library that **read as complete**. Split out of `(aej)` as a different kind of defect. Schema v20, `organize_runs`. | ✅ shipped 2026-08-20 |
| **`(aek)`** | A full disk during drive setup crashed with a `pathlib` traceback. ⚠ The fix was the **ordering**, not error handling - the sentence already existed and the run died before reaching it. | ✅ shipped 2026-08-21 |
| **`(ael)`** | No CLI route copies a library to a second drive when the source folder is gone. `(aei)` closed most of it. | ⚠ **OPEN** |
| **`(aep)`** | A failed copy leaks backend vocabulary and a raw `[Errno 13]`. Split out of `(aek)` 2026-08-21 - its third finding, and the only one not about setup. | ⚠ **OPEN** |

⚠ **`(aei)` is the headline and nothing else would have found it.** It needed a real library, a
real second drive and a run that was allowed to report success. No unit test asks *"did the second
drive receive anything?"*, because the query that was wrong - `SELECT source_path, sha256,
perceptual FROM files`, no `drive_uuid`, no `WHERE` - is correct for every other caller.

## What it proved sound, which a findings list drops

- The `.partial` → rename → record write path survived **both** a `SIGKILL` and a full disk with
  **no corrupt file and no phantom row**.
- `(adx)` gap 1's clone disclosure fired correctly on an **11 GB clone**.

## What it did not test

Everything soaks two, three and four were later written for. **Nothing refused**: no step
`chmod`s anything, no destination goes read-only mid-run, no drive unmounts, and neither deleting
command (`reclaim`, `clean-empty`) was exercised at all. That absence is why soak three exists and
soak four after it - and soak two's stock-take, which named refusal as the unexplored class, was
written from soak one's shape rather than from soak one's document, because there was none.

## Why this file exists, and what its absence cost

⚠ **Two of soak one's six findings are still open, and they are the only soak findings that are.**
Everything soaks two, three and four raised is closed. The difference is not that `(ael)` and
`(aep)` are harder - it is that they lived in `PROJECT_STATUS.md` bullets and two backlog entries
rather than in a record with a *"what is still open"* section, so nothing pulled them forward for
three weeks. **A record is not paperwork about the past; it is the thing that keeps a run's
unfinished half visible.** That is the argument for writing one on the day, and this reconstruction
is what it costs not to - a shorter document, missing two of seven steps, written by someone
reading commits instead of by someone who was there.

## ⚠ DATED CORRECTION - 2026-08-27

**A record, so the text above is not edited.** Two facts in it have moved:

- *"Two of soak one's six findings are still open, and they are the only soak findings that
  are"* - **`(aep)` shipped**, and soak six (2026-08-25) raised three more. Derived from
  `BACKLOG.md`'s open section on 2026-08-27, the open soak findings are **four**: `(ael)` from
  this run, and `(ahs)`, `(aht)`, `(ahv)` from soak six.
- *"Everything soaks two, three and four raised is closed"* - still true, and now also true of
  soak five. Soak six is the one with open findings.

🔑 **The argument the passage makes is untouched and is the reason this correction sits beside it
rather than replacing it.** `(ael)` and `(aep)` sat open for three weeks because they lived in
bullets rather than in a record with a *"what is still open"* section. That is why this file was
written, and it is why the correction is dated rather than folded in - a record edited to stay
correct stops being one.
