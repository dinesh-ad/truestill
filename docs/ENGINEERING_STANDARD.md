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

**A check run in the wrong shell is a measurement error, and this one flatters.** `zsh` does not
word-split an unquoted variable, so `FILES="a b"; cmd $FILES` passes **one** argument where `sh`
passes two - and a `git diff -- $PATHS` or a `pytest $TARGETS` built that way silently matches
nothing and reports **clean**. It happened twice in one session, both times returning the
reassuring answer about code that was fine. Quote the expansion, pass the arguments literally, or
run the check under `sh -c` - and when a verification comes back green faster or quieter than
expected, suspect the harness before believing it.

**The gate matrix has three layers, and a change is verified at the layer it can break.**

| Layer | Command | Owns |
|---|---|---|
| Static | `ruff check` / `ruff format --check` / `mypy` | Style, imports, types |
| Engine | `pytest` (`make check`) | Behaviour: dating, dedup, layout, catalog, custody, safety gates |
| Client | `pytest tests/e2e` (`make e2e`) | What a user actually reads on screen |

**Which layer to run, and when - the decision is a command, not a judgement.** Targeted tests in
the inner loop, seconds. `make check` before every commit. **`make gate`** before a commit whose
diff reaches the browser: it runs `check`, then `e2e` only when the diff touches
`packages/truestill-app/src/` or `tests/e2e/`, and prints the files that decided it either way.
The justification for skipping the client layer must be output you can paste. Measured
2026-08-10: check 19-33 s for 2,080 tests, e2e ~6.5 min for 412. Full rule and its costs:
`IMPLEMENTATION_STANDARDS.md` §6.1, which is binding.

**Never the full gate on an edit.** That premise is what made the gate feel expensive.

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

  **Creating a file with explicit permissions is NOT one of the exceptions - pathlib does it,
  and `os.open` here is a bug rather than a style choice.** Settled 2026-08-01 while writing the
  session URL file, and recorded because `os.open(p, O_CREAT | O_WRONLY | O_TRUNC, 0o600)` looks
  exactly like the atomic, careful answer. It is not. Measured:

  * `Path.open` has **no** permissions parameter (its `mode=` is `'r'` / `'w'`), and
    `write_text` alone gives the umask default - **0664** on the machine this was measured on,
    i.e. a credential readable by the whole group.
  * `Path.touch(mode=0o600)` **does** set permissions, but only when it creates the file. On an
    existing file it leaves the mode alone and does not truncate.
  * A mode is applied **only at creation** - so `os.open(..., 0o600)` over an existing 0644 file
    leaves it **0644** and writes the secret into it. Verified.
  * `os.open` with `O_CREAT` **follows a symlink** at the target path and writes through it.
    Verified: the secret landed in the link's victim file.

  So the sequence is `unlink(missing_ok=True)` → `touch(mode=…)` → `write_text`. It is pure
  pathlib *and* strictly safer than the one-syscall version: the unlink both guarantees the mode
  is applied and removes a symlink instead of writing through it. Guarded by
  `test_session_link.py`, which pins the pre-existing-mode and symlink cases specifically -
  a test that only writes to a fresh path passes against both implementations.
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

  *Five worked examples - different mechanisms, same root cause. The first three are one
  session, 2026-07-31; the fourth and fifth are 2026-08-04, and they are what promote this from
  "three ways one session went wrong" to a shape that keeps recurring. The last two are a
  mirrored pair: one restored what the mutation removed, the other removed what the work added.*

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

  4. *The package manager put it back.* Proving a guard fires when a dependency is missing meant
     uninstalling it and running the suite. The runner was `uv run pytest`, and **`uv run`
     re-syncs the environment before it runs anything** - it reinstalled the package that had
     just been removed, and the suite went green against an unmutated world. The tell was in the
     probe printed beside the run: it reported the dependency **present** immediately after the
     uninstall reported removing it. The fix is to stop going through the runner: invoke the
     venv interpreter directly (`.venv/bin/python -m pytest`), or block the import with a
     `PYTHONPATH` shim the runner has no opinion about.
     Same family as the editable install above - something between the mutation and the
     assertion restores the world - but a different mechanism, and a more inviting one, because
     the command that undoes the mutation is the same command everything else in the repo is run
     with. **Suspect it whenever the mutation is to the *environment* rather than to the source:
     a dependency, a lockfile, an installed binary.** A source mutation the runner cannot see is
     safe from this; an environment one is exactly what it exists to repair.

  5. *The restore threw away the work.* Not a mutation that failed to apply - a **restore** that
     removed more than the mutation. After proving one mutant, the file was put back with
     `git checkout -- <file>`, which restores from **HEAD**: the change being developed was
     uncommitted, so it went with the mutation. The next mutation would then have run against a
     file that no longer contained the feature, and every assertion about it would have been
     measuring the old code while reading as a result about the new.
     The tell was the presence check: a restore that is supposed to be a no-op reported the
     feature's own constant **absent** - `grep -c` returned 0 - immediately after a "restore".
     The fix is to save the original **by content** before mutating, write it back afterwards,
     and **assert the file is byte-identical** to what was saved. `git` cannot tell your work
     from your mutation; a saved string can.
     **This is the mirror of the case above, and worth stating as a pair.** There, the
     environment restored what had been removed and the mutant never survived; here, the tool
     removed what had been kept and the *feature* never survived. Both leave a green suite that
     is measuring something other than the thing under test, and neither announces itself - so
     the check is the same in both directions: **verify the world is what you think it is at the
     moment the assertion runs, before and after.**

  One resolved past the mutant, one never contained it, one contained the file but not the
  change, one had it removed by the tool used to run the test, one had the *feature* removed by
  the tool used to undo the test. All five **failed in the reassuring direction**, which is the
  family resemblance: a
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

    **A presence assertion must name the CODE that was removed, never a bare identifier that
    also appears in prose.** Added 2026-08-03 after this failed twice in one session, and it
    fails in the *opposite* direction from the rest of this rule: the mutation was applied
    correctly and the check reported it as absent, which reads as "the patch did not land" and
    sends you re-patching working code.
    Both times the identifier appeared in the target's own **docstring** - these functions
    document their constants, so `assert "_RATE_FLOOR_SECONDS" not in getsource(f)` matched the
    prose that explains the constant rather than the `if` that used it. Once it was subtler
    still: the removed line was the only *printed* use of `inventory.audio`, but the same name
    survived in a reconciliation expression two lines down, so no single identifier could
    distinguish mutant from original.
    Assert the statement - `"elapsed < _RATE_FLOOR_SECONDS"`, `'audio  : {inventory.audio'` -
    and the check discriminates. The rule above already said *line*; this says why saying
    *identifier* instead is not a shortcut.

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

- **A test's precondition must be proven to hold at the moment it is asserted, not merely to
  have been set.** The seventh member, and a mechanism the other six do not cover: the *test
  framework itself* undoes the setup between the fixture and the assertion, so the test runs
  without its precondition and passes for the wrong reason.

  *Worked example - 2026-07-31, `(aad)`.* A fixture set `sys.stdout` and `sys.stderr` to `None`
  to reproduce a windowed launch. **pytest's capture plugin re-assigns both for the call
  phase, after fixture setup runs**, so by the time the test body executed the streams were
  ordinary capture objects again. Three tests passed while testing nothing. Verified both ways
  round before rewriting: fixture-set reads `False`, body-set reads `True`.

  The family resemblance is the ruff cache and the stale worktree - green while proving
  nothing - and the new cause is that **something between setup and assertion is entitled to
  change the world back**. Suspect it whenever a test manipulates state the framework also
  manages: streams, the working directory, signal handlers, the event loop, logging.

  *The check is one line: assert the precondition inside the test body, next to the assertion
  that depends on it.* If that is awkward, set it in the body too.

- **Where two defences catch the same case, assert PROVENANCE, not the outcome.** The eighth
  member, and a mechanism none of the others covers. The other seven are about a guard that
  cannot fail, is switched off, is aimed at the wrong module, asserts the wrong subject, whose
  proof proves nothing, whose references go stale, or whose precondition is undone. This one is
  about a guard that is **correct, aimed correctly, and still cannot detect the thing it was
  written for** - because something *else* also catches it.

  A test that asserts *"this was refused"* answers *whether* something refused, never **which
  defence did**. Delete either one and the test stays green, so the guard silently stops
  guarding the specific protection it was written to pin.

  *Worked example - `(jj)` tar support, 2026-08-01.* Tar's safety rests on
  `tarfile.data_filter`, an argument a refactor drops without anyone noticing, so a test existed
  purely to fail if it were removed. It matched the word `"outside"` in the refusal message -
  and **our own `_validate_entry_name` says exactly that**, so it passed with `data_filter`
  deleted. It was asserting that *something* refused.

  The fix is to assert where the refusal **came from**. `tarfile.FilterError` can only be raised
  by the filter, and the refusal re-raises `from` it, so:

  ```python
  assert isinstance(raised.value.__cause__, tarfile.FilterError)
  ```

  fails the moment the call goes.

  **The honest half, and the reason the chain assertion is necessary rather than tidier:** with
  the filter removed, the *traversal* test still passes, because the local name validation
  catches that case too. Only the symlink and device-node tests fail on their own. Overlapping
  defences are usually good and should not be removed to make a test sharper - so the test is
  what has to change.

  *Suspect this wherever defence is layered:* validation plus a library's own check, a guard test
  plus a type, a refusal in two places. Ask **"if I delete the one I am pinning, does this test
  still pass?"** - and if the answer needs thinking about, assert the provenance.

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

- **Run the browser lane when browser-exercised *behaviour* changes, not when browser *files*
  change.** The ninth member, and the only one about *deciding to run a gate* rather than about
  writing one. The diff is a proxy for the wrong thing: a server-side refusal, a payload key or a
  status change can be invisible in `app.js` and fully visible to a Playwright assertion.

  *Origin, 2026-08-02.* `(aap)` taught `backup_preview` to refuse a folder that already holds a
  known library, returning the existing `{ok: false, error}` shape. `make e2e` was skipped on the
  stated grounds that **`app.js` was unchanged** - true, and irrelevant: the browser lane drives
  `#bk-preview` and reads what comes back, so a new refusal on that endpoint is squarely inside
  what it tests. The lane happened to stay green, so the wrong criterion cost nothing that day
  and would not have announced itself if it had been wrong.

  The question to ask is not *did I edit a file the browser loads* but *can a Playwright
  assertion see a different answer than before*. Anything reached over HTTP by the app - a
  service function, a payload key, a status code, a refusal string - is a yes. The lane is ~90 s
  and is not in `make check`, so the cost of running it when unsure is a minute; the cost of
  skipping it correctly-by-luck is a regression that surfaces on someone else's push.

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

- **When the thing under test SHARES A NAME with a system-provided equivalent, assert the
  DELIVERY MECHANISM, not the rendered result.** The tenth member. Closest to the eighth, and
  distinct from it in the way that matters: there, the competing defence is **ours**, so the
  question is which of two things we wrote did the work. Here the competitor is **the operating
  system**, which we did not write, do not ship, and cannot delete to find out - and on the
  developer's machine it is usually present, so the guard is at its weakest exactly where it is
  written.

  An assertion can be **non-vacuous in method and still vacuous in effect**. The method can be
  the strongest one available and the effect still nil, because the environment satisfies it
  independently of the artifact.

  *Worked example - bundling DejaVu Sans Mono, 2026-08-05.* The requirement was that the app ship
  its own monospace face rather than resolve one per OS. `getComputedStyle().fontFamily` was
  correctly rejected as vacuous: it echoes the declaration and passes with no font present. The
  replacement was CDP `CSS.getPlatformFontsForNode`, which reports what the **rasteriser** used -
  a genuinely stronger instrument, and the right one.

  It was still vacuous, because **the bundled family and the system font have the same name**.
  `DejaVu Sans Mono` is installed on the developer's Linux box, so CDP returns the expected
  string whether the bundle shipped or not.

  **The tell, and it only appeared because the mutation was run.** With the entire bundle
  stripped - no `@font-face`, the old stack restored - **7 of 10 browser tests still passed,
  including every one of the three CDP surface checks.** Review had read that suite as strong.
  It was strong against the wrong failure.

  The fix is to assert the **delivery mechanism**, each leg of which the operating system cannot
  satisfy:

  1. the **network response** - a 200 for the asset from our own origin (a *request* is not
     enough: a 404 still fires one, and the page falls back silently);
  2. **`document.fonts`** - it contains only `@font-face`-declared faces, never system ones, so a
     `loaded` entry there cannot have come from the OS;
  3. the **reachable `@font-face` rule** itself, asserted to use `url()` and not `local()` -
     `local()` would re-admit the system copy and make the whole distinction unobservable again.

  Those three are exactly the tests that failed under the mutant. Keep the rendered-result
  assertion too - it catches per-glyph fallback, which is a real and separate defect - but never
  let it stand alone.

  *Suspect this whenever the artifact under test has a same-named counterpart the machine may
  already provide:* a bundled font, a vendored library that is also installed, a shipped binary
  that is also on `PATH`, a config file that also exists in `/etc`. Ask **"if this artifact were
  absent, would the environment answer in its place?"** The name is what makes the substitution
  invisible, so the assertion has to reach for something the name does not confer.

  **This is the third time in one session (2026-08-04/05) that a mutation caught what review did
  not.** The other two are not recorded as rules because they were *badly aimed mutants* rather
  than new mechanisms - one changed a `viewBox` while the test compared path data, one changed a
  value the fixture rendered identically either way - and in both the mutation, not the reading,
  is what exposed it. Review reads a test and asks whether it looks strong; only the mutation
  asks whether it *is*. Where the two disagree the mutation is right, and the cost of skipping it
  is a suite everyone believes has been verified.

- **Assert that a stylesheet token RESOLVES, not that its text looks right.** The eleventh
  member, and the only one about a gate that cannot see the artifact at all. `make check` runs
  ruff, mypy and pytest; **none of them reads CSS**, so a stylesheet is unguarded except by the
  browser lane.

  *Origin, 2026-08-06.* A stray `*/` ended a comment in `tokens.css` two lines early. CSS error
  recovery discards the declaration that follows a parse error, so `--text-xs` stopped existing -
  silently, with the whole Python gate green. The existing guard read the token and asserted it
  did not end in `px`; an **empty value does not end in `px`**, so it passed too. What caught it
  was two unrelated browser tests, by three pixels of top-bar height.

  A missing token is not a smaller token: there is no rule, so the element inherits, and a 12px
  label becomes body size. Any guard that reads a custom property must therefore assert it is
  **non-empty first** and only then assert its shape - the shape check alone is satisfied by
  absence.

  The guard was proved against **the real malformed comment**, restored byte-for-byte, not a
  synthetic empty token. A synthetic one proves the assertion works; only the real defect proves
  it fires on the thing that actually happened.

- **A stub that never matched is indistinguishable from a stub that matched and returned
  nothing.** The twelfth member. Every assertion downstream of an unmatched stub is vacuous, and
  the test passes.

  *Origin, 2026-08-06 - three times in one session.* `ui.route("**/api/stats**", ...)` never
  matched, because the endpoint is `/api/library/stats`. The screen fell through to the real
  (empty) catalog, rendered its "Nothing to report yet" state, and a test looking for a string in
  the custody card found no string - and passed. The same shape twice more: a Backups test that
  stubbed the library total but not `/api/drives`, and a panel test whose `#panel` was
  `display: none` for want of a payload, so every measurement in it read zero.

  **The tell is that the screen renders NOTHING**, not that it renders something wrong. A test
  whose subject is missing entirely should be suspected of not being wired up, because a page
  with no data looks exactly like a page whose data said nothing.

  > **Assert the stub was HIT, not only that the page looks right.** Count the interception, or
  > assert a value that can only have come from the stub.

  All three passed review and all three were exposed by a mutation - the mutation removed the
  behaviour under test and the test still passed, which is the only signal that says *this test
  was never watching*.

- **A fixture whose SUBJECT never entered the code path produces the same observable as a
  successful run.** The thirteenth member. The others are about a guard that cannot fail, is
  switched off, is aimed at the wrong module, asserts the wrong subject, whose proof proves
  nothing, whose references go stale, whose precondition is undone, that a second defence also
  catches, that the OS satisfies, that reads a stylesheet, or that stubs a URL nothing requests.
  This one is about a **confirmation** - a fixture built to demonstrate a defect, which appears
  to demonstrate it while the code under test never ran.

  *Worked example - the rescan MOVED case, 2026-08-07.* The claim was that a hand-moved file
  reaches a specific branch and is then counted in no bucket. The fixture built a drive with
  catalog rows but **no marker on disk**, so `attach_drive` never reached that branch at all -
  the adoption guard answered first. The observables were **identical to a true confirmation**:
  the record still named the old path, and `linked` / `unmatched` / `unreadable` were all zero.
  Every assertion about the outcome passed. What separated them was a probe on the *subject*:
  `files hashed: []`. The file never became a candidate, so nothing about the branch was shown.

  The family resemblance to the mutation rules is exact, and so is the remedy. There, the
  question is *did the mutant load and was it mutated*; here it is **did the input reach the
  code you are making a claim about**. Both fail in the reassuring direction, and in both the
  outcome alone cannot tell you.

  > **Assert that the subject ENTERED the path, not only that the outcome looks right.** Count
  > the call, log the candidate, print what was actually read. An outcome reproduced for the
  > wrong reason is worse than no reproduction: it retires the question.

  *Suspect it whenever a fixture must satisfy preconditions to reach the code under test* - a
  marker file, a registered row, a mode flag, a non-empty index. The more setup a repro needs,
  the more ways it has to succeed without ever arriving.

  **THE SECOND ARRIVAL: THE DOUBLE THAT SHORT-CIRCUITS.** Added 2026-08-10, because the example
  above reaches the failure by an unmet *precondition* and this one reaches it through a stub
  that worked perfectly. **The tell is that the stub sits UPSTREAM of the thing under test**, and
  the value it returns makes the code exit before the subject runs. Note the boundary against the
  twelfth member: there the stub never matched; here it matched exactly as designed.

  *Worked example - the flake report's verdict guard.* The rule it enforces is that the script may
  never call a test flaky. It stubbed `_gh` to return `None`, which makes `main()` return at
  *"no runs to read"* - so it asserted on output the script had never produced. A mutation making
  it print `flaky: no` passed. The fix was to drive the stub through `run list` *and*
  `run download` against fabricated runs, so the assertions reach the lines they name.

  Two details from that repair are worth carrying:

  * **Assert on the OUTPUT, not the source**, when the rule is about what a program says. The
    docstrings arguing for this rule necessarily use the forbidden word, and a source scan would
    have been satisfied by them - and by any future column hiding behind them.
  * **A stub returning the "nothing here" value is the dangerous one.** `None`, `[]`, `{}` and
    `""` are exactly the values that make callers return early, so the most convenient stub to
    write is the one most likely to skip the code you are asking about.

  *Four instances in four subsystems inside two days* - the decisions fixture that seeded one
  trip, the `{event}` token under a scheme that never reaches it, a privacy filter test, and this
  one. That rate is the argument for treating "did my input arrive?" as a routine question rather
  than a post-mortem one.

- **A step that reports success is not evidence that it did anything.** The fourteenth member,
  and the one that reaches outside the test suite: the others are about a guard, a fixture or a
  proof, this is about **any mechanism whose green is the only thing anybody checks.**

  *Worked example - the CI trace upload, 2026-08-07.* §6 promises *"a red run arrives with a
  replay rather than a guess"*. The step ran on every failure, reported **success**, and
  uploaded **nothing**: `actions/upload-artifact` v4+ excludes hidden files by default and the
  output directory is `tests/e2e/.artifacts`, which is hidden. Artifact count on every run in
  the repository's history: **0**. Every browser failure this project has diagnosed was
  diagnosed without the replay, and nobody noticed, because the thing that would have said so
  was the step's own status.

  The family resemblance is exact. The stub whose route never matched rendered a page with no
  data and passed. The bundled font's absence left every CDP check green because the OS
  answered in its place. Here a collector collected nothing and went green. **In all three the
  mechanism is intact, aimed correctly, and producing nothing** - and in all three the signal
  that would reveal it is the one signal nobody reads, because it is already the colour you
  want.

  > **Assert the OUTPUT, not the exit status.** Ask what the step is supposed to produce, then
  > check that it exists. Where the tool can do it for you, make absence an error rather than a
  > warning (`if-no-files-found: error`) - a warning in a log nobody opens is the same silence
  > with extra steps.

  *Suspect it for anything whose product is a side effect rather than a return value:* an
  upload, a cache write, a report file, a notification, a metrics push. Its success field
  describes whether the code ran, never whether the work happened.

- **Wait for a signal that only the post-condition can produce - never one that is already
  true.** The sixteenth member. §3's browser rules already forbid *hard* waits ("auto-waiting
  assertions only"); this is the failure that survives them. An auto-waiting assertion is only as
  good as the thing it waits ON, and one that is satisfied by the state BEFORE the work returns
  immediately, reporting a pass for a post-condition that never happened.

  **The test is not wrong about what it checks. It is wrong about when it is allowed to look.**

  Recorded 2026-08-08. A test organized a folder twice and asserted that the second run offered no
  typed-word confirm: `expect("#org-result").to_contain_text("duplicate")` then
  `expect("#org-confirm [data-typed-confirm]").to_have_count(0)`. Both were satisfiable before the
  second run finished - `#org-result` still held the FIRST run's text, and `#org-confirm` is
  emptied at the START of the click rather than replaced at its end. **The test passed against the
  live defect**, and nothing revealed it except a mutation that failed to fire.

  > **Assert on something that BECOMES true, not on something that is already true.** An element
  > that survives a previous render, one that is cleared rather than replaced, and an absence of
  > any kind are all satisfied by the starting state. Pick the sentence, count or element that
  > only the finished work can produce, and wait on that.

  *Suspect it for:* `to_have_count(0)` and every `not_to_*`; any assertion on a container the
  handler empties before it works; any second run over a surface the first already wrote. The
  reliable tell is to ask **"was this true one millisecond after the click?"** - if yes, the
  assertion is a coin toss dressed as a wait.

- **A mutation must be asserted PRESENT and UNIQUE, or its scope stated.** The fifteenth member,
  and the one the presence rule above does not reach. Presence answers "did the change land";
  it does not answer "did it land in one place". A mutation that matches several sites is a
  different failure and it fails green: the extra sites can mask the one under test, or the
  blast radius can exceed what the test was scoped to observe, and either way the suite reports
  a pass that means nothing.

  Recorded 2026-08-08 from a real instance. `Catalog.source_hints_for_drive` was mutated by
  removing ` AND f.captured_at IS NOT NULL` from its `WHERE` clause - a clause **shared verbatim
  with `camera_copies_for_events`**, so the anchor matched twice. The presence assertion counted
  occurrences and refused, which is the only reason it was caught; a `str.replace` with no count
  would have mutated both queries, kept them in step with each other, and passed the parity test
  it was meant to break.

  > **Count, do not just find.** `assert t.count(anchor) == 1` before replacing, and include
  > enough surrounding lines - the `SELECT` list, the function's own signature - to make the
  > anchor unique. Where a mutation genuinely must hit several sites, say so and say why, so a
  > reader can tell a deliberate sweep from an accidental one.

  *Suspect it wherever code is deliberately duplicated:* two queries over one population, a
  constant repeated in a migration and its schema, a guard applied at several call sites. Those
  are exactly the places a single-site mutation is most valuable and least likely to be unique.

  **It paid again the day after it was written.** A patch to `tests/e2e/test_ui_regressions.py`
  asserted two `typed.fill("move")` sites; there were three. The count refused and the patch did
  not half-apply, leaving one site on the old vocabulary and a suite that would have failed for a
  reason unrelated to the change. Two saves in two days, both from counting rather than finding.

  **The same rule governs ORDINARY EDITS, not only mutations, and a formatter can stale a proof.**
  Recorded 2026-08-09 after this bit twice more in one session, both caught by the author and
  neither by a test:

  * A `str.replace` that matches nothing **succeeds**. Two edits to `decisions.py` silently did not
    apply because `ruff format` had reshaped the blocks between writing the patch and running it;
    the file was left referencing a name that no longer existed. **An edit applied by string
    replacement must assert its match count exactly as a mutation does** - `assert
    t.count(anchor) == 1` before replacing, and a check that the new text is present afterwards.
  * **A mutation proof taken BEFORE a formatter ran is stale.** Reformatting moves the anchors a
    mutation targets and can reshape the very assertion it was proved against, so the proof no
    longer describes the code that will be committed. **Re-prove after the last formatter run, not
    before** - and re-prove after editing a test the mutation targets, for the same reason.

  > The family resemblance across all of these: **a change you believe you made and did not.** The
  > suite is green either way, and green is exactly what it looks like.

  **THE COST IS THE METHOD, NOT WASTE - recorded so nobody later trims it as overhead.** A
  mutation is one full suite run: about **20 seconds** here, so eight mutations is roughly three
  minutes of wall clock. That is the whole price, and it has been paid back three times in two
  days. On 2026-08-09 the **fifth** mutation against the decisions writer failed to fire and
  earned a test for a hand-edited document naming one day under two trips - a case that would
  otherwise have killed a restore part way through, with some decisions applied and no report.
  **Stopping at four would have shipped it.** The same day, a mutation that killed nothing proved
  a defensive branch was unreachable, and it was deleted rather than left to look load-bearing.

  *Two distinct outcomes, both valuable, and neither available from a green suite:* a mutation
  that does not fire means **either** the guard is missing **or** the code is dead. Find out
  which before writing the test - the answer is a test in one case and a deletion in the other.

- **A fixture modelled on the current library inherits its blind spots.** The seventeenth member.
  Not "use more rows" - that says nothing about where to look. **Ask which property of your data
  is currently accidental, and put the second one in the fixture.**

  Recorded 2026-08-09 from `(ack)`. A restore gave the first trip every other trip's days. The
  decisions fixture seeded **one** trip, so the day-to-trip mapping was never exercised - and the
  reason it seeded one is that **the real catalog holds exactly one trip**. The fixture was
  faithful to the library, and being faithful to a one-trip library is what hid a defect that only
  appears at two.

  **The suite was not naively single-instance**, which is why "more rows" would have missed it:
  `test_catalog_trips.py` creates five trips and `test_trip_review.py` two. Only the round-trip
  that had to carry identity *off the machine* used one.

  > **A count of one is not a fixture, it is a coincidence.** One trip, one drive, one event, one
  > album, one copy - each hides every defect that needs two things to tell apart. Where the code
  > maps, joins, merges or de-duplicates, the fixture needs two of the mapped thing, and they must
  > be **distinguishable**: two trips on the same days would have passed this too.

  *The tell:* a fixture that mirrors the maintainer's own library. It is the most tempting kind -
  realistic, easy to justify - and it can only find bugs the maintainer has already hit.
  Corollary, from the same day: the real catalog held zero events and zero date confirmations, so
  the feature had only ever met seeded examples of the thing it exists to protect.

- **A test written in terms of the constant it guards cannot falsify the constant.** The
  twenty-ninth member, and it is **not** a member of the vacuous-assertion family. Those tests
  assert something that never ran - an unmatched stub, a subject that never entered the path, a
  guard whose defect has been fixed. This one runs, and what it asserts is **true and useless**:
  it restates the constant against itself. A tautology passes at every value, including a wrong
  one.

  > **The tell: would the test still pass after you changed the constant?** If yes, it is testing
  > the plumbing rather than the value - that the comparison happens, not that the number is
  > right.

  *Worked instance, 2026-08-10.* `FUTURE_TOLERANCE` decides how far ahead of now a capture date
  may sit. Two tests pinned its boundary, written as `FUTURE_TOLERANCE - 1 minute` (accepted) and
  `FUTURE_TOLERANCE + 1 minute` (refused). Both are correct, both are useful for catching an
  off-by-one in the comparison, and **both pass at one day, at two days, and at five minutes.**
  The constant was `timedelta(days=1)` while the real gap between where a photo is taken and
  where it is imported is **26 hours** - so a fresh photo from UTC+14 imported on UTC-12 went to
  `Undated/`, and the suite was green throughout. The tests pinned *where* the boundary was and
  never *whether it belonged there*.

  **The repair is to assert what the world imposes, in the world's units.** The added test says
  26 hours in absolute terms, so trimming the tolerance back fails there rather than silently
  re-passing. Keep the relative tests too - they catch a different bug - but do not mistake them
  for cover.

  **And the cry-wolf half, because loosening a bound is the easy direction.** Widening a tolerance
  can quietly retire the case it was written for, so pin that case absolutely as well: the 2051
  library that motivated the future check is now asserted refused by year, not by offset from the
  constant. One test says "must still accept 26 hours"; the other says "must still refuse 2051".
  Neither can be satisfied by moving the number.

  *Same shape, worth naming so it is recognised elsewhere:* a test asserting a limit equals its
  own constant; a threshold test that reads the threshold; a timeout test parameterised by the
  timeout; a retry test that loops the configured retry count. Each proves the mechanism consults
  its setting, and none proves the setting is right.

- **A guard proven by the problem it hunts dies at the moment it succeeds.** The twenty-eighth
  member. The family is any assertion whose validity depends on the defect still existing:
  a cry-wolf test that demonstrates a matcher works by pointing at real findings, a fixture built
  from the bad data, a check pinned to a count that is supposed to fall. Each is honest the day
  it is written and vacuous the day the work lands - and it goes quiet precisely when the guard
  becomes load-bearing, because there is nothing left for it to find.

  Recorded 2026-08-10. The screen-switch ratchet proved its matcher by asserting the allowlist
  was non-empty and equal to what the scan returned. That was sound at 8 violations and expired
  at 0, where **"found nothing" and "looks at nothing" become indistinguishable** - the state the
  whole ratchet exists to hold.

  > **Prove the matcher on input you construct, never on the backlog it is draining.** The
  > rebuilt version runs the rule over source written to violate, including one case that must
  > still be caught (an action behind a *sleep*), so it says the same thing at 8 findings and at
  > 0.

  ✅ **First observed instance, four days after this member was written - and it happened to the
  guard this member was written beside.** The screen-switch ratchet proved its matcher on a
  fixture where `#bk-source` sat below `#drives-list`. Fixing `(acd)` moved that region below every
  control, so the fixture stopped describing anything unsafe and **went green for the wrong
  reason** - the rule was still enforced, but the proof that it could see anything had quietly
  expired. Repointed at Settings, where `#mig-path` really does sit below `#layout-preview`.

  *That a rule predicted its own next violation is the point:* a member that only describes a past
  failure is a story, and one that catches the next one is a control.

  *The tell:* the guard gets weaker every time someone does the right thing.

- **A rule that depends on somebody remembering to read it is not a control.** The twenty-seventh
  member. **Three instances in one week, in three subsystems**, which is why this is a property of
  how rules are written here rather than three unlucky days:

  1. The mutation-restore rule lived in §4, precise and correct, naming the command and the fix -
    and was broken **twice in one day** (`(ace)`).
  2. The no-retry rule lived as a comment at `Makefile:103` and `ci.yml:220`, at both enforcement
    points and nowhere teachable.
  3. `BACKLOG.md`'s *Item letters* section carried the rule, an allocation line recording the next
    free letter, **and a warning that `(u)` and `(v)` had already been taken twice**. Five letters
    were then assigned twice across three days, breaking citations in four documents.

  **This member originally said the fix was to give a rule a findable home, and the third instance
  disproves that.** Instance 3 had the best placement available - the right file, the right
  section, a machine-readable allocation line, and a worked example of the exact failure - and it
  still failed, because consulting it was voluntary. Placement is necessary and it is not
  sufficient. Where a rule lives only changes *who could* have read it.

  > **Ask what happens when nobody reads it.** If the answer is "the rule is broken and nothing
  > says so", the rule is documentation. Make it executable, or accept that it will be broken and
  > say so honestly - the two acceptable answers, and "write it more clearly" is neither.

  *The tell:* the rule is phrased as an instruction to a person - *check here before assigning*,
  *save the original before mutating*, *never re-run a red lane*. Prose can describe a control; it
  cannot be one. The duplicate-letter guard added for instance 3 is the shape that works: it
  cannot be forgotten, because nobody has to remember it.

- **Never retry a failing test to get a green build - and never let "most red lanes are flaky"
  become the reason you stopped looking.** The twenty-sixth member. Two rules, deliberately in
  one entry, because each is what makes the other survivable.

  **No automatic retries, no re-running a red lane hoping for a different answer.** A test that
  fails and then passes on retry turns the build green and takes the defect with it, and the
  industry is unanimous on this. It is already refused at both enforcement points - `Makefile`
  and `ci.yml` both say so at the site - but it was only ever written where it is *enforced*,
  never where it is *taught*, which is how a practice survives on habit. Habits do not survive a
  bad afternoon at the end of a long week. A flaky test is **quarantined and filed**, never
  retried.

  **And the fact that makes that hard: measured externally, ~84% of pass-to-fail transitions are
  flakes rather than real regressions**, with async waiting the single largest root cause at
  about 45%. That number is dangerous knowledge. A team that internalises it learns to shrug at a
  red lane, and the one regression in six walks straight through - the failure mode is not
  disbelieving the suite, it is believing the base rate instead of the evidence in front of you.

  > **The counter is the rule already in force: prove unrelated, never assert it.** A red lane is
  > a claim about your change until something else is *shown* to explain it. "Probably flaky" is
  > a hypothesis, and the base rate is why it is a tempting one, not why it is true.

  Done correctly on `(abq)` this week: the failure looked like a known flake, **and the push under
  test had touched the same file**, so the trace was read before the flake was blamed - zero
  `/api/backup/preview` requests and no `withBusy` label, which proved the handler never ran. That
  is what "prove unrelated" costs, and it is the whole reason the two rules belong in one entry:
  a suite you cannot retry is only bearable if you can find out *why* it went red, and a base rate
  is not a reason.

- **For an intermittent failure, repetition is evidence. For a mechanism that could lie, only a
  differential is.** The twenty-fifth member, and it decides which instrument to reach for.

  A flake fails *sometimes*, so each additional green run lowers the chance you simply missed it -
  counting is the right tool, and `(abq)` is gated on 8. A mechanism that could be wrong fails the
  opposite way: **a signal that lies produces green runs.** Counting greens on a suite that does
  not yet depend on it measures nothing about it, and counting them after it does is worse -
  that is precisely the state the count would be certifying as safe.

  > **Ask what a green run would look like if the thing were broken.** If the answer is "the
  > same", stop counting and build a differential: break the thing the code claims to depend on,
  > and require the test to go RED. A dependency you have not seen fail is a dependency you have
  > not seen.

  Measured 2026-08-10, three times over, which is why this is a finding rather than an argument.
  A load's DOM write deferred by `setTimeout` left **all ten** readiness tests green. Removing the
  wait from `open_screen` left its 37 green. Removing it from the `ui` fixture left **all 407**
  green. In each case the mechanism was absent and repetition reported health. The differential
  said the opposite immediately: with one screen's load broken, the converted test failed and the
  same test in its old form passed - the one result that distinguishes a real dependency from a
  decorative one.

  *Corollary:* a run count still has a use, but name it honestly. Five green runs of new
  timing-sensitive tests is **smoke-aging**, reported and not gating. It is not evidence the
  mechanism is sound, and calling it that is how a count ends up certifying itself.

- **A signal tests wait on must be derived from the writes it claims to cover, never asserted
  beside them.** The twenty-fourth member, and the failure it prevents is worse than the one it
  fixes. A readiness flag that flips early does not produce a flaky suite - it produces a
  **quiet** one, because every test then waits on a lie and passes. The suite looks healthier the
  moment it stops being able to see.

  Recorded 2026-08-10, building `data-ready` for the app's screens. Derivation is the whole of
  it: the flag is assigned textually downstream of the `await` of the same promises that perform
  the DOM writes, in one function, and the markup ships `loading` so `ready` can never be
  satisfied by the starting state. A flag set from a timer, a count, a `readyState` or "the last
  thing I remember starting" is a **proxy**, and a proxy that leads its subject is indistinguishable
  from a correct signal until something silently breaks.

  > **Prove it with the dangerous idiom on purpose.** The test that earns its place waits for the
  > flag and then does a deliberately non-retrying read. If the flag ever leads the DOM, that one
  > named test goes red instead of a flake appearing somewhere else three weeks later.

  *And say where the proof stops.* Measured the same day: wrapping one load's DOM write in
  `setTimeout(…, 0)` left **all ten** browser tests green, including the deliberate one-shot read -
  the deferred write lands before a separate round trip can read it. That case has no reliable
  browser proof and is defended by a static scan instead. A mechanism whose weak spot is written
  down is worth more than one whose weak spot is assumed absent.

- **A branch the common case masks is the one nothing exercises.** The twenty-third member. When
  two paths produce the *same observable outcome*, tests written against the outcome cover only
  whichever path the default takes - and the other can be deleted without a single failure.

  Recorded 2026-08-10. A backup copy that fails re-raises the original error; a backup copy that
  fails **and cannot clean up** raises a longer message naming the surviving partial and its
  size. From outside, both are "the run stopped with an OSError". A mutation deleting the second
  branch entirely killed no test, because every test reached the first.

  > **Ask which branch your fixture takes, then write the test that takes the other one.** The
  > tell is a conditional whose arms differ in *detail* rather than in *kind* - a longer message,
  > an extra field, a second attempt - where the caller's assertion sees neither.

  *Same family:* a third call site untested because the default scheme never reaches it; an
  `else` that only fires on a filesystem CI does not have; a fallback that only runs when an
  optional dependency is missing. Each is live code with no test and a green suite.

- **A report about state must say what it does not cover.** The twenty-second member. `"tree
  clean"` is a claim about **tracked content versus HEAD** and nothing else. It does not say that
  no file was written, that no mtime moved, or that another tool will agree.

  Recorded 2026-08-09. After `git checkout -- .` undid a repo-wide corruption, **219 files were
  rewritten on disk with identical bytes.** `git status` was correctly empty and was reported as
  "tree clean"; the maintainer's editor showed three files modified, because an editor that
  caches git state or reads mtimes sees a mass rewrite. Both reports were true and they appeared
  to contradict each other, which costs more trust than a wrong report does.

  > **When you have just done something that touches every file - a checkout, a formatter over
  > the tree, a bulk rename - say so alongside the status line.** The conclusion is not wrong; it
  > is answering a narrower question than the reader thinks.

  *The same applies to any summarised state:* "no failures" (which tests ran?), "nothing to do"
  (over what scope?), "up to date" (compared against what?).

- **One library is a test bed, never a specification.** The twenty-first member, and it governs
  how every measurement in this repo is reported.

  Truestill is a product for the world. The maintainer's library is the only one anyone here can
  measure, which makes it evidence about *his* files and nothing more. Generalising from it to
  the product needs a separate argument, stated out loud.

  > **When you report a measurement, say which of the two it is.** "3.6% of these files carry
  > GPS" is a fact about a 2013-2014 library. "GPS is a weak signal" is a claim about the
  > product, and it is false: a user arriving today with any modern phone has coordinates on
  > nearly every photo.

  **It cuts both ways**, which is why it is a rule and not a caution. A feature useless to this
  library may be the primary one for everybody else - GPS is exactly that, and it is the *only*
  naming evidence available to someone whose folders are all `DCIM`, which is most people. And a
  feature that works perfectly on these 2,695 files may fail on a real phone dump.

  Recorded 2026-08-09, correcting `(kk)`: a measurement showing one phone in nine geotagging was
  read as a finding about the feature, when it was a finding about that decade's default
  settings.

- **The fair comparison for a storage change is two clean databases, never one database before
  and after.** The twentieth member, and the same shape as the eighteenth one day later in a
  different domain - which is what makes it a rule rather than an anecdote.

  Recorded 2026-08-09, dropping a redundant index. Measured **in place**: drop it, re-measure,
  and `library_status` was **1.7x slower** (0.967 ms -> 1.692 ms). That number was real and the
  conclusion drawn from it was wrong. **It was the freed pages, not the plan.** Prepared as two
  clean copies - each `ANALYZE`d and `VACUUM`ed, one with the index and one without - the same
  query measured **0.844 ms and 0.848 ms**.

  > **A mutation of a database is not a controlled experiment.** Dropping an index, deleting rows
  > or rewriting a table leaves free pages, stale statistics and a changed layout behind, and the
  > next measurement reads all three at once. Build each state from the same source and compare
  > them; do not compare a database to its own past.

  *Suspect it whenever a measurement follows a `DROP`, a `DELETE`, an `ALTER` or a bulk write.*
  The tell is the same as the eighteenth member's: **the number is real and it is not measuring
  what you think.** There, three CI runs were a slope that the fourth erased; here, one file was
  a comparison that a second file erased.

- **A test that pins "the newest version" breaks on the next version by construction.** Corollary,
  recorded from the same commit. Two tests asserted `CURRENT_SCHEMA_VERSION == 17`, written when
  17 *was* the newest - so the next migration failed two tests about a change it had never
  touched, and the fix looked like editing tests to make a change pass.

  > **Assert what the change did, not where it sits in a sequence.** "The capture columns arrived
  > at v17" and "a v16 file is brought fully current, whatever current is" are the same intent,
  > survive every later migration, and are *stronger*: the first would catch v17 being
  > renumbered, which `== 17` never could.

  *Same family:* a test pinning "the last item", "the newest run", "the current release" or the
  length of a list that grows.

- **A guard that is silently cancelled is worse than one never scheduled, because the calendar
  says it ran.** The nineteenth member. It generalises past the workflow it came from: whenever a
  check is moved somewhere cheaper - a nightly, a separate job, a background task, a slower tier -
  the move is only done when you have checked **what can stop it running and how you would find
  out.** A guard nobody scheduled is an obvious gap. A guard that starts and is killed leaves
  green ticks and a schedule entry, and reads as coverage.

  Recorded 2026-08-09. The collection-order pass was moved to a nightly because parallelism had
  made it the largest step in the job. The workflow's `concurrency` group was
  `ci-${{ github.ref }}` with `cancel-in-progress: true`, so a scheduled run and a push to `main`
  share one group - **the first morning push would have cancelled the nightly mid-flight**, and
  the nightly was by then the only trigger that ran that pass. Caught before it shipped, by
  asking what could stop it rather than by assuming a cron fires.

  > *Ask three things before moving a check off the main path:* what cancels or skips it, who
  > sees the result, and what the symptom would be if it silently stopped. If the answer to the
  > third is "everything looks the same", the move needs a signal before it needs a schedule.

  *Same family, different mechanism:* a `skipif` whose condition is always true, an allow-list
  entry nobody prunes, a matrix leg that quietly stopped being included. Each reports success for
  work it did not do.

- **Three points is not a trend, and a live metric is not a constant.** The eighteenth member.
  Two ways to be confidently wrong about a measurement, both recorded 2026-08-09 from the same
  afternoon.

  **The trend.** A Windows CI step measured 566 s, 1009 s, 1472 s on three commits, and was
  reported here as a regression. The fourth run was **596 s** - on the commit carrying *every*
  change of that session and **more tests than the 1009 s run**. The series is noise with a 2.6x
  spread, and the retraction was written the same day.

  > **The tell was available before the fourth point and was not used: the newest run should have
  > been the slowest and was not.** A trend that needs the newest measurement to be exceptional
  > is not a trend. Before reporting one, ask what the next point would have to be to disprove it
  > - and if the answer is "anything", say variance instead.

  *What to do instead:* report the ratio that holds within a single run, where the machine is
  constant. Windows at **2.1x ubuntu on one commit** was the real finding, and it survived.

  **The live metric.** `test_space_is_checked_against_the_destination_drive` compared a recorded
  `free_bytes` against a **second** `shutil.disk_usage` reading of the same disk. Two samples of
  a moving quantity, and it was green only because nothing else was writing - the first parallel
  run failed it, intermittently, because other workers were. It now asserts **which path was
  measured**, which is the claim its name makes and cannot race.

  > **A test may compare a live metric against a recorded one only if it controls both.** Disk
  > free space, wall-clock time, memory, and file mtimes are readings, not values. Assert the
  > input that produced them, or pin the reading.

- **Errors.** Exceptions typed and specific - no bare `except`. User-facing CLI errors are
  actionable sentences, not tracebacks. Every subprocess call checks its return code and
  surfaces stderr on failure. Partial-failure policy: one bad file never aborts a batch - it
  is logged, counted, and reported at the end.

## 5. When to break a rule

Rules bend when the situation demands - but a violation must be **explicit, commented, and
contained.** Write the comment for the next engineer: state *what* rule you're breaking and
*why*, right at the site. The test is simple - a new engineer reads the comment and
understands, with no archaeology. An uncommented deviation is a bug, not a judgement call.
