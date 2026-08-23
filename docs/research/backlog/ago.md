# (ago) A DOCUMENTATION AUDIT: 632 CITATIONS, AND NOTHING CHECKED ONE.

*Body of entry `(ago)`. **SHIPPED 2026-08-23.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ✅ SHIPPED 2026-08-23
>
> Sixteen stale citations fixed in living documents, and a guard so the class cannot return
> silently. `BACKLOG.md` had recorded the exposure in its own text and nothing acted on it.

## The exposure was already written down

`BACKLOG.md`, under *Consciously out of scope*, says it plainly: **"Nothing would tell us.
Checked: no test or guard asserts a line number."** It was written about a JavaScript formatter
that would rewrite `app.js` and invalidate 65 pointers. The class is wider - **632 `path:line`
citations across 206 tracked documents**, drifting under every ordinary refactor.

## Research: the pattern has a name

**Docs as tests** - use tooling to detect stale documentation and fail the build, rather than
relying on review to notice. The study behind it found **230 stale code-element references across
82 repositories**, 23% of those analysed, and the recommended technique is a cheap grep that flags
references which have vanished from source.

## ⚠ THE RAW NUMBER WAS MISLEADING, AND THE CLASSIFICATION IS THE FINDING

32 of 632 citations did not resolve. **31 of those 32 sit in records** - research notes, audits,
soak records, `SHIPPED.md` closures - which this repo deliberately never rewrites, because *a
record rewritten to stay correct stops being one*. The single one in canon is
`TiffImagePlugin.py:950`, a **Pillow** file, correctly absent from this tree.

**So the corpus was in far better shape than the count suggested**, and a guard over all of it
would have gone red on the past on the day it was written - switched off within a week, taking its
real signal with it (`ENGINEERING_STANDARD.md` §4).

## What was actually stale, and it was found by looking at a different signal

A file-exists-and-in-range check finds nothing here, because a drifted line is usually still *in
range*. The signal that works is cheaper and sharper: **a citation pointing at a blank line**.
Nobody cites one on purpose.

**Sixteen fixed, in documents somebody reads in order to do something:**

| document | was | is |
|---|---|---|
| `BACKLOG.md` + `agh.md` | `server.py:904` | `:914` |
| `BACKLOG.md` + `agh.md` | `test_server.py:18,31,37` | `:20,33,39` |
| `BACKLOG.md` + `agd.md` | `backup.py:239-245` | `:247-253` |
| `BACKLOG.md` + `agd.md` | `IMPLEMENTATION_STANDARDS.md:1280` | `:1354` |
| `agd.md` | `backup.py:248` | `:259` |
| `cli-app-parity.md` | `cli.py:576`, `:616`, `organize.py:1024` | `:594`, `:634`, `:1030` |
| `DECISIONS.md` | `local.py:113-118`, `date_rescue.py:280`, `drive_adoption.py:167` | `:111-118`, `service/date_rescue.py:286`, `:231` |
| open entry bodies | `aax`, `abw`, `ads`, `adt`, `adz`, `aed`, `age`, `ll` | ten citations re-aimed |

⚠ **`DECISIONS.md` was stale in a second way, and it is corrected rather than tidied.** It offered
two comments as evidence; one of them - *"not evidence either way"* - **is no longer in the
source**. The behaviour is unchanged, the decision stands, and the correction says so, because
silently swapping the quote would have hidden exactly the drift being audited.

⚠ **Several were caused by my own commits earlier the same day.** `backup.py` moved under `(afw)`;
`IMPLEMENTATION_STANDARDS.md` moved because `(afw)` added the record contract to it. Nothing
noticed.

## The guard, and what it deliberately does not cover

`test_live_documents_cite_code_that_exists.py` checks the **living** set only: binding canon,
current guides, and **the body of every backlog entry still open** - read from `BACKLOG.md` rather
than listed, so an entry leaves the scope in the same commit that ships it. `SHIPPED.md` is
excluded: a closure is provenance, not instruction.

⚠ **STATED RATHER THAN IMPLIED** (§4's twenty-second member): it cannot tell that a line moved
*within* a file onto other real code. Of the five drifts found by hand in canon, it would have
caught **two**. Catching the rest honestly means citing symbols rather than line numbers, which is
a different and larger change - **named here, not smuggled in.**

## Also audited, and clean

* **`CLAUDE.md`'s document map is complete** - all **64** non-body documents are named in it,
  checked against `git ls-files`. Its own dated readings gained 2026-08-23: **206 / 142 / 64**.
* **Every numeric claim carrying its own command holds**: 17 subcommands, 50 routes, 82 §4
  members, schema v21. The browser lane read **505**, not the 502 recorded on 2026-08-22 - updated
  as a dated reading, which is how that paragraph is built.
* **Six open entries spot-checked against the code** - `(afq)`, `(ael)`, `(aac)`, `(aap)`,
  `(adn)`, `(agh)` - and all six are still genuinely open.
* **`PROJECT_STATUS.md` §1 was a day behind on state**, which matters because it is the file a
  cold start reads first: it did not mention the record-scheme contract change or schema v21.

## Proof

Five mutations, all caught, three cry-wolf. ⚠ **Two survived first and both mutants were VALID**:
with the corpus cleaned, deleting the blank-line rule and deleting the range rule each killed
nothing, because there was no longer anything to find. **A guard whose only evidence is that the
world happens to be tidy is unfalsifiable and would stay green through its own deletion.** The
detector now has its own positive cases, written against real tracked files with the blank line
*located* rather than hardcoded, so the fixture cannot rot the way the citations it guards did.
