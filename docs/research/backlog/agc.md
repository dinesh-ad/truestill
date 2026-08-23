# (agc) A RULE CITED BY SECTION NUMBER ALONE WAS FILED UNDER THE WRONG AUTHORITY, THIRTEEN TIMES.

*Body of entry `(agc)`, in [`SHIPPED.md`](../../SHIPPED.md). The letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(agc)** Shipped 2026-08-23.

  ## What was wrong

  *"Partial-failure policy: one bad file never aborts a batch - it is logged, counted, and
  reported at the end."* lives in **`ENGINEERING_STANDARD.md` §4, the Errors bullet** - one of the
  eight unnumbered members. It was cited as **`IMPLEMENTATION_STANDARDS.md` §1** almost
  everywhere it appears.

  **The difference is authority, not shelving.** `IMPLEMENTATION_STANDARDS.md` *"overrides
  `ENGINEERING_STANDARD.md` on any conflict"* - its own first paragraph. So every one of these
  sites claimed more for the rule than the rule has.

  ## The census - thirteen sites, nine files

  | file | sites | how wrong |
  |---|---|---|
  | `organizer.py:1115` | 1 | **named `IMPLEMENTATION_STANDARDS.md` outright** |
  | `test_a_catalog_that_cannot_be_written_stops_the_run.py:3` | 1 | **named it outright** |
  | `afe.md` | 3 | bare `§1` |
  | `aet.md` | 2 | bare `§1` |
  | `afw.md` | 1 | bare `§1` |
  | `SHIPPED.md:933` | 1 | bare `§1` |
  | `BACKLOG.md:153` | 1 | bare `§1` |
  | `scan.py:153` | 1 | bare `§1` |
  | `test_one_undecodable_file_never_aborts_a_batch.py:17` | 1 | bare `§1` |
  | `test_the_app_records_what_a_run_did.py:45` | 1 | bare `§1` |

  ⚠ **`code-quality-audit.md:198` was the ONLY site that got the section right**, and it is the
  one that shows the second failure - see below.

  ## 🔑 WHY IT SURVIVED, WHICH IS THE POINT

  **Two properties make it near-undetectable.**

  1. **The quoted text was correct every single time.** A search for the words returns thirteen
     agreeing sites and zero contradictions. The corpus looks *consistent* precisely because it is
     uniformly wrong - the ordinary tell for drift, two documents disagreeing, is absent.
  2. **The section numbers collide.** Both files have a §1 and a §4. Every citation resolves to
     *something*, so no link check, no guard and no reader ever hits a dead reference. **Nothing
     can go red.**

  ⚠ **And it was live, not cosmetic.** `(afw)` is an open entry whose stated first question is
  *"is backup's fail-fast a §1 violation?"* - and that question **cannot be answered correctly
  while the rule is filed under the wrong authority**, because the answer is a claim about what
  the rule may compel. A ruling made on it would have been made against the binding contract when
  the rule is in the canon that loses.

  ## ⚠ THE SECOND FAILURE, AT THE ONE CORRECT SITE

  `code-quality-audit.md:197-198` says *"§4's partial-failure policy"* - right. But:

  - **the document is ambiguous**: one line above it cites `IMPLEMENTATION_STANDARDS.md` §8, so a
    bare *"§4"* immediately after reads as **that** file's §4, which is the filename and
    organization contract;
  - **it calls them *"two binding rules"*** when only one is - §9 is in the binding contract, §4
    is in the canon that loses.

  **Right section, wrong document, by silence.** Which is the argument for naming the file rather
  than for being more careful with numbers.

  ## What was done

  - **Live sites corrected in place** (open work and code): `BACKLOG.md`, `afw.md`,
    `organizer.py`, `scan.py`, and the three tests.
  - **Records corrected BESIDE, dated, originals left standing**: `SHIPPED.md` (a closure) and
    `code-quality-audit.md` (an audit record).
  - **Shipped entry bodies** `afe.md` and `aet.md` corrected in place with the house-style inline
    *"this said §1 until 2026-08-23"* note, which is how this repo records a fixed citation
    without losing what it said.
  - **`ENGINEERING_STANDARD.md` §4 gains the sixty-fourth member**: *a rule cited by its section
    number rather than its document inherits the authority of whichever document the reader
    assumes.* It is the **inverse** of the thirty-fifth - that one is a sentence that was never a
    rule acquiring the force of one; this is a real rule acquiring the force of the wrong one.

  ## The standing habit

  **Name the file, always; never the section alone.** `ENGINEERING_STANDARD.md` §4, not §4. Three
  words, and the only thing that would have caught this - the quotation could not, because it was
  right.

  ⚠ **Not enforced, and that is stated rather than left as an implied to-do.** A guard would have
  to know which document each section number belongs to, which is the judgement being automated
  rather than a lookup. Considered; not built.
