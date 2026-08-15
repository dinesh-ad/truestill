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

On 2026-08-15 those read **133** and **78**, leaving **55** mapped below.

### The canon - binding, kept current

| Question | Document |
|---|---|
| Where does the project stand? What is next? | [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) |
| How do I work here? (workflow, research order, code standard) | [`docs/ENGINEERING_STANDARD.md`](docs/ENGINEERING_STANDARD.md) |
| What are the binding rules? (invariants, architecture, data, gates) | [`docs/IMPLEMENTATION_STANDARDS.md`](docs/IMPLEMENTATION_STANDARDS.md) |
| Why is the product this way? (settled stances: accounts, licensing, monetization) | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
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

### Live branches - what exists on the remote besides `main`

| branch | at | what it is |
|---|---|---|
| `wip/trip-rename-finding-3` | `66f6c22` | `(abw)` finding (3), **analysed and not merged** - a feature question, not a defect. See [`research/backlog/abw.md`](docs/research/backlog/abw.md). |

⚠ **THE RULE: a branch that outlives its session is named here and owned by a backlog entry, or
it is deleted.** No third option. A branch nobody knows about **looks like safety and behaves
like a leak** - it is not in `main`, so no gate runs it, no guard reads it and no review sees it,
while everyone assumes the work is "kept somewhere".

This is the week-old stash one layer up, and that is not an analogy - it is the same failure with
a wider blast radius. That stash held 148 lines including a test, was invisible to
`git stash show --stat` (which does not list the untracked file it carried), and would not have
survived a fresh clone. **A stash is at least obviously personal; a pushed branch looks
institutional and is not.** Both are one command from gone and neither is anyone's job to notice.

**Verify rather than trust this table** - `git ls-remote --heads origin` is the source, and a row
here that no longer resolves is the same drift the document map exists to prevent.

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
- **The pre-commit hooks are lint, format, typecheck and the trailer rules. They do not run the
  suite, and their green output is not the gate.** Written down 2026-08-12 because it was broken
  that day by someone working to this standard: the hooks print a column of green immediately
  above the commit, `make check` does not, and the eye takes the nearer one. A red suite reached a
  commit and the letter-uniqueness test was what caught it. Same class as `(ace)` and the closure
  rule - a rule that lives only in practice gets broken by someone who can quote it.
- **`make gate` when the diff reaches the browser.** It runs `check`, then `e2e` only if the diff
  touches `packages/truestill-app/src/` or `tests/e2e/`, and prints what decided it. The reason
  for skipping the browser lane is a command's output, never a recollection.
- The browser lane stays separate from `make check` and out of a fresh clone's path: `make check`
  is green with no browser installed. `IMPLEMENTATION_STANDARDS.md` §6.1 is the binding rule.
- **Proving a guard bites is a separate step from writing it**, and there are two tools.
  `scripts/mutate_once.py` for the single proof you write while fixing something - it refuses on a
  missed or ambiguous anchor rather than reporting success, which `sed -i` does not: a reflowed
  target cost three false proofs in one day, each a green run against unmutated code.
  `uv run python scripts/mutation_matrix.py --suite <name>` for a whole suite. Not in `make check` -
  it costs minutes. It reports two different findings: a test no mutation kills (unproven), and a
  mutation that kills no test (missing guard, or dead code). `ENGINEERING_STANDARD.md` §4,
  fiftieth member.
- `exiftool` must be installed and on PATH for metadata paths.
