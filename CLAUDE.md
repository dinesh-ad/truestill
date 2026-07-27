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
| Why is the product this way? (settled stances, no accounts/telemetry) | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| What is approved but unbuilt? | [`docs/BACKLOG.md`](docs/BACKLOG.md) |
| How does the code lay out day to day? | [`docs/CLAUDE.md`](docs/CLAUDE.md) |
| What does it cost, and what should I not "optimize"? | [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) |
| What changed and when? | [`CHANGELOG.md`](CHANGELOG.md) |

Research and QA records (`docs/*-research.md`, `docs/walkthrough-qa-report.md`) are
historical: they record what was investigated and when. Some predate the
`vaeon` → `truestill` rename and say so inline.
