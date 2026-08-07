# CLAUDE.md

truestill - a local-first media organizer, de-duplicator, and backup pipeline (uv workspace:
`truestill-core` library + `truestill-cli` + `truestill-app`).

The command is `truestill`; the local web UI is `truestill-app`. Drives are identified by a
`.truestill-drive.json` marker (pre-rename `.vaeon-drive.json` drives are still read - see
`IMPLEMENTATION_STANDARDS.md` §3.1).

## Read first, every session

0. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) - **start here.** Where the project
   stands, what ships next, and the standing rules. Read it before doing anything else.
1. [`docs/ENGINEERING_STANDARD.md`](docs/ENGINEERING_STANDARD.md) - the portable canon.
2. [`docs/IMPLEMENTATION_STANDARDS.md`](docs/IMPLEMENTATION_STANDARDS.md) - the binding,
   repo-specific contract.

**`IMPLEMENTATION_STANDARDS.md` wins on any conflict.**

## The document map - which doc answers which question

| Question | Document |
|---|---|
| Where does the project stand? What is next? | [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) |
| How do I work here? (workflow, research order, code standard) | [`docs/ENGINEERING_STANDARD.md`](docs/ENGINEERING_STANDARD.md) |
| What are the binding rules? (invariants, architecture, data, gates) | [`docs/IMPLEMENTATION_STANDARDS.md`](docs/IMPLEMENTATION_STANDARDS.md) |
| Why is the product this way? (settled stances: accounts, licensing, monetization) | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| What is approved but unbuilt? | [`docs/BACKLOG.md`](docs/BACKLOG.md) |
| How do I move libraries to another machine? | [`docs/moving-machines.md`](docs/moving-machines.md) |
| How does the code lay out day to day? | [`docs/CLAUDE.md`](docs/CLAUDE.md) |
| What does it cost, and what should I not "optimize"? | [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) |
| What does the product look like? (wordmark, colour, icons) | [`docs/brand.md`](docs/brand.md) |
| What is wrong with the UI, surface by surface? | [`docs/ui-inventory.md`](docs/ui-inventory.md) |
| How do I report a vulnerability, and what is in scope? | [`SECURITY.md`](SECURITY.md) |
| What changed and when? | [`CHANGELOG.md`](CHANGELOG.md) |

Research and QA records (`docs/*-research.md`, `docs/walkthrough-qa-report.md`) are
historical: they record what was investigated and when. Some predate the
`vaeon` → `truestill` rename and say so inline; where one has been overtaken by later work it
carries a dated **superseded-by** header. They are never rewritten to match the present - a
record that is edited to stay correct stops being a record. **When a research doc and
`IMPLEMENTATION_STANDARDS.md` disagree, the contract wins.**

New here? `docs/PROJECT_STATUS.md` **§0** is the fresh-clone setup, **§1** is where the project
stands, **§2** is what ships next and **§3** is what blocks it. The closed year-first layout arc
is no longer summarised there; the record of its **close** is
[`docs/legacy-decommission-research.md`](docs/legacy-decommission-research.md) ("Done
2026-07-28"). [`docs/default-layout-research.md`](docs/default-layout-research.md) holds the
design and the flip, but read its own header first - its status line predates the build.
