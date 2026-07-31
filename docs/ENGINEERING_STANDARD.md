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

- **When a fix lands on one surface, ask where else the rule is written down - not whether the
  other surface has a test.** The CLI and the app implement one contract twice (62 core symbols
  are imported by both), so a repair that reaches one copy and not its twin is a standing risk
  rather than an accident. It has now happened three times: F0 (migrate-undo fixed,
  organize-undo not), F38 (twelve job sites updated, one missed), and `cli.py:513`.

  **A second test would have caught the drift; a shared home would have made it impossible.**
  §9 already proves the pattern works - `models.status_label` and `models.date_quality` have
  exactly one home each, which is why the CLI and the app *cannot* word an outcome or count a
  date-quality signal differently. The dual-hash rule never got one: "the expected hash is
  `copy_sha256`, never `sha256`" was written at two call sites, so correcting one left the other
  silently wrong, and the CLI had no test because the rule had been **copied instead of
  shared**. Missing coverage was the symptom; duplication was the cause.

  So the remedy for any instance is usually to delete one of the two copies, not to add a second
  assertion. **Enforced** by `packages/truestill-app/tests/test_surface_parity.py`, which flags a
  catalog-row rule expressed at a call site on one surface and not its twin - and which protects
  the *repair*, not the contract: before the `cli.py:513` fix both surfaces agreed and both were
  wrong, and it scored zero. A green run there means the two copies match, never that they are
  right.

- **A mutation proof must show that the mutant is the code under test.** The fifth member of
  this family. The other four are about a guard that cannot fail, is switched off, is aimed at
  the wrong module, or asserts the wrong subject. This one is about the *proof of a guard* -
  the step taken to demonstrate a test can fail - and it goes wrong the same way: it reports
  success while proving nothing.

  Breaking the code and watching a test go red is what separates a guard from a decoration. But
  the mutation and the test run are two different things, and **nothing checks that they met.**
  When they do not, the test passes, and a passing test is read as "the mutation was caught by
  something else" or "the guard is fine" rather than "the mutant was never loaded."

  *Three worked examples, one session, 2026-07-31 - different mechanisms, same root cause.*

  1. *The editable install.* The mutation was written into a `cp -r` copy of `packages/` under
     the scratch directory, then `pytest` was pointed at the copy's test file. The copy's tests
     `import truestill_app...`, which the venv's **editable install resolved back to the real
     repo**. All ten tests passed against an unmutated implementation. Re-run with `PYTHONPATH`
     ahead of site-packages, six failed.
  2. *The stale worktree.* The mutation was applied inside `git worktree add --detach <path>
     HEAD`, but the code under test was **uncommitted**. The worktree was a faithful copy of a
     tree that predated the guard entirely, so the import failed - and had the guard merely been
     *older* than the change rather than absent, it would have run happily against the wrong
     code and passed.

  3. *The mutation that never applied.* An anchor string was replaced in a scratch copy, but the
     formatter had reflowed that code since it was written, so the replacement matched nothing
     and silently did nothing. `__file__` **confirmed the mutant tree was loaded** - and the run
     came back green, which reads as "the guard is weak". It was not evidence at all: the tree
     was loaded and unmutated. This one is a layer deeper than the other two, because the
     identity check the rule already demanded *passed*.

  One resolved past the mutant, one never contained it, one contained the file but not the
  change. All three **failed in the reassuring direction**, which is the family resemblance: a
  mutation proof that silently proves nothing leaves a guard everyone now believes has been
  verified. Three different mechanisms, one root cause - which is what makes this a rule rather
  than a habit.

  **The requirement: assert BOTH that the mutant is the loaded code AND that the mutation is
  present in that loaded source, before trusting the result.**

  A mutation can also be *correct* and still do harm - it is the one case in this family that
  does not fail in the reassuring direction. See the isolation rule below: **mutating a guard
  can disable the isolation that guard provides**, so a proof of a path-resolution bug runs the
  very code that ignores the redirect.

  * *Identity:* `assert str(mutant_root) in module.__file__` for an imported module, the
    equivalent for anything else; for a subprocess, print the resolved path and check it.
  * *Presence:* assert the change is actually there - `assert "<the removed line>" not in
    inspect.getsource(target)`, or have the patch script fail loudly when its anchor does not
    match. A silent `str.replace` that finds nothing is the failure mode; make it raise.

  *A proof that cannot say which file it loaded is not a proof - and one that cannot say the
  change is in that file is only half of one.* When a mutated run does not fail, the first two
  questions are whether it ran the mutant and whether the mutant was mutated. Only after both
  are answered is "the test is weak" a conclusion rather than a guess.

- **When something's status changes, grep for every reference to it before reporting.** The
  sixth member of this family, and the one that applies to *documents*. The others are about a
  guard; this is about a **claim** - something correct where you edited it, while its dependents
  go on asserting the old answer. A stale cross-reference is a document stating something false,
  and the reader most likely to hit it is a cold start with no way to tell.

  *Worked examples - 2026-07-31, and the point is that I reported "no stale status" twice and
  was wrong twice.*

  1. *The restructure.* `BACKLOG.md`'s "Approved, not yet built" was split by real status, and
     `(n)` and `(ii)` were left in "Ideas / deferred" while their own text said *mostly built*
     and *half built*. The entries were right; the section contradicted them.
  2. *The closure.* Closing `(aaj)` left `(bbb)` saying *"the half that is missing is recorded
     as `(aaj)`"* and the Converged programs block saying *"the unbuilt half of item 4 is
     `(aaj)`"*. I found the first by grepping after the fact, **missed the second**, and only
     caught it when building the gate below - a third instance, after two manual sweeps.

  Both times the entry body was checked and the **references to it** were not. One `grep` for
  the identifier would have found all of them, which is what makes this mechanical rather than a
  matter of care.

  **Enforced** by `packages/truestill-app/tests/test_backlog_references.py`: an item in a
  settled section (built, or out of scope) that another line describes as unfinished. Scoped by
  measurement, not preference - **0** hits before `(aaj)` was closed, **2** at the moment it
  was, **0** after repair - and the phrase list deliberately excludes "remains" and "deferred",
  which legitimately describe a settled item's reasoning. Where a dependency cannot be checked
  mechanically, the rule still stands and the grep is the review step.

- **A test must not be able to write to a real user location - make it impossible, not
  forbidden.** Any code that resolves an OS-conventional directory (`platformdirs`, `~`,
  `%APPDATA%`) will resolve it *for the test suite too*. The remedy is a **session fixture that
  points those roots at a temporary directory**, so isolation holds by construction. A rule
  people remember is not a remedy: nobody writing a feature test is thinking about the
  developer's home directory.

  *Worked example - `(aae)`, 2026-07-31.* Moving the default catalog to `user_data_dir` froze it
  in a module constant at import, so no override could reach it and no test could isolate it.
  Every test running a default-`--db` command wrote a real `catalog.sqlite` into the user's data
  directory. **Both CI runners did it, and so did the developer's machine** - the stray file was
  found and deleted afterwards. Fixed by resolving per call, honouring `TRUESTILL_DATA_DIR` /
  `TRUESTILL_CACHE_DIR` on every platform, and a root `conftest.py` redirecting both roots for
  the session.

  **Two techniques worth keeping from how it was found, because they generalise.**

  1. *A constant computed at import is unpatchable, and therefore un-isolatable.* Resolve
     any default that depends on the environment or the filesystem **at the point of use**.
     The symptom is a
     test that cannot influence behaviour it obviously should be able to.
  2. ***`make check` can pass for the wrong reason, and a clean-checkout run is how you find
     out.*** Here the suite was green locally only because the working copy contained a
     **gitignored** `reports/catalog.sqlite` that a fresh clone does not have. Reproducing with
     `git ls-files -z | tar --null -T - -cf - | tar -xf - -C <tmp>` - a copy of exactly what is
     tracked, nothing else - reproduced CI's failure locally in one run. **Reach for it whenever
     CI fails and local passes**: the difference is almost always untracked state.

     One trap in the technique itself: the copy has no `.git`, so every guard that enumerates
     via `git ls-files` fails with exit 128 and looks like a real regression. Run `git init -q .
     && git add -A && git commit` in the copy before trusting its result.

  **Isolation has now failed three times, from three different directions.** That is what
  decides the shape of the check.

  1. *The import-time constant.* The default was frozen at import, so no override could reach it
     and no test could isolate it. Real catalogs were written on two CI runners and one
     developer machine.
  2. *The shared temporary root.* A test that **creates** the standard catalog wrote into the
     session-wide redirected root. Isolation from the real home held perfectly; isolation
     between tests did not, and every later test asserting "No catalog yet" failed depending on
     the order it ran in.
  3. *The mutation proof itself.* Proving the `catalog` command ignored `TRUESTILL_DATA_DIR`
     meant **running the code that ignores it**. The redirect was in place and irrelevant: the
     mutant did not consult it, and the run wrote a real 160 KB catalog into
     `~/.local/share/Truestill`. The proof was valid; the side effect was not.

  Each one arrived somewhere the previous fix did not cover, and the third was produced *by the
  act of verifying the second*. So the standing check is not "remember to isolate" - that is
  what failed each time - but:

  > **Verify the real location is untouched.** Before and after any mutation of a
  > path-resolution or isolation mechanism, look at the actual OS directory. `ls` it; note
  > whether it existed and when it was last written.

  A mutation deliberately removes a safety property, and the isolation the suite depends on may
  *be* that property. Assume the redirect does not hold while the mutant is loaded, and confirm
  by looking rather than by reasoning - reasoning is what produced all three.

     *Second occurrence, two hours later, and what promotes this from anecdote to rule.* The
     next CI failure was lint, and local was green again - this time because of a **gitignored
     `.ruff_cache`**. The sharper lesson, which the first case did not show:

     > **A cached check can be stale for a reason that has nothing to do with the cached file.**

     Ruff caches a verdict per file, keyed on that file's contents plus the config. Adding a
     root `conftest.py` made the bare name `conftest` resolve as first-party, which changed how
     **six untouched files** classified their imports. Neither their contents nor the config
     changed, so the cache could not see it and replayed six stale *clean* verdicts. The same
     clean-checkout copy caught it on the first run.

     **The consequence, applied.** A gate that can report a stale pass is not a gate, so `make
     lint` runs `ruff check --no-cache`. Measured cost of giving up the cache on this repo:
     0.04s to 0.08s. Weigh any local cache the same way - if bypassing it is cheap, bypass it,
     because the failure mode is not a slow gate but a **silent** one.

- **Errors.** Exceptions typed and specific - no bare `except`. User-facing CLI errors are
  actionable sentences, not tracebacks. Every subprocess call checks its return code and
  surfaces stderr on failure. Partial-failure policy: one bad file never aborts a batch - it
  is logged, counted, and reported at the end.

## 5. When to break a rule

Rules bend when the situation demands - but a violation must be **explicit, commented, and
contained.** Write the comment for the next engineer: state *what* rule you're breaking and
*why*, right at the site. The test is simple - a new engineer reads the comment and
understands, with no archaeology. An uncommented deviation is a bug, not a judgement call.
