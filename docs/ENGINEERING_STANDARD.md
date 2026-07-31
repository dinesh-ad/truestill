# truestill - Engineering Standard (the canon)

Portable principles for working in truestill. This is the *generic* tier. The repo-specific,
checkable rules live in [`IMPLEMENTATION_STANDARDS.md`](IMPLEMENTATION_STANDARDS.md), which
**wins on any conflict**. Keep this file short: every rule below is one you can actually
violate in *this* repo. If a rule can't be violated here, it doesn't belong here.

truestill is a **local-first CLI/library** heading toward a desktop app. It has no server, no
network API boundary, no untrusted multi-tenant input. Do not import server-SaaS machinery
(pagination, circuit breakers, DTO layers, telemetry stacks, GDPR tooling). Right-size.

## 1. Total cost of ownership

- **Justify every component with a measured need.** A dependency, a table, a layer of
  indirection, a cache - each earns its place by solving a problem you can point at, not one
  you imagine. Written justification lives in the dependency inventory.
- **Reliability over novelty.** Prefer the stdlib and the boring, proven approach. New tech
  needs a reason the old tech can't serve.
- **Defer until a concrete trigger appears.** Don't build the abstraction for the second
  backend until the second backend exists. Leave a seam, not scaffolding.

## 2. The three-phase workflow

**Reconnaissance → Implementation → Verification.** Do them in order; don't blur them.

1. **Reconnaissance.** Read the actual code first. Report truth as `file:line`. No design, no
   edits in this phase - just establish what *is*. Claims about behaviour must be grounded in
   files, never in memory ("I think it does X" is banned; go read it).
2. **Implementation.** Grounded in the research priority order (§3). Make the smallest change
   that is correct. Match the surrounding code's idioms.
3. **Verification.** Run the full gate matrix and report the **exact output**. "Tests pass" is
   not a report; the passing summary line is. If a step is skipped, say so.

**The gate matrix has three layers, and a change is verified at the layer it can break.**

| Layer | Command | Owns |
|---|---|---|
| Static | `ruff check` / `ruff format --check` / `mypy` | Style, imports, types |
| Engine | `pytest` (`make check`) | Behaviour: dating, dedup, layout, catalog, custody, safety gates |
| Client | `pytest tests/e2e` (`make e2e`) | What a user actually reads on screen |

The third layer is not optional garnish. It exists because a whole class of defect - the
product describing itself incorrectly - is invisible to the first two, and shipped repeatedly
before it existed. **If a change alters anything a user reads, it is not verified until the
browser lane has run.** Conversely, do not re-assert engine behaviour through a browser: it is
slower, flakier, and already covered. Each layer owns what only it can see.

Three standing rules on that third layer: **no sleeps** (auto-waiting assertions only - hard
waits are the dominant flake source), **no retries** (a retry-until-green browser suite
launders the nondeterminism the layer exists to expose; a flaky test is quarantined and filed
with its trace), and **UI source assertions are not coverage of a flow**. Grep-style checks
that a string exists in shipped JS/HTML pin wiring; they do not prove a multi-step or
destructive path works. Any such path needs a real browser test that drives the UI and
asserts on what a user reads. *Worked example - migration undo resume, 2026-07-29.* After a
cancelled undo apply, `panel.innerHTML = summary + panel.innerHTML` re-parsed the armed card
and wiped the Preview onclick - resume looked present and was dead. Source guards still
passed; only the Playwright e2e caught it.

## 3. Research priority order

When you need to know how something behaves, consult in this order and stop when answered:

1. **This repo's own docs** - they outrank everything else for product and contract questions.
   `IMPLEMENTATION_STANDARDS.md` wins on conflict; then `DECISIONS.md`, `BACKLOG.md`,
   `PROJECT_STATUS.md`, and dated `docs/*-research.md` records. A research record is not
   rewritten to stay current; when it and the contract disagree, the contract wins.
2. **The source itself** - read the code; claim behaviour with `file:line`, never from memory.
3. **Official docs / RFCs / language references** (free and public).
4. **Upstream issue trackers & maintainer responses** on free public forges - especially for
   tools that already fought the battle you're fighting (the failure modes are catalogued there).
5. **Existing patterns in this repo** - reuse the helper that exists; don't duplicate it.
6. **Mature-project practice** visible in free public sources - how well-run projects solve it.

Forbidden: asserting library behaviour without verifying it; copying a stale blog pattern;
re-implementing something the repo already has.

### 3.1 No paid third-party research or tooling (standing, 2026-07-30)

**Do not use, authenticate, or suggest any paid third-party service** for research or agent
work. That includes parallel.ai, commercial research APIs, hosted tools that require an
account or API key, and anything that would add a paid dependency or credential prompt. This
is **in addition to** the no-new-dependency rule (§4 Dependencies): even a free trial that
needs signup is out.

Research is done from: this repo's docs, the source, and **free public** sources. If a question
cannot be answered without a paid service, **STOP and report the gap plainly** - that is a
legitimate answer. Do not sign up, do not prompt for credentials, do not add the service as a
dependency, and do not treat "I could look it up on a paid API" as progress.

## 4. Code standard

- **Idioms (Python 3.13, standard build).** `pathlib.Path` for all path manipulation - never
  `os.path.*` in source (an audit on 2026-07-29 found zero call sites; this codifies that
  practice, it is not a migration). Use `os` only for operations pathlib does not expose:
  `os.access` for permission probes, `os.utime` for setting mtime/atime, `os.cpu_count` for
  worker sizing. Directory walks that need the dir-tree shape use `Path.walk` (3.12+), not
  `os.walk` and not `rglob`. `@dataclass(slots=True)` for internal models. `StrEnum` for
  enumerations. `match` for structured dispatch, f-strings, `:=` where it reads better.
  **Not** pydantic/attrs for internal models - truestill has no untrusted-input API boundary,
  so stdlib dataclasses are the right-sized choice. Validation belongs only at real trust
  boundaries (CLI args, sidecar JSON, catalog reads).
- **Absolute imports only (standing, 2026-07-30).** Every import under `packages/` is absolute
  (`from truestill_app.service.fs_browse import …`, `import truestill_app.service.fs_browse`).
  No relative imports (`from .…`, `from ..…`, `from . import …`). Relative imports are the
  natural reach during a package split and make each subsequent move harder to reason about -
  the importing file no longer names where the symbol lives. Enforced by
  `packages/truestill-app/tests/test_absolute_imports.py`; a guard that has not been seen to
  fail is not a guard (§4 below).
- **Typing.** mypy `strict` is mandatory. Full annotations incl. return types; modern syntax
  (`X | None`, `list[str]`, `Self`). No untyped defs. No `type: ignore` without a reason code
  and a comment.
- **Dependencies.** Minimal by principle. Every runtime dep justifies itself against a stdlib
  alternative **in writing**. Lower-bound + lockfile; no blind upper-pins; `uv.lock` is the
  source of truth; updates happen via a periodic `uv lock --upgrade` review.
- **Performance.** Stream files in chunks - never read a whole media file into memory. One
  disk pass per file per run wherever possible. Concurrency via a worker pool for I/O-bound
  batches. No accidental O(n²): any nested iteration over the library carries a comment
  proving its bound.
- **Tests (enrichment over count).** Every feature gets: a happy path, the edge cases the
  research phase surfaced (forum-mined failure modes *are* the test spec), an
  idempotency/re-run test wherever state is touched, and cross-platform-safe assertions
  (compare paths via `.as_posix()`, never `str(Path)`). Prefer fixtures, `parametrize`,
  `tmp_path`, and injected input over TTY. A test that merely restates the implementation is
  not coverage. Test count is never a target - it changes; don't cite it as done-ness.
- **A regression fixture must be validated by running it against the bug it guards.**
  **A fixture that cannot fail against the bug is not a regression test** - it is a test of
  something else that happens to pass. Reintroduce the defect (revert the constant, restore the
  old branch), confirm the fixture *fails*, then restore and confirm it passes. Until that has
  been done, a green fixture is evidence of nothing.

  *Worked example - the event-clustering fix, 2026-07-28.* The defect: a cut threshold defined
  relative to local density, so a burst-shot day shattered into fragments. The first regression
  fixture used **uniform** 8-second spacing and passed under the broken rule exactly as happily
  as under the fixed one - a purely relative threshold has nothing to cut on when every gap is
  identical, so **the fixture reproduced the very flaw it was meant to catch**. The second
  attempt added 7-minute pauses and still did not discriminate: against an 8-second median that
  is `ln 420 - ln 8 = 3.85`, just under the 4.0 threshold, so it passed *by luck*. Only a
  10-minute pause (`4.20`) actually reproduced the failure. Both attempts were green, and both
  were worthless, and only running them against the bug showed which.

  This is the same reasoning as the E2E lane's no-retry rule and the mutation checks used on the
  commit-msg hook and the type fence: **a guard is not known to work until it has been seen to
  fail.**
- **A guard test must be proven not to cry wolf: assert it ignores legitimate look-alikes.**
  The sibling of the rule above, and the failure it prevents is worse. A fixture that cannot fail
  is merely worthless; a guard that fires on ordinary input gets **switched off**, taking its real
  coverage with it. So a guard states both halves: what it catches, and what it must let through.

  *Worked example - the mangled-dash guard, 2026-07-28.* It rejects `word` + hyphen + space +
  `word`, the shape a botched em-dash sweep leaves in shipped copy. That pattern is one character
  away from things this repo is full of: `year-first`, `re-hash`, `2014-08-15`, `--apply`. The
  test asserts all four are accepted, in the same test that asserts the real damaged string is
  rejected. Without the second half the guard would have been disabled the first time someone
  wrote a hyphenated compound, and nobody would have recorded why.

  The same shape applies wherever a check is a heuristic over real content: **name the
  look-alikes and pin them**, or the check has a short life.
- **A guard must still be AIMED at the thing it guards. A monkeypatch targets the module that
  *owns* the name, never a re-export of it.** The third member of this family, and the one with
  no symptom: the two rules above are about a guard that cannot fail, this is about a guard that
  stopped being connected to its subject and reports success either way.

  Python binds names, not references. `from x import f` in module `b` creates `b.f`; patching
  `a.f` afterwards does not change what `b` calls. So a patch aimed at a facade re-export reaches
  the real code only while the caller also goes through that facade - and stops the moment the
  implementation moves, silently, with the test still green.

  *Worked example - the F10 service split, 2026-07-30.* `truestill_app/service.py` became a
  package whose `__init__.py` is 78 re-export bindings and zero definitions. Two tests patched
  through it. `tests/e2e/test_busy_state.py` patched `service.migration_preview` while
  `service/migrate.py` called its own global: the blocking wrapper never ran, so **one** test
  failed outright and **two** kept passing without exercising the per-drive lock they exist to
  pin. `test_inventory.py` patched `service.organize_preview` to prove `organize_inventory` never
  routes through the expensive path - both functions live in `service/organize.py`, so injecting
  the exact defect it names left the test **green**. Neither was detectable by reading the test:
  both looked correct and had been correct when written.

  The failing test is the lucky case. The one that keeps passing is the one that costs you a
  defect later, because nothing ever goes red to say the coverage left.

  **Enforced** by `packages/truestill-app/tests/test_patch_targets_stay_aimed.py`, which reads
  submodule-ness from the live package rather than a hardcoded list, so a new surface is covered
  the day it is added; it is pinned against both real defects above and against the correctly
  aimed forms it must not disturb. Where a seam cannot be checked mechanically, the rule still
  stands and the aim is a review question.
- **A guard must assert what the promise is, not what happens to have survived.** The fourth
  member of this family, and the subtlest: the first three are about a guard that cannot fail,
  is switched off, or is aimed at the wrong module. This one is aimed at the right module and
  the wrong *subject* - it checks a thing that is true while the promise it stands for is
  broken, and reports success.

  *Worked example - the date confirmation, 2026-07-31.* The obligation was that a human-confirmed
  date survives a re-ingest. The test asserted that the confirmation row survived in
  `date_confirmations`. It passed. Measured directly, the **file row had reverted**: a confirmed
  2011 date was back to the 2014 filename evidence, and the next `migrate-layout` would have
  re-rendered the file to 2014 with the confirmation sitting intact and ignored beside it. The
  storage survived; the promise did not. Rewritten to assert **the date the library is actually
  filed under**, it failed, and found a real defect in `record_uploaded`.

  The question to ask of any guard: *if this assertion passed and the feature were still broken,
  what would that look like?* If you can describe it, you are asserting the wrong subject.

- **Errors.** Exceptions typed and specific - no bare `except`. User-facing CLI errors are
  actionable sentences, not tracebacks. Every subprocess call checks its return code and
  surfaces stderr on failure. Partial-failure policy: one bad file never aborts a batch - it
  is logged, counted, and reported at the end.

## 5. When to break a rule

Rules bend when the situation demands - but a violation must be **explicit, commented, and
contained.** Write the comment for the next engineer: state *what* rule you're breaking and
*why*, right at the site. The test is simple - a new engineer reads the comment and
understands, with no archaeology. An uncommented deviation is a bug, not a judgement call.
