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

**Before building anything from `BACKLOG.md`, check `SHIPPED.md`.** The two share one letter
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

On 2026-08-22 those read **183** and **121**, leaving **62** mapped below. ⚠ They read **181**/**119**, **180**/**119** and **176**/**115** earlier that same day, **159**/**102** on 2026-08-21, **148**/**93** on 2026-08-20, **139**/**84** on 2026-08-19 and **133**/**78** on 2026-08-15 - stale within a day, three times - which is the argument for running the commands rather than for updating these numbers faster. **The mapped figure is the one to watch**: it held at 55 across four readings, moved to 56 on 2026-08-21 when `soak-two-plan.md` became the first document since 2026-08-15 to land outside `docs/research/backlog/`, and reads **61** on 2026-08-22 - `soak-two-record.md`, `soak-three-plan.md`, `soak-three-record.md`, `soak-four-plan.md` and `soak-four-record.md`, each of which has a row below. ⚠ **It then HELD at 61 across a second reading that day**, when the totals moved by four - four new backlog bodies, no new document outside them - which is the map working rather than the map going stale. It then moved to **62** with `soak-one-record.md`, which has a row below - a count that moves WITH a row is the map working; the failure is one that moves without. It **held at 62** when `afp.md` and `afq.md` landed, because both are backlog bodies and the exception covers them. A mapped count that moves **without** a row being added is the map going incomplete; a count that moves *with* one is the map working.

### The canon - binding, kept current

| Question | Document |
|---|---|
| Where does the project stand? What is next? | [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) |
| How do I work here? (workflow, research order, code standard) | [`docs/ENGINEERING_STANDARD.md`](docs/ENGINEERING_STANDARD.md) |
| What are the binding rules? (invariants, architecture, data, gates) | [`docs/IMPLEMENTATION_STANDARDS.md`](docs/IMPLEMENTATION_STANDARDS.md) |
| Why is the product this way? (settled stances: accounts, licensing, monetization, toolchain) | [`docs/DECISIONS.md`](docs/DECISIONS.md) - **D10**+**D13** on Python 3.14 (deferred, then adopted when the deferral's premise proved false), **D11** holds mypy, **D12** refuses Aceternity |
| What is approved but unbuilt? | [`docs/BACKLOG.md`](docs/BACKLOG.md) - the **index**; each entry's body is [`docs/research/backlog/<letter>.md`](docs/research/backlog) |
| **Is this already built?** (provenance - read before building anything) | [`docs/SHIPPED.md`](docs/SHIPPED.md) |
| What does it cost, and what should I not "optimize"? | [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) |
| What changed and when? | [`CHANGELOG.md`](CHANGELOG.md) |

### Guides and reference - current, not binding

| Question | Document |
|---|---|
| What is this project, and how do I install and run it? | [`README.md`](README.md) |
| How do I report a vulnerability, and what is in scope? | [`SECURITY.md`](SECURITY.md) |
| How do I move libraries to another machine? | [`docs/moving-machines.md`](docs/moving-machines.md) |
| What does the product look like? (wordmark, colour, icons) | [`docs/brand.md`](docs/brand.md) |
| Where did the brand artwork come from, and under what licence? | [`brand/PROVENANCE.md`](brand/PROVENANCE.md) · [`brand/README.md`](brand/README.md) |
| What is wrong with the UI, surface by surface? | [`docs/ui-inventory.md`](docs/ui-inventory.md) |
| What does the Organize result grid have to look like? | [`docs/organize-grid-design.md`](docs/organize-grid-design.md) |
| What is the plan for React, and what is already settled? | [`docs/react-migration-plan.md`](docs/react-migration-plan.md) |
| What did soak one do, and why is its record a reconstruction? | [`docs/soak-one-record.md`](docs/soak-one-record.md) - **ran 2026-08-20, written 2026-08-22**: the run that overturned the most, rebuilt from commits because no record was kept. Two of its six findings are still open |
| What will soak two cover, and what could soak one not have seen? | [`docs/soak-two-plan.md`](docs/soak-two-plan.md) - the plan; §1 carries the corpus ruling |
| What did soak two actually find? | [`docs/soak-two-record.md`](docs/soak-two-record.md) - **ran 2026-08-21**, a record: five findings, and three harness defects that nearly became false ones |
| What is soak three, and why refusal? | [`docs/soak-three-plan.md`](docs/soak-three-plan.md) - the plan; the thesis is the stock-take at the end of the soak-two record |
| What did soak three find? | [`docs/soak-three-record.md`](docs/soak-three-record.md) - **ran 2026-08-21**, a record: four findings, and the two most dangerous properties held |
| What will soak four cover, and why has nothing soaked the deleting commands? | [`docs/soak-four-plan.md`](docs/soak-four-plan.md) - the plan; `reclaim` and `clean-empty`, and the method a destructive soak needs |
| What did soak four find? | [`docs/soak-four-record.md`](docs/soak-four-record.md) - **ran 2026-08-22**, a record: four findings, and the two properties most likely to destroy irreplaceable data both held |
| What did the Organize design spike establish? | [`docs/organize-preview-record.md`](docs/organize-preview-record.md) - the findings, kept because the spike itself is gitignored |
| What are the rules for TypeScript, React, Tailwind and Rust? | [`docs/frontend-and-shell-standard-research.md`](docs/frontend-and-shell-standard-research.md) - a **record**, not the canon |
| What does Google Takeout actually put on disk? | [`docs/takeout-format.md`](docs/takeout-format.md) |
| What does each package do? | [`packages/truestill-core/README.md`](packages/truestill-core/README.md) · [`packages/truestill-cli/README.md`](packages/truestill-cli/README.md) · [`packages/truestill-app/README.md`](packages/truestill-app/README.md) |
| What are the test fixtures, and what may I regenerate? | [`packages/truestill-core/tests/fixtures/README.md`](packages/truestill-core/tests/fixtures/README.md) |

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
- **Measurement** - [`preview-performance-profile.md`](docs/preview-performance-profile.md),
  [`testing-new-corpus.md`](docs/testing-new-corpus.md),
  [`ado-webkit-tail.md`](docs/research/ado-webkit-tail.md) (the WebKit-tail investigation, closed
  2026-08-15 - census, retired hypotheses and the experiment that ended it)

New here? `docs/PROJECT_STATUS.md` **§0** is the fresh-clone setup, **§1** is where the project
stands, **§2** is what ships next and **§3** is what blocks it. `default-layout-research.md` holds
the layout design and the flip, but read its own header first - its status line predates the build.

### Live refs - what exists on the remote besides `main`

**No branches. `git ls-remote --heads origin` shows `main` alone**, which is how the maintainer
wants it (2026-08-15). Unmerged work that must survive lives under a **tag** instead:

| tag | peels to | what it is |
|---|---|---|
| `preserved/abw-finding-3` | `66f6c22` | `(abw)` finding (3), **analysed and not merged** - a feature question, not a defect. Was the branch `wip/trip-rename-finding-3`. See [`research/backlog/abw.md`](docs/research/backlog/abw.md). |

**Why a tag rather than deleting it, and this is the rule below applied rather than dodged:**
those 148 lines existed on the remote *only* as that branch - `66f6c22`'s own message reads
*"preserved from stash@{0}"* - so deleting it would have returned them to a local stash on one
machine, which is the exact leak this section was written about. A tag is a remote ref like any
other: it survives a fresh clone, and it keeps the branch list clean. `git show <tag>` reads it,
`git switch -c <name> <tag>` resumes it.

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
- **The pre-commit hooks are ruff, ruff-format, mypy, three prose guards (`dash-style`,
  `product-name`, `no-redirect-artifacts`) and two commit-msg guards (`no-ai-coauthor`,
  `entry-closure`). They do not run the suite, and their green output is not the gate.** Written down 2026-08-12 because it was broken
  that day by someone working to this standard: the hooks print a column of green immediately
  above the commit, `make check` does not, and the eye takes the nearer one. A red suite reached a
  commit and the letter-uniqueness test was what caught it. Same class as `(ace)` and the closure
  rule - a rule that lives only in practice gets broken by someone who can quote it.
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
  lane is no longer dark - it runs at 03:17 and can be fired on demand. ⚠ **This said *"the 470
  browser tests"* until 2026-08-22, when the lane held 502**; count it rather than quote it -
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
- `exiftool` must be installed and on PATH for metadata paths.

### The corpora - three of them, and they answer different questions

**`IMPLEMENTATION_STANDARDS.md` §5 is the source for all of this**; what follows is the short form
so a new session does not have to be told. ⚠ **The fence is unchanged: `/home/dinesh/pCloudDrive/`
and `/home/dinesh/Icedrive/` are never read, walked or stat'd, at any depth, under any flag.**

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
