# The languages the canon does not cover - what survived review

Recorded 2026-08-14. **A research record, not the canon.** `ENGINEERING_STANDARD.md` and
`IMPLEMENTATION_STANDARDS.md` are the standard; this sits beside `BACKLOG.md` because most of what
follows is *findings about tools we have not adopted*, not rules in force.

A draft standard for TypeScript, React, Tailwind and Rust was written **without repository
access** and reviewed against the repo on 2026-08-14. Roughly half its factual claims were wrong,
and the wrong half is preserved below under **Recorded findings** rather than deleted - a
correction is worth more in the record than a clean document. What was right and is enforceable
is in **Rules**. What was already canon has been cut and cross-referenced.

**Prose convention: hyphens, not em-dashes** - `IMPLEMENTATION_STANDARDS.md` §6.2.

---

## Rules

### 1. TypeScript

**1.1 The gate runs the compiler. This is the finding the review was worth.**

`make frontend` called `npx vite build` directly for the whole life of the React seam, skipping
the `tsc --noEmit &&` in the frontend's own `package.json` build script. **Vite strips types; it
does not check them.** So `strict`, `noUncheckedIndexedAccess` and every other flag in
`tsconfig.json` were configured and read by nothing.

When the check was finally run it was **not clean**: three `TS2591` errors in `vite.config.ts`,
present since the seam landed and invisible to `make check`, `make gate` and CI alike. Cause:
`"types": []` excluded all ambient type packages while the config imports `node:crypto`,
`node:fs` and `node:path`. Fixed with `@types/node` (dev-only, type-only, zero runtime) and
`"types": ["node"]`.

Guarded by `test_the_frontend_is_typechecked.py`, both halves: the gate must invoke
`tsc --noEmit` **before** `vite build`, and the agreed flags must still be set. A gate that runs
`tsc` against a permissive config checks nothing, and dropping one line from a JSON file is a
quieter regression than deleting the step.

Flags in force: `strict`, `noUncheckedIndexedAccess`, `noUnusedLocals`, `noUnusedParameters`,
`noFallthroughCasesInSwitch`, `isolatedModules`. `exactOptionalPropertyTypes` and
`verbatimModuleSyntax` were proposed and are **not** adopted - neither has a call site yet, and a
flag turned on before the code that needs it is a flag that gets turned off by the first person
it inconveniences.

**1.2 Sidecar JSON is `unknown` until narrowed.**

Every value crossing the HTTP boundary from the Python sidecar arrives over a socket from another
process, possibly a different version after an upgrade. An interface declaration is an assertion
about that response, not a check of it. `unknown`, narrowed by a hand-written type guard per
shape; no runtime schema library unless one earns its place in writing, per
`IMPLEMENTATION_STANDARDS.md` §7.

**Nothing violates this today because there is no fetch layer** - see §3.

`any` is banned in frontend source, guarded by `test_the_frontend_source_rules.py`.

### 2. React

**2.1 Most current React advice does not apply here.** Search results for React practice are
overwhelmingly Next.js App Router advice: Server Components, Server Actions, `use()` for async
data, streaming, partial pre-rendering. **All of it is inapplicable.** Truestill serves a Vite
bundle from Starlette to a WebView. There is no Node server, no RSC boundary, no server actions.
When guidance mentions Next.js, `app/`, `"use server"` or `"use client"`, it is describing a
different architecture. An agent that applies it will introduce a framework we deliberately do
not have.

**2.2 The kill list.** Not written here: hand-memoization for performance, `useEffect` for
fetching, `useState` for form submission state, Redux, class components, PropTypes, and CSS-in-JS.

Hand-memoization is guarded. See the finding in §7 for why the guard's *reason* is not the one
the draft gave.

**2.3 `useEffect` is for synchronising with something outside React** - a subscription, an
imperative DOM API, the job event stream. Not data fetching, not derived state (a calculation
during render), not responding to an event (that belongs in the handler). **Judgement, not
guardable** - marked as a suggestion per this file's own rule.

**2.4 Server state, URL state and local state are three things.** Do not collapse them into one
store, and do not duplicate server state into `useState` where it can go stale. **Judgement, not
guardable.**

Whether a global store is justified at all: the only state that outlives a screen today is the
text size, and `app.js` implements it as *"a `data-text-size` attribute on the root, and nothing
else"*. Two contexts would cover it. A store needs a reason first.

### 3. Complexity, in the languages that now exist

Extends `IMPLEMENTATION_STANDARDS.md` §8, which is the performance law and is Python-shaped. Not
restated here.

**TypeScript.** The dominant accidental quadratic in a React codebase is a lookup inside a map:
`items.map(i => others.find(o => o.id === i.id))` is O(n·m) and reads as one line. Build a `Map`
once. Any nested iteration over a photo list carries a comment proving its bound, exactly as §8
already requires of Python.

**Rendering.** State the expected item count in a list component's own comment, and if it is
unbounded, say what bounds the render. ⚠ The draft claimed a 33,457-item list was imminent; that
figure is the **hashing corpus** (`PERFORMANCE.md` §5), not a rendered list. The Organize results
grid collapses behind "show all N", and the unbounded browse view is `(abk)`, unbuilt. The rule
stands; the urgency was overstated.

**Rust.** Not applicable at the current size. If a complexity question arises in the Rust, that
is evidence the scope rule in §7 has been broken.

### 4. Toolchain currency, reviewed August 2026

The recommendation is **change nothing**, and the reasons matter more than the conclusion.

**Already current:** `uv` for environments, locking and running with `uv.lock` as the source of
truth; `ruff` for lint and format; src layout under `packages/` with a `pyproject.toml` per
package. Python 3.13 is the floor and correct - `requires-python = ">=3.13"` in all three
packages.

**Type checker: stay on mypy strict.** The market moved more in eighteen months than in the
previous decade - Pyrefly 1.0 (May 2026, Rust), Astral's `ty`, mypy 2.0 with experimental
parallel checking. Both Rust checkers are an order of magnitude faster. Reasons to stay:

- **Type checking is not the bottleneck.** The Windows lane is 1638 s of *summed* test time
  against ubuntu's 121 s (`PERFORMANCE.md` §5.1); wall clock under `-n auto` is 831 s. mypy is
  not visible in either.
- **The conformance numbers are disputed by a factor of three.** Sources published within weeks
  of each other give Pyrefly 58% and 87.8%, and `ty` 15% and 53.2%. A benchmark that unsettled
  cannot decide a gate.
- **`ty` is beta with no plugin support.**
- **Never change a gate while a lane is red.**

Revisit when `ty` reaches stable 1.0, or mypy becomes visible in a lane's wall clock. A second
checker in advisory mode is cheap and produces evidence rather than argument.

**Governance note, not technical:** uv, ruff and ty all come from Astral, and Astral joined
OpenAI in March 2026. Three of four toolchain tools under one owner is a concentration worth
knowing. Not a reason to act - all are permissively licensed and forkable - but a reason not to
add the fourth without thought.

**Free-threaded Python:** worth watching in 3.14, not adopting. This workload is I/O-bound on
network filesystems by 3.6x-36x (`PERFORMANCE.md` §5), so removing the GIL buys nothing here.

### 5. Tauri, settled by build

Three findings from `(adh)`'s Stage 1, recorded so they are not re-derived. Evidence:
[`tauri-sidecar-lifecycle-research.md`](tauri-sidecar-lifecycle-research.md) and
[`react-migration-plan.md`](react-migration-plan.md).

- **`resources` + `resource_dir()`, never `externalBin`.** The two mechanisms land in different
  trees (`/usr/bin` versus `/usr/lib`), so a one-folder PyInstaller build is **broken on Linux**,
  not merely fragile off it. Spawn the sidecar as an ordinary child.
- **CSP can name a runtime port.** `connect-src http://127.0.0.1:*` works on WebKitGTK, verified
  against a control that proves CSP was blocking in the first place. ⚠ `localhost` and
  `127.0.0.1` are distinct CSP host-sources and `session_link` writes `127.0.0.1`; listing one
  and using the other fails silently at the fetch.
- **The WebView has no Node.** No `child_process`, no `fs`, no Node built-ins. The failure looks
  like a module resolution error and reads as a bundler problem, which it is not.

---

## The frontend on disk

The draft proposed a layout. This is what exists, as of `ed0caad`:

```
packages/truestill-app/frontend/
  .npmrc  .nvmrc  package.json  package-lock.json
  tsconfig.json  vite.config.ts
  src/main.tsx          <- the entire React source; mounts nothing
```

`main.tsx` publishes `__BUNDLE_SOURCE_HASH__` onto `document.documentElement.dataset.bundle` and
does nothing else. **No `screens/`, no `components/`, no `lib/`, no fetch layer, no store, no
router, no lint config.** React 19.2.8, Vite 8.2.1, TypeScript 7.0.2, Node pinned by `.nvmrc` to
24.16.0 with `engine-strict=true`.

**When screens arrive: one directory per screen, matching the seven nav items**, so a person
reading the nav rail can find the code without a map. `lib/` waits until the first island needs a
fetch - a directory invented before its first file is a directory that gets filled to justify
itself.

⚠ **`tokens.css` does not move into the frontend tree.** It lives at
`truestill_app/static/tokens.css`, where Starlette serves it and **20 e2e files assert computed
styles against it**. The draft's proposed `styles/` directory would have created a second copy
that drifts the first time either is edited - silently, because nothing in the Python gate reads
CSS (`ENGINEERING_STANDARD.md` §4). Guarded by
`test_the_frontend_source_rules.py::test_tokens_css_is_not_imported_into_the_bundle`.

---

## Recorded findings - things believed that were not true

Kept because the corrections are the useful part.

**The React Compiler is not installed, and does not ship with React 19.** The draft's central
React rule was "do not hand-memoize, because the compiler does it at build time". The compiler is
a **separate opt-in Babel plugin**; `package.json` has five devDependencies and none is
`babel-plugin-react-compiler`. `vite.config.ts` is `plugins: [react()]` and nothing else.
Installing React 19 brings none of it. The no-memoization rule survives on the canon's own
grounds - optimise the proven bottleneck - and the guard says so in its docstring, so the wrong
reason cannot be inherited.

The draft also named `react-hooks/exhaustive-deps` as "the guard" for compiler eligibility.
**There is no ESLint here at all** - no config file, no plugin, no dependency.

> ⚠ **SUPERSEDED 2026-08-15: TAILWIND IS NOW INSTALLED, SO §3'S THREE FINDINGS ARE RULES IN
> FORCE.** This section's last line said they *"become rules the day Tailwind is installed, and not
> before"*. That day was 2026-08-15 - `tailwindcss@4.3.3` and `@tailwindcss/vite` are in
> `frontend/package.json`, wired through `@theme inline` against `tokens.css`. All three findings
> held on contact with the real install: token names stay out of Tailwind's namespaces (a
> `--leading-*` attempt was refused by `test_no_token_sits_in_a_tailwind_namespace` within seconds),
> no namespace is reset, and `tokens.css` remains the single source with every Tailwind value a
> `var()` pointing at it. **The paragraph below is left exactly as written** - it was correct when
> written, and a record edited to stay correct stops being a record.

~~**Tailwind is not a dependency.** §3 of the draft was written as rules in force. Tailwind appears
nowhere in `package.json`.~~ The three findings it recorded are correct **as records of a 4.3.3
spike** (`react-migration-plan.md`), not as rules: `tokens.css` stays the source of truth
consumed via `@theme inline` with `var()` references; never reset a Tailwind namespace, because
`--radius-*: initial` removes the *utilities* and shadcn ships those class names; a colliding
token name silently redefines a utility, since Tailwind's values sit in `@layer theme` and ours
are unlayered. They become rules the day Tailwind is installed, and not before.

**There is no Rust.** No `Cargo.toml`, no `tauri.conf.json`, no `capabilities/`. `BACKLOG.md`
`(adh)` states it: the Stage 1 spike lived in `/tmp`, which has been cleared, and nothing was
committed. So the draft's `cargo clippy` gate rule and its "every capability carries a comment"
rule govern files that do not exist. **The proposed `#[tauri::command]` counter was refused**: a
guard over zero files reports green forever and would be cited as coverage - the
empty-set-reads-as-success trap this repo keeps finding. Write it in the commit that brings the
crate in.

The scope rule itself is kept, as a rule for when the crate arrives: **Rust owns the window,
Python owns the photos, React owns the pixels.** Every `#[tauri::command]` is a second
implementation of something Python already does, reachable by a second protocol, needing its own
tests. If a feature can be an HTTP call to the sidecar, it is an HTTP call to the sidecar.

**`noUncheckedIndexedAccess` was already on.** The draft called it the highest-value flag beyond
`strict` and proposed adopting it; `tsconfig.json` has had it since the seam landed. What was
missing was anything that read the file.

---

## Cut as duplicate

- The Python code standard in full - `ENGINEERING_STANDARD.md` §4.
- "Nothing in the gate reads CSS, so a stylesheet is unguarded" - `ENGINEERING_STANDARD.md` §4
  already says it; cross-referenced above rather than restated.
- The performance law - `IMPLEMENTATION_STANDARDS.md` §8. Only the TypeScript and rendering
  extensions are here.
- "Measure before optimising" - `ENGINEERING_STANDARD.md` §4. The frontend rule cites it.

---

## Maintenance

Docs change in the same commit as the code. **A rule that has never been enforced by a guard is a
suggestion and says so here** - §2.3 and §2.4 are marked as such. When a rule is overturned by
measurement, the measurement is recorded beside it rather than the rule being quietly edited.
