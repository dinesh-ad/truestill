# CLAUDE.md

truestill - a local-first media organizer, de-duplicator, and backup pipeline (uv workspace:
`truestill-core` library + `truestill-cli` + `truestill-app`).

The command is `truestill`; the local web UI is `truestill-app`. Drives are identified by a
`.truestill-drive.json` marker (pre-rename `.vaeon-drive.json` drives are still read - see
`IMPLEMENTATION_STANDARDS.md` §3.1).

**This is the only entry point.** `docs/CLAUDE.md` was merged here on 2026-08-15 and no longer
exists; two overlapping "Read first" lists naming the same three canon docs is two things that can
disagree. Its day-to-day guidance is §"Working here" below, unchanged. ⚠ Older records
(`docs/default-layout-research.md:233,252`) still cite `docs/CLAUDE.md`; those are **records and
are deliberately not edited** - a record rewritten to stay correct stops being one - so this note
is what resolves the pointer.

## Read first, every session

0. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) - **start here.** Where the project
   stands, what ships next, and the standing rules. Read it before doing anything else.
1. [`docs/ENGINEERING_STANDARD.md`](docs/ENGINEERING_STANDARD.md) - the portable canon.
2. [`docs/IMPLEMENTATION_STANDARDS.md`](docs/IMPLEMENTATION_STANDARDS.md) - the binding,
   repo-specific contract.

**`IMPLEMENTATION_STANDARDS.md` wins on any conflict.**

**Before building anything from `BACKLOG.md`, check `SHIPPED.md`.** ⚠ **And start from
`## Build next`** - the file is sectioned by what an entry *is* since P175, and the other sections
hold conditional work, internal tooling, records and rulings. **A record is never deleted to
shorten the list** (`(ait)`/`(aiu)`: a lost answer key corrupts every measurement taken against it). The two share one letter
namespace and answer opposite questions - open work and provenance. The pair was split on
2026-08-01 because one file doing both jobs let `(aae)` and `(jj)` sit in the wrong section while
they were shipping, so **a letter absent from the backlog is not free**; look for it in
`SHIPPED.md` before treating it as unbuilt. Neither map named `SHIPPED.md` until 2026-08-10, which
left a cold start with no route to *"is this already built?"* - the question the file exists to
answer.

## The document map - which doc answers which question

⚠ **This map covers every tracked `.md` file except the backlog bodies, and completeness is
the point.** It listed **16** until 2026-08-15 - so two thirds of the corpus was unmapped,
including `README.md` and `react-migration-plan.md`, which carries **14 code citations**. The map
is the entry point; a map missing two thirds of it sends a cold start to search instead.

**The one deliberate exception**: `docs/research/backlog/*.md` is **one file per lettered entry**,
reached through its own index rather than listed here - a table with a row each would be complete
and unreadable, which is the failure this map already had once. Both figures are commands rather
than numbers to trust, because a number here rots the next time anyone adds a document:

```
git ls-files '*.md' | wc -l                      # every tracked document
git ls-files 'docs/research/backlog/*.md' | wc -l # the exception above
```

On 2026-08-22 those read **183** and **121**, leaving **62** mapped below. ⚠ They read **181**/**119**, **180**/**119** and **176**/**115** earlier that same day, **159**/**102** on 2026-08-21, **148**/**93** on 2026-08-20, **139**/**84** on 2026-08-19 and **133**/**78** on 2026-08-15 - stale within a day, three times - which is the argument for running the commands rather than for updating these numbers faster. **The mapped figure is the one to watch**: it held at 55 across four readings, moved to 56 on 2026-08-21 when `soak-two-plan.md` became the first document since 2026-08-15 to land outside `docs/research/backlog/`, and reads **61** on 2026-08-22 - `soak-two-record.md`, `soak-three-plan.md`, `soak-three-record.md`, `soak-four-plan.md` and `soak-four-record.md`, each of which has a row below. ⚠ **It then HELD at 61 across a second reading that day**, when the totals moved by four - four new backlog bodies, no new document outside them - which is the map working rather than the map going stale. It then moved to **62** with `soak-one-record.md`, which has a row below - a count that moves WITH a row is the map working; the failure is one that moves without. It **held at 62** when `afp.md` and `afq.md` landed, because both are backlog bodies and the exception covers them. A mapped count that moves **without** a row being added is the map going incomplete; a count that moves *with* one is the map working. ⚠ **2026-08-23: 206 / 142 / 64.** The totals moved by twenty-three and twenty-one; the mapped figure moved by two - `cli-app-parity.md` and `user-evidence-log.md`, **each of which has a row below**. Audited against the tree the same day: **every one of the 64 is named in this file**, so the exception is doing its job and the map is not behind. It then moved to **65** with `tests/golden/README.md` - the golden-corpus snapshot's home, and its row is below - a count moving WITH its row, again. **2026-08-24: 66**, with `handoff-2026-08-24.md` - its row is below. ⚠ **2026-08-25: 243 / 175 / 68, then 69** with `handoff-2026-08-25.md`, whose row is below. The 68 was reached in three readings that day - **67** with `soak-five-record.md` and **68** with `soak-six-record.md`, each of which has a row below, and it **held at 68** across five new backlog bodies (`(ahp)` through `(aht)`) because the exception covers them. ⚠ **2026-08-26: 255 / 186 / 69, and the mapped figure HELD** across `aia.md`, `aib.md`, `aic.md`, `aid.md` and `aie.md` - five new documents, all backlog bodies, all covered by the exception. The totals moved by five and the mapped figure did not, which is the map working. ⚠ **The sentence recording those readings was itself garbled on 2026-08-25** - two appended clauses left in the wrong order, one contradicting the other about how far the totals moved - and is rewritten here rather than appended to again. A count sentence that grows by accretion is the drift this paragraph is about, one level up. ⚠ **2026-08-26: 249 / 180 / 69 - the mapped figure HELD** across five new backlog bodies (`(ahu)` through `(ahy)`), no new document outside them, which is the exception working exactly as designed. It **held again at 69** later that day - 250 / 181 - when `(ahz)` landed, one more backlog body and no document outside them. ⚠ **2026-08-27: 256 / 186 / 70.** The totals moved by six and the mapped figure by **one** - `handoff-2026-08-27.md`, whose row is above; the other five were backlog bodies. **Audited against the tree the same day: all 70 are named in this file, zero unmapped.** ⚠ **2026-08-29: 259 / 188 / 71**, then **263 / 191 / 72** after soak eight, and **264 / 192 / 72** with `aik.md`. The first move was `soak-seven-plan.md`; the second added three backlog bodies (`aih`, `aii`, `aij`) the exception covers and one mapped document, `soak-eight-record.md`, **whose row is above**; the third added `aik.md` alone and **the mapped figure HELD**, which is the exception working. ⚠ **2026-08-29 (later): 265 / 193 / 72** with `ail.md`, and **the mapped figure HELD again** - one more backlog body, covered by the exception. A count that moves *with* its row - or holds when only a body lands - is the map working. ⚠ **2026-08-30: 279 / 205 / 74.** The totals moved by fourteen and twelve; the mapped figure by **two** - `soak-nine-record.md` and `release-rehearsal-record.md`, **each of which has a row below**. **Audited against the tree the same day: all 74 are named in this file, zero unmapped.** ⚠ **2026-08-31 (P167/P168): 289 / 212 / 77** - the mapped figure moved by **one**, `handoff-2026-08-31.md`, **whose row is below**; `aje.md` was the body. **Audited the same day: all 77 are named in this file, zero unmapped.** ⚠ **2026-08-31 (later): 287 / 211 / 76** - `soak-eleven-record.md` is the mapped one, whose row is below; the other four are backlog bodies (`aja`-`ajd`). ⚠ **2026-08-31: 280 / 207 / 75.** The totals moved by one and two; the mapped figure by **one** - `soak-ten-record.md`, **whose row is below**; the other two were backlog bodies (`aiy`, `aiz`) the exception covers. ⚠ **2026-09-01: 291 / 213 / 78.** The mapped figure moved by **one** - `soak-twelve-record.md`, **whose row is below**; `ajf.md` was the body, and it is the body that should have existed on 2026-08-31 and did not (see below). ⚠ **2026-09-01 (later): 292 / 214 / 78 - the mapped figure HELD**, `ajg.md` being a backlog body the exception covers. ⚠ **2026-09-01 (P169): 293 / 215 / 78 - HELD again**, `ajh.md` being one more backlog body. ⚠ **2026-09-01 (P170): 294 / 216 / 78 - HELD a third time**, `aji.md` being one more body. ⚠ **2026-09-01 (P171): 295 / 217 / 78 - HELD a fourth time**, `ajj.md` being one more body. ⚠ **2026-09-01 (P172): 296 / 218 / 78 - HELD a fifth time**, `ajk.md` being one more body. ⚠ **2026-09-01 (P173): 297 / 219 / 78 - HELD a sixth time**, `ajm.md` being one more body. ⚠ **2026-09-01 (P175): 298 / 220 / 78 - HELD a seventh time**, `ajn.md` being one more body. ⚠ **2026-09-01 (P186): 302 / 223 / 79.** The mapped figure moved by **one** - `handoff-2026-09-01.md`, **whose row is above**; `ajp.md` and `ajq.md` are backlog bodies the exception covers. ⚠ **2026-09-02 (P192): 305 / 225 / 80.** The mapped figure moved by **one** - `agent-tooling.md`, **whose row is below**; `ajr.md` and `ajs.md` are bodies the exception covers. ⚠ **2026-09-03 (P199): 306 / 225 / 81.** The mapped figure moved by **one** - the contract oracle's `README.md`, **whose row is below**. ⚠ **2026-09-03 (P203): 311 / 229 / 82** - `handoff-2026-09-03.md`, whose row is below; the five earlier handoffs keep their names in this file, under *The records*. Run the audit rather than reading this number: compare `git ls-files '*.md' | grep -v docs/research/backlog/` against the names in this file - that is the check, and it is what turned a plausible "+2 with no rows" worry into a fact in one command.

### The canon - binding, kept current

| Question | Document |
|---|---|
| Where does the project stand? What is next? **What order are we building in?** | [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) - **§1b** is the build order (engine, then contract, then UI), written down 2026-08-25 after being re-argued three times |
| How do I work here? (workflow, research order, code standard) | [`docs/ENGINEERING_STANDARD.md`](docs/ENGINEERING_STANDARD.md) |
| What are the binding rules? (invariants, architecture, data, gates) | [`docs/IMPLEMENTATION_STANDARDS.md`](docs/IMPLEMENTATION_STANDARDS.md) |
| Why is the product this way? (settled stances: accounts, licensing, monetization, toolchain) | [`docs/DECISIONS.md`](docs/DECISIONS.md) - **D10**+**D13** on Python 3.14 (deferred, then adopted when the deferral's premise proved false), **D11** holds mypy, **D12** refuses Aceternity |
| What should I build next? | [`docs/BACKLOG.md`](docs/BACKLOG.md) **`## Build next`** - the short list, and the only section that answers this. ⚠ **The file is sectioned by WHAT AN ENTRY IS since P175** - *Build next*, *Conditional, and counted*, *Internal / tooling*, *Blocked*, *Rulings*, *Records*, *Ideas / deferred*. `grep -cE '^- \*\*\([a-z]{1,3}\)' docs/BACKLOG.md` counts them all; the number that matters is the size of **Build next**. `PROJECT_STATUS.md` **§2c** is why. The **index**; each entry's body is [`docs/research/backlog/<letter>.md`](docs/research/backlog). ⚠ **AN ENTRY LINKS ITS OWN BODY, and that is what guards the body's existence** - `test_doc_pointers_resolve.py` already fails on a markdown link that resolves to nothing, so a linked body cannot go missing. On 2026-09-01, **3 of 118 open entries did not link theirs** and `(ajf)` - the top-ranked item in the 2026-08-31 handoff - **had no body at all**, having escaped the guard by not pointing at it. All 118 link now. **No new census guard was added and none is wanted**: `(ago)` ruled that a guard is an artifact that has to earn itself, and one green on the day it is written, over a class an existing guard already covers, earns nothing |
| **Is this already built?** (provenance - read before building anything) | [`docs/SHIPPED.md`](docs/SHIPPED.md) |
| What does it cost, and what should I not "optimize"? | [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) |
| What changed and when? | [`CHANGELOG.md`](CHANGELOG.md) |

### Guides and reference - current, not binding

| Question | Document |
|---|---|
| What is this project, and how do I install and run it? | [`README.md`](README.md) |
| How do I report a vulnerability, and what is in scope? | [`SECURITY.md`](SECURITY.md) |
| **Where does an arriving engineer start?** | [`docs/handoff-2026-09-03.md`](docs/handoff-2026-09-03.md) - the current dated state check: this session's three defect classes with the DO for each, an **index of every earlier class** and where its record holds it, state as commands, §1b's conditions, the two releases and what no check has reached. ⚠ **The five earlier handoffs are RECORDS, listed under *The records* below, and the map names only this one as the start point** (ruled 2026-09-03, P203: their §1 defect classes and DOs are cited by closed entries, a soak record and three test docstrings as the source of named conventions, so they are evidence, not superseded working documents) |
| How do I move libraries to another machine? | [`docs/moving-machines.md`](docs/moving-machines.md) |
| What has Claude Code installed here, and what may each tool do? | [`docs/agent-tooling.md`](docs/agent-tooling.md) - the two MCP servers and two plugins that live **outside the repo**, and **the fence gap first**: an MCP tool is covered by neither enforcement layer, so a call that carries project facts is a decision each time |
| What does the product look like? (wordmark, colour, icons) | [`docs/brand.md`](docs/brand.md) |
| Where did the brand artwork come from, and under what licence? | [`brand/PROVENANCE.md`](brand/PROVENANCE.md) · [`brand/README.md`](brand/README.md) |
| What have real users actually lost, in their own words? | [`docs/user-evidence-log.md`](docs/user-evidence-log.md) - a **record**: forum evidence behind `(abf)`, `(agk)` and the parity gap. Evidence, never rules |
| What is wrong with the UI, surface by surface? | [`docs/ui-inventory.md`](docs/ui-inventory.md) |
| What does the Organize result grid have to look like? | [`docs/organize-grid-design.md`](docs/organize-grid-design.md) |
| What is the plan for React, and what is already settled? | [`docs/react-migration-plan.md`](docs/react-migration-plan.md) |
| **What can the CLI do that the app cannot?** (the UI arc's real cost) | [`docs/cli-app-parity.md`](docs/cli-app-parity.md) - **5 subcommands with no route, plus `catalog --move`**, and **five** partial, counted from the table on 2026-08-30. ⚠ **BOTH numbers have been wrong in the other document while right here.** The partial count said *six* there until 2026-08-30; the no-route count said five while the table held **six**, because `rename` had its own row rather than a place in the list - and it became right by `(aix)` stage 3 shipping a route, which is luck, not maintenance. **Count the table.** Completeness pinned by a test **in one direction only** - every CLI subcommand appears; an app-only capability has no row at all, which is `(ahg)`. The route column is a human read |
| What did soak one do, and why is its record a reconstruction? | [`docs/soak-one-record.md`](docs/soak-one-record.md) - **ran 2026-08-20, written 2026-08-22**: the run that overturned the most, rebuilt from commits because no record was kept. **One of its six findings is still open** - it said two until 2026-08-27, and `(aep)` has shipped |
| What will soak two cover, and what could soak one not have seen? | [`docs/soak-two-plan.md`](docs/soak-two-plan.md) - the plan; §1 carries the corpus ruling |
| What did soak two actually find? | [`docs/soak-two-record.md`](docs/soak-two-record.md) - **ran 2026-08-21**, a record: five findings, and three harness defects that nearly became false ones |
| What is soak three, and why refusal? | [`docs/soak-three-plan.md`](docs/soak-three-plan.md) - the plan; the thesis is the stock-take at the end of the soak-two record |
| What did soak three find? | [`docs/soak-three-record.md`](docs/soak-three-record.md) - **ran 2026-08-21**, a record: four findings, and the two most dangerous properties held |
| What will soak four cover, and why has nothing soaked the deleting commands? | [`docs/soak-four-plan.md`](docs/soak-four-plan.md) - the plan; `reclaim` and `clean-empty`, and the method a destructive soak needs |
| What did soak four find? | [`docs/soak-four-record.md`](docs/soak-four-record.md) - **ran 2026-08-22**, a record: four findings, and the two properties most likely to destroy irreplaceable data both held |
| What did soak five find, and which half is missing? | [`docs/soak-five-record.md`](docs/soak-five-record.md) - **ran 2026-08-25**, a record: the whole library, every feature. Zero resolver decisions changed across 10,745 files and `Input/` byte-identical after every run; two findings, one withdrawn, and the reversal paths deliberately **not** soaked |
| What is soak seven, and why a manufactured mess? | [`docs/soak-seven-plan.md`](docs/soak-seven-plan.md) - the plan; the shape table with the field evidence behind each, the prediction written **before** the run, and the honest limit. Built by `scripts/make_messy_corpus.py`; the corpus is not committed |
| What did soak six find, and what does a lost catalog cost? | [`docs/soak-six-record.md`](docs/soak-six-record.md) - **ran 2026-08-25**, a record: the reversal paths and the rebuild drill. Backup verified AT THE DESTINATION, `(agm)`'s retention-one argument demonstrated live, and the founding *"categories are recomputable"* falsified |
| What did soak eight find on a manufactured mess? | [`docs/soak-eight-record.md`](docs/soak-eight-record.md) - **ran 2026-08-29**, a record: 8,970 files / 18.7 GB of deliberate mess. 500 of 500 stripped copies filed away from their dated twin, **zero false perceptual pairs**, and **two of my own predictions missed** |
| How do I cut a release, and what has already been proven? | [`docs/release-rehearsal-record.md`](docs/release-rehearsal-record.md) - **ran 2026-08-30**, a record: the publish job's five never-executed steps, run for the first time on a throwaway tag. Six assets, checksums and **`cosign verify-blob` verified BY HAND**. The one honest delta is `--draft`, so `gh release create` is rehearsed as a mechanism and unrehearsed as a publication |
| What did soak nine find with five fixes in place? | [`docs/soak-nine-record.md`](docs/soak-nine-record.md) - **ran 2026-08-30**, a record: the same 8,951-file mess with `(aid)`, `(aie)`, `(ain)`, `(aim)` and the encoding work shipped. **Nothing lost across five full-corpus runs, three with a syscall refused for every file**; the reversal arc closes (666 restored, tree identical); perceptual recall **identical to soak eight** and zero false pairs over 3.1 M comparisons. ⚠ **Two of the five fixes could not be exercised by the corpus at all** |
| What happens on exFAT, on real removable media? | [`docs/soak-ten-record.md`](docs/soak-ten-record.md) - **ran 2026-08-31**, a record: the first filesystem that refuses on its own. The exFAT answer key (a **third** outcome - a call that succeeds and does nothing), `(aie)` and `(ain)` proved unable to fire here, the **durability window** where success is reported before the medium has the bytes, and an unclean pull that resurrected **4.3 GB of deleted directory entries** while every byte of file content survived. ⚠ **The mid-write pull is named as NOT measured** |
| What survives an INTERRUPTED write, on three filesystems? | [`docs/soak-eleven-record.md`](docs/soak-eleven-record.md) - **ran 2026-08-31**, a record: exFAT, NTFS and FAT32, **three physical mid-write pulls**. The damage shape is set by the filesystem and the window size by the **mount options** - 836 zero-byte on exFAT, 304 unreadable on NTFS (which **refused to mount**), 38 on FAT32 because `flush` kept 16 MB in flight instead of 3.5 GB. **`verify` caught every damaged file on all three; `rescan` caught 2, 304 and 1.** `(aix)`'s rename measured mid-flight on NTFS, and **nine predictions with five misses** |
| What happens to the one file on a drive that is not a photograph? | [`docs/soak-twelve-record.md`](docs/soak-twelve-record.md) - **ran 2026-08-31, written the next day** deliberately, against soak one's cost: the damaged-`.truestill-decisions.json` matrix, six shapes. `(aje)` - `read_decisions` promised *"Never raises"* and raised on invalid UTF-8, bricking every catalog open from an **unguarded** seam. The run **died at row three** and the preserved tree's missing fourth directory is the evidence. ⚠ **The app half RAN 2026-09-01**, on unprivileged loop devices, and found `(ajg)`: `backup` still crashes on a vanished drive because `(ajd)` caught one exception class and there are two. The app was **better** than the CLI there, inverting `(aiq)`. Four predictions, two correct, one missed, one half |
| What did the Organize design spike establish? | [`docs/organize-preview-record.md`](docs/organize-preview-record.md) - the findings, kept because the spike itself is gitignored |
| What are the rules for TypeScript, React, Tailwind and Rust? | [`docs/frontend-and-shell-standard-research.md`](docs/frontend-and-shell-standard-research.md) - a **record**, not the canon |
| What does Google Takeout actually put on disk? | [`docs/takeout-format.md`](docs/takeout-format.md) |
| What does each package do? | [`packages/truestill-core/README.md`](packages/truestill-core/README.md) · [`packages/truestill-cli/README.md`](packages/truestill-cli/README.md) · [`packages/truestill-app/README.md`](packages/truestill-app/README.md) |
| What are the test fixtures, and what may I regenerate? | [`packages/truestill-core/tests/fixtures/README.md`](packages/truestill-core/tests/fixtures/README.md) |
| What does the date resolver decide over the real corpus, and why is that snapshot not CI coverage? | [`tests/golden/README.md`](tests/golden/README.md) - `record`/`check` on demand; the differential logic alone is CI-tested |
| What is the contract oracle, and why is it never regenerated? | [`packages/truestill-app/tests/fixtures/contract-oracle/README.md`](packages/truestill-app/tests/fixtures/contract-oracle/README.md) - the spec of 2026-09-03 and `openapi-typescript`'s 3,793-line rendering of it, frozen; `scripts/emit_api_types.py` is accepted against the pair byte for byte, because TypeScript 7 left the tool nowhere to run |

### The records - historical, never rewritten

**They record what was investigated and when.** Some predate the `vaeon` → `truestill` rename and
say so inline; where one has been overtaken it carries a dated **superseded-by** header. They are
never rewritten to match the present - a record that is edited to stay correct stops being a
record. **When a research doc and `IMPLEMENTATION_STANDARDS.md` disagree, the contract wins.**

- **Dates and metadata** - [`date-provenance-design.md`](docs/date-provenance-design.md),
  [`date-layering-gap-check.md`](docs/date-layering-gap-check.md),
  [`date-resolver-corpus-measurement.md`](docs/date-resolver-corpus-measurement.md),
  [`metadata-chain-research.md`](docs/metadata-chain-research.md),
  [`messenger-dates-research.md`](docs/messenger-dates-research.md)
- **Layout and organizing** - [`org-structure-research.md`](docs/org-structure-research.md),
  [`default-layout-research.md`](docs/default-layout-research.md),
  [`legacy-decommission-research.md`](docs/legacy-decommission-research.md) (the close of the
  year-first arc, "Done 2026-07-28"),
  [`adaptive-day-folder-research.md`](docs/adaptive-day-folder-research.md),
  [`migration-routing-research.md`](docs/migration-routing-research.md),
  [`empty-folder-cleanup-research.md`](docs/empty-folder-cleanup-research.md)
- **Grouping and naming** - [`trip-grouping-research.md`](docs/trip-grouping-research.md),
  [`events-clustering-research.md`](docs/events-clustering-research.md),
  [`folder-name-suggestion-research.md`](docs/folder-name-suggestion-research.md),
  [`local-naming-research.md`](docs/local-naming-research.md),
  [`reverse-geocoding-research.md`](docs/reverse-geocoding-research.md),
  [`filename-safety-research.md`](docs/filename-safety-research.md)
- **Drives and recovery** - [`drive-identity-research.md`](docs/drive-identity-research.md),
  [`decisions-on-drive-research.md`](docs/decisions-on-drive-research.md)
- **UI and shell** - [`ui-v1-research.md`](docs/ui-v1-research.md),
  [`ui-v2-research.md`](docs/ui-v2-research.md),
  [`tauri-sidecar-lifecycle-research.md`](docs/tauri-sidecar-lifecycle-research.md)
- **Audits and QA** - [`code-quality-audit.md`](docs/code-quality-audit.md),
  [`architecture-excellence-2026-audit.md`](docs/architecture-excellence-2026-audit.md) (advisory;
  no implementation authorized), [`format-coverage-audit.md`](docs/format-coverage-audit.md),
  [`walkthrough-qa-report.md`](docs/walkthrough-qa-report.md),
  [`job-run-skeleton-diff.md`](docs/job-run-skeleton-diff.md) (**FROZEN RECORD - SUPERSEDED**)
- **Handoffs** - dated state checks, each a snapshot of its own day and never superseded by the
  next: [`handoff-2026-08-24.md`](docs/handoff-2026-08-24.md), [`handoff-2026-08-25.md`](docs/handoff-2026-08-25.md),
  [`handoff-2026-08-27.md`](docs/handoff-2026-08-27.md), [`handoff-2026-08-31.md`](docs/handoff-2026-08-31.md),
  [`handoff-2026-09-01.md`](docs/handoff-2026-09-01.md). Their defect classes are indexed in the current handoff
- **Measurement** - [`preview-performance-profile.md`](docs/preview-performance-profile.md),
  [`testing-new-corpus.md`](docs/testing-new-corpus.md),
  [`ado-webkit-tail.md`](docs/research/ado-webkit-tail.md) (the WebKit-tail investigation, closed
  2026-08-15 - census, retired hypotheses and the experiment that ended it)

New here? `docs/PROJECT_STATUS.md` **§0** is the fresh-clone setup, **§1** is where the project
stands, **§1b** is the build order the rest sits inside, **§2** is what ships next and **§3** is
what blocks it. `default-layout-research.md` holds
the layout design and the flip, but read its own header first - its status line predates the build.

### Live refs - what exists on the remote besides `main`

**No branches. `git ls-remote --heads origin` shows `main` alone**, which is how the maintainer
wants it (2026-08-15). Unmerged work that must survive lives under a **tag** instead:

**Preserved work, one row each - and there is none today:**

| tag | peels to | owned by |
|---|---|---|
| *(none)* | | |

⚠ **RELEASE TAGS ARE DELIBERATELY NOT LISTED HERE, ruled 2026-09-03 (P204), and the table said so
about its own only row before it was removed.** That row was `v0.1.0`, and its own words were *"a
**release** tag, not preserved work - the only ref here that is meant to be permanent"* - the table
describing an entry that did not belong to it. It then drifted exactly as that admission predicts:
`v0.1.1` was published 2026-09-03 and **got no row**, so a section whose closing line is *"verify
rather than trust this table"* was itself unverified. **The two kinds of ref have opposite
maintenance models**, which is the whole reason:

- A **release tag** is generated by a process, permanent, and **completely enumerable by command** -
  so a row adds nothing a command does not give and must be hand-written at every tag. It would have
  drifted again at `0.1.2`.
- A **preserved-work ref** is the thing the rule below actually governs, and **no command can
  classify one**: `git ls-remote` lists refs, it cannot say which are owned by a backlog entry.
  That judgement is why this table exists, and it is the only thing it should carry.

```sh
git ls-remote --tags origin   # every tag, releases included
gh release list               # which of them are published, and which is Latest
```

⚠ **THERE IS NO PRESERVED WORK ON THE REMOTE AS OF 2026-08-31, and that is the rule finishing
rather than the rule lapsing.** `preserved/abw-finding-3` (`66f6c22`, 148 lines, was the branch
`wip/trip-rename-finding-3`) held `(abw)` finding (3)'s unmerged attempt from 2026-08-15 until
`(aix)` shipped the feature and **refused that shape** - it renamed the catalog row and left the
disk alone. Superseded work is not unmerged work, so the rule below stopped protecting it and
started applying to it, and it was deleted with the maintainer's authorisation.

**Why it was a tag for those sixteen days, which is the rule applied rather than dodged:** those
148 lines existed on the remote *only* as that branch - `66f6c22`'s own message reads *"preserved
from stash@{0}"* - so deleting it **then** would have returned them to a local stash on one
machine, which is the exact leak this section was written about. A tag is a remote ref like any
other: it survives a fresh clone, and it keeps the branch list clean. `git show <tag>` reads one,
`git switch -c <name> <tag>` resumes one. ⚠ **The stash it was copied from no longer exists**
(`git stash list` is empty), so by the end the tag was the only copy - which is why deleting it
needed the entry's analysis first, and got it.

⚠ **THE RULE: a ref that outlives its session is named here and owned by a backlog entry, or it
is deleted.** No third option, and a tag is not an exemption from it - it is a way to satisfy the
first half. A branch nobody knows about **looks like safety and behaves
like a leak** - it is not in `main`, so no gate runs it, no guard reads it and no review sees it,
while everyone assumes the work is "kept somewhere".

This is the week-old stash one layer up, and that is not an analogy - it is the same failure with
a wider blast radius. That stash held 148 lines including a test, was invisible to
`git stash show --stat` (which does not list the untracked file it carried), and would not have
survived a fresh clone. **A stash is at least obviously personal; a pushed branch looks
institutional and is not.** Both are one command from gone and neither is anyone's job to notice.

**Verify rather than trust this table** - `git ls-remote --heads origin` and `git ls-remote --tags
origin` are the source, and a row here that no longer resolves is the same drift the document map
exists to prevent.

## Working here - the day-to-day

### Repo shape

- `packages/truestill-core/` - core library and safety-critical logic.
- `packages/truestill-cli/` - `truestill` command surface.
- `packages/truestill-app/` - local web UI (`truestill-app`), imports core only.
  `frontend/` is the React + TypeScript + Vite + **Tailwind v4** source, with shadcn components
  under `src/components/ui/`; its build output is `static/dist/` (`main.js` and `main.css`).
  Tailwind aliases `tokens.css` and defines nothing of its own.
- `docs/` - decisions, standards, backlog, and research records.

### Practical reminders

- **Inner loop: targeted tests only.** Never the full gate on an edit.
- **`make check` before every commit** - it runs against a **45 s ceiling** (`TEST_SECONDS_MAX`),
  which is not friction. ⚠ This said *"19-21 s"* until 2026-08-15; nine runs that day read
  **16.39-25.99 s**, outside the band at both ends. The ceiling is the durable number.
- **The pre-commit hooks are NINE: ruff, ruff-format, mypy, three prose guards (`dash-style`,
  `product-name`, `no-redirect-artifacts`), two commit-msg guards (`no-ai-coauthor`,
  `entry-closure`) and the pre-push `push-gate`. They do not run the suite, and their green
  output is not the gate.** Written down 2026-08-12 because it was broken
  that day by someone working to this standard: the hooks print a column of green immediately
  above the commit, `make check` does not, and the eye takes the nearer one. A red suite reached a
  commit and the letter-uniqueness test was what caught it. Same class as `(ace)` and the closure
  rule - a rule that lives only in practice gets broken by someone who can quote it.
  ⚠ **THE COUNT READ *"three prose guards and two"* AND OMITTED `push-gate` UNTIL 2026-08-24** -
  and the omitted one is **the only hook here that can refuse a push**, which is this paragraph's
  own subject. A sentence about not trusting a column of green left out the single entry in that
  column with the power to stop you. It is `.pre-commit-config.yaml`'s `push-gate`,
  `stages: [pre-push]`, `verbose: true`; `scripts/check_push_gate.py` is what it runs.
  ⚠ **AND THE WORD READ *"EIGHT"* UNTIL 2026-08-26 WHILE ITS OWN LIST ENUMERATED NINE**
  (3 + 3 + 2 + 1). `git log -S` finds one commit for it: `96af43a` - **the very commit that added
  `push-gate` because it had been left out**. The list was corrected and the number was left at
  its pre-correction value, so a paragraph about not trusting a column of green shipped with a
  count that disagreed with the column beside it. Twice now, the same failure, one level down.
  ⚠ **SOMETHING PINS THIS SENTENCE NOW, AND UNTIL 2026-08-26 NOTHING DID.**
  `test_the_hook_census_is_not_a_guess.py` parses `.pre-commit-config.yaml`'s hook ids and asserts
  both halves into the bullet above: the **word** equals the count, and **every id is named**. The
  two are separate tests because the two drifts were different - 2026-08-24 lost a name while the
  count stayed honest, 2026-08-26 lost the count while the names stayed complete - and a guard
  checking one would have passed on the other. Both are proved by mutation.
  **This paragraph said the opposite until then, and applying `(ago)` is what changed it**: a
  census guard is a new artifact that has to earn itself, so it was recorded rather than guarded
  - correctly, on one drift. **Two drifts in the paragraph warning about this exact failure is the
  evidence that ruling asked for.** `test_push_gate_runs_under_pre_commit.py` still reads that
  file only to build a *fixture* config, and `test_live_documents_cite_code_that_exists.py` still
  cannot see prose; neither was ever the census.
- ⚠ **DO NOT run `make gate` for backend work** (changed 2026-08-20). `make check` before every
  commit, as always; the browser lane is **not** part of the routine loop. If a change genuinely
  reaches a screen, **say so and ask** rather than running it by reflex. **The test of "reaches a
  screen" is whether the change could make a screen STOP SHOWING SOMETHING** - deleting a payload
  field a renderer reads is exactly that, and `(aer)` did.
- ⚠ **AND WHEN IT IS ON: THE AFFECTED FILES FIRST, THE FULL LANE ONCE** (2026-08-21). Run the
  `tests/e2e/` files whose subject the diff touches - about **two minutes** - and iterate there;
  run the full lane **once, before the commit**, for what the affected files could not see. Never
  iterate on the full lane. `(aer)` is why: one 28-minute run returned 6 red, and the finding in
  it - a wording collision two of the failing files assert against directly - was reachable in the
  first two minutes. The other fifty-eight were spent waiting rather than on the work it created.
- **The CI e2e job runs NIGHTLY and on `workflow_dispatch`, not on push** (re-decided
  2026-08-22; it was `if: false` from 2026-08-20). A push still costs ~3 minutes, and the browser
  lane is no longer dark - it is **scheduled** for 03:17 (`ci.yml`'s `cron: "17 3 * * *"`) and can
  be fired on demand. ⚠ **SCHEDULED IS NOT WHEN IT RUNS, and this line said *"it runs at 03:17"*
  until 2026-09-01**: that morning's run was queued and started at **08:40Z**, five hours and
  twenty-three minutes late. GitHub documents this - *"the `schedule` event can be delayed during
  periods of high loads"*, and it recommends avoiding the top of the hour, **which `ci.yml` already
  does and says so in its own comment**. So the mitigation is applied and the delay happened
  anyway: the cron is a request, not a promise. `gh run list --commit <sha>` is the answer to
  *"has the browser lane seen this commit yet?"*, and on a morning like that one it has not.
  ⚠ **The lane's SIZE is a command, never a number here**; it read *"the 470 browser tests"* until
  2026-08-22, and every figure written in since has rotted within days -
  `uv run pytest tests/e2e --collect-only -q | grep -oE '[0-9]+ tests collected'`.
  ⚠ **The old condition, *"the first migrated screen"*, could not fire**: `(adi)` migrates by
  ISLAND, not by screen. **Per-push returns when the lane finishes in under ~8 minutes** - a lever
  that exists and is unused, since `make e2e` is serial across two browsers while `pytest-xdist`
  is already a dependency and `make test` already uses `-n auto`.
  ⚠ **A path filter was refused with a proof, not a hunch**: `(afo)` touched core, an app service
  and the CLI, **no markup path**, and changed wording two `tests/e2e/` files assert directly.
  ⚠ **Its silence is not coverage** - `ENGINEERING_STANDARD.md` §4's fifty-fourth member. The three
  `check` lanes are deliberately kept because they are the only thing that sees Windows and macOS,
  and on 2026-08-20 alone they caught `timeout(1)` not existing on BSD and Windows being unable to
  execute a bash script.
- `make gate` and `make e2e` still work locally and are unchanged; the browser lane stays out of a
  fresh clone's path, and `make check` is green with no browser installed.
  `IMPLEMENTATION_STANDARDS.md` §6.1 is the binding rule.
- **Proving a guard bites is a separate step from writing it**, and there are two tools.
  `scripts/mutate_once.py` for the single proof you write while fixing something - it refuses on a
  missed or ambiguous anchor rather than reporting success, which `sed -i` does not: a reflowed
  target cost three false proofs in one day, each a green run against unmutated code.
  `uv run python scripts/mutation_matrix.py --suite <name>` for a whole suite. Not in `make check` -
  it costs minutes. It reports two different findings: a test no mutation kills (unproven), and a
  mutation that kills no test (missing guard, or dead code). `ENGINEERING_STANDARD.md` §4,
  fiftieth member.
- ⚠ **`warnings.catch_warnings` IS UNUSABLE IN THIS CODEBASE'S HOT PATH, so do not reach for it.**
  It assigns process-global `warnings.filters` and `warnings.showwarning`, and `scan.py` hashes on
  a `ThreadPoolExecutor` **by default** - CPython says the behaviour is *undefined* with two or
  more threads. The `ContextVar` fix landed in **3.14** behind a flag that is **off** on
  non-free-threaded builds; this project runs **3.14** as of 2026-08-22 (`DECISIONS.md` D13) and
  the flag is still `0` there, measured. Use `truestill_core.decode_noise`, which
  installs once per process and carries the argument. `(aev)`
  ⚠ **Upgrading did not change this** - measured on 3.14.4 after the move: the flag is still `0`.
  The rule is written against the FLAG, not the version, which is why adopting 3.14
  (`DECISIONS.md` **D13**) left it standing.
- ⚠ **AD-HOC BENCHMARKS: `/tmp` IS tmpfs - RAM, not disk.** The suite already runs on real
  ext4 by `suite_scratch.py`'s recorded decision; an ad-hoc script does not inherit it and
  measures RAM while claiming disk. Four findings were mislabelled that way on 2026-08-23 and one
  ruling reopened at **41x**. Use `suite_scratch.scratch_root()` / `/data/tmp/truestill`, or
  state the filesystem in the write-up. This line is the decision's *reach*, not a new rule.
- ⚠ **THE SESSION SCRATCHPAD IS ON /tmp TOO - tmpfs - and it held 11 GB on 2026-08-23**,
  filling swap to 98% twice in two days (`suite_scratch.py` is the decision; this is its reach
  again, one layer up). `TMPDIR=/data/tmp/truestill` is set machine-locally in
  `.claude/settings.local.json` and **verified**: a fresh session's `tempfile.gettempdir()`
  answers `/data/tmp/truestill`, so tempfile and subprocess writes land on ext4. **Whether the
  scratchpad PATH itself follows TMPDIR is not yet observed** (headless sessions create none;
  check the next interactive session). Until observed: anything larger than ~100 MB - corpora,
  measurement trees, catalogs - goes under `/data/tmp/truestill/<purpose>` by rule, and an
  experiment deletes what it grew. Preserved evidence is different and goes beside
  `scratch-race-2026-08-22` on `/data/TruestillLibrary`, never in a session directory.
- ⚠ **CITE A SYMBOL, NEVER A LINE NUMBER** (2026-09-01, `(ago)`). A living document writes
  `drive.py:library_independence`, not that function's line number, and
  `uv run python scripts/cite_symbols.py <doc>` converts one. **The guard refuses a line wherever a
  symbol encloses it**, so the old format cannot come back by habit;
  `test_live_documents_cite_code_that_exists.py` is the rule.
  🔑 **Why, measured**: a **fifteen-line comment** added to `app.js` displaced **46 citations
  across 16 documents, 18 of them live**, and the guard saw none of them - every one landed on real
  code. A content hash was **refused on a measurement**: 83 of 220 cited symbols changed body in
  twelve days, so it would have demanded 83 re-records in that window to catch a class the evidence
  does not show. **Records keep line numbers** and that is a decision, not an unfinished migration -
  a living document must resolve *today*, a record says what was true *when it was written*.
  ⚠ **The cost is real and stated**: 207 citations point inside a body, so a reader now scans the
  enclosing symbol - median 32 lines, 12% over 80. Where precision matters, quote the line in the
  prose. `ENGINEERING_STANDARD.md` carries the full ruling.
- ⚠ **A CENSUS OR A CLAIM IS RE-RUN BEFORE IT IS ACTED ON, and this cost four entries in one week**
  (2026-09-01). `(aht)` said nothing removes the archive staging tree - `archive_extract.clear_staging`
  exists, is tested, and is **never called**. `(ss)` says organize preview *"hashes every file"* -
  `scan.py`'s `_needs_sha` pre-filters by size and perceptual hashing is conditional. `(acg)` said
  album membership travelled unresolvably - **it did not travel at all**. And a correction written
  the day before said *"silent on every screen"* when **the app has no restore route at all**.
  🔑 **Each was a sentence that was nearly right and wrong about one surface**, and each survived
  because the check that produced it was never re-run. **Read the body, then run its check** - the
  entry's own text is a premise, not evidence.
  ⚠ **AND SWEEP THE WHOLE TREE, NOT `*.md`** (2026-09-03, `(aka)`). A correction to a factual
  claim is only as wide as its pathspec, and **the pathspec is the one part of a sweep nothing
  reports back to you**. P204 corrected *"the publish job has never run"* in three documents and
  reported the class closed; `git grep -nI -e "<claim>" -- . ':!*.md'` found a fourth copy the next
  day in `ci.yml`'s banner - the text a person reads when deciding whether to dispatch the browser
  lane before tagging. Prose is load-bearing in workflow comments, docstrings, `Makefile` and
  `pyproject.toml` here. **Use `git grep -nI -e "<claim>" -- .` and read each hit before calling it
  a defect** - one of the five hits was `afg.md`, already corrected on the day it expired.
  **No guard is possible**: a guard would have to know a sentence is false.
- ⚠ **QUOTE THE LINE, DO NOT SUMMARISE IT** - when a finding rests on a transcript, a run record
  or a log, **paste the line into the entry**. Two of four entries filed on 2026-08-31/09-01 had a
  mechanism that had to be corrected - `(aiq)` and `(aji)` - and **both times the wrong claim was
  a summary of evidence already in hand, and the right one was a line that could have been
  pasted**. `(aja)` and `(ajb)` quote their transcripts verbatim and neither needed correcting.
  ⚠ **NO GUARD IS POSSIBLE HERE and that is stated rather than left as a gap**: nothing in this
  repo reads an evidence transcript (`test_live_documents_cite_code_that_exists.py` reads *code*
  citations), and a guard that did would be asserting that a person read a file to its end, which
  is unobservable. `(ago)`'s bar refuses one in its own words - it *"would have gone red on the
  past on the day it was written"*. **This is a practice, and it costs nothing.** `(ajk)`
- `exiftool` must be installed and on PATH for metadata paths.

### The corpora - three of them, and they answer different questions

**`IMPLEMENTATION_STANDARDS.md` §5 is the source for all of this**; what follows is the short form
so a new session does not have to be told. ⚠ **The fence is unchanged: `/home/dinesh/pCloudDrive/`
and `/home/dinesh/Icedrive/` are never read, walked or stat'd, at any depth, under any flag.**
*(Since 2026-08-23 two enforcement layers back it - permission deny rules and a sandbox
read-deny, both tested; `IMPLEMENTATION_STANDARDS.md` §5's fence row carries the layers and
their limits. The rule above stays the rule - the layers are backstops.)*

| corpus | what it is | what it can answer |
|---|---|---|
| `~/TruestillLibrary/` | **free scratch, entirely.** Nested folders, N copies, deliberately messy trees - **no permission needed, ever** | how the product behaves on a real library at real scale |
| `~/ad/application/exif-samples` | ianare's repo, 115 files / 54 MB | **format edges** |
| `~/ad/application/metadata-extractor-images` | drewnoakes' repo, 10,703 files / 2.8 GB, 52 format dirs | **format edges**, plus 1,461 deliberately fuzzed files |

Copy from the two repos into `TruestillLibrary` freely - they are outside the library and outside
every fence.

⚠ **THEY ARE A DIFFERENT AXIS FROM SCALE, AND SIZE CANNOT SUBSTITUTE FOR IT.** Soak one was 4,111
files from **one person's devices**: it covers the formats those devices emit and nothing else. A
maker note that parses wrong, an orientation tag in an unexpected place, a container exiftool reads
differently - **none of those can appear in such a corpus however large it grows.** `(adp)` is the
precedent: 33% of a real corpus drawn sideways, found only by rendering real photographs. A curated
format corpus is that move aimed at **parsing** rather than rendering. Measured 2026-08-21: the two
repos hold **1,428 organizable files across 38 distinct media extensions**, against a real library
that is overwhelmingly one lineage of `.jpg`.

**Any observation of `TruestillLibrary` is a SNAPSHOT** - never a fixture, never a design premise.
The two repos are different in kind: version-controlled and reproducible anywhere, so a finding
against them is citable by commit rather than by date.
