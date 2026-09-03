# React + shadcn migration - the plan, and what is already settled

`(adi)`. Recorded 2026-08-14. Target: Tauri v2 shell, React + TypeScript + Vite frontend,
shadcn/ui components, screen by screen. **The Python backend does not move.**

## What does not move, and why that is the whole shape of this

`IMPLEMENTATION_STANDARDS.md` §2 forbids `truestill-app` importing `truestill-cli`, and
`service/` is the F10 facade the browser talks to through `/api/*`. **React replaces a renderer,
not a boundary.** If organize logic appears in a component, the migration has failed regardless of
how the screens look. Nothing in `truestill-core` or `service/` is in scope.

## Settled before starting, by measurement rather than by plan

| | |
|---|---|
| `tokens.css` stays the source of truth | **BUILT 2026-08-15**, no longer only a spike: Tailwind 4.3.3 consumes it via `@theme inline` in `frontend/src/styles/tailwind.css`, and every shadcn contract name (`--primary`, `--background`, …) aliases a token rather than carrying a value. Originally **verified in a 4.3.3 spike**, not read: the utility resolves at use site against our var, Tailwind emits no global of its own, and all three of our dark blocks survive. The widely-repeated "`@theme inline` breaks dark mode" describes writing a literal, not a `var()` reference. |
| Tokens are out of Tailwind's namespaces | `(fa99e58)`. The collision was silent redefinition, not breakage - Tailwind's values sit in `@layer theme`, ours are unlayered, unlayered wins. `--radius-*: initial` was measured and rejected: it removes the utilities, which breaks the shadcn components that ship them. |
| The type scale and text colours are separate | `--type-*` and `--fg-*`. `--text-*` was carrying both, and it is Tailwind's font-size namespace. |
| The browser lane covers the shipped engine | `(9cdd85d)`. WebKit is what the Tauri shell renders in on Linux and macOS. |
| The migration's test cost | **3 of 55 e2e files** touch `app.js` internals: two reach into `organizeCompletion`, one calls `showScreen()`. The other 52 assert on rendered words, so they survive a renderer swap and become the acceptance test for each migrated screen. |

That last row is the reason this is checkable at all, and it is a rule being cashed in rather than
luck: *"§9 asserts on the words a person reads, never on element ids"*.

## ⚠ Known holes, carried here so they are not rediscovered

**`test_the_bundled_family_is_what_rasterises` is blind on WebKit, and WebKit is what ships.**
It is the only assertion that reads which font the engine *actually painted with* rather than which
one CSS asked for - the check that once caught IBM Plex Mono silently rasterising its custody pips
in Times New Roman. It needs CDP, which only Chromium speaks, so on WebKitGTK and WKWebView the
substitution it exists to catch would go unseen. The two provenance defences above it still run
everywhere (the face is fetched from our origin; both weights reach `loaded`). **What is uncovered
is the last step: whether a glyph fell back mid-string.** Nothing in this migration closes it, and
a component library arriving with its own font stack is exactly when it would matter. If a
cross-engine equivalent appears, this is the test to point at it.

**The existing suite keys on ids and `data-*`.** ~62 `data-testid`, plus `#id` selectors and
semantic hooks (`data-refusal`, `data-risk-action`), and every screen gates on `data-ready`.
**Treat that selector set as a written contract**: each React screen renders the same hooks and
sets `data-ready` when its loads settle, so the unchanged suite is a differential oracle - green
against the Jinja screen, and required green against the React one before the old is deleted.
Radix portals move dialogs and popovers to `document.body`, so any descendant chain crossing a
portal boundary breaks; those are the assertions to expect to rewrite.

## Settled by build

**Tauri's static CSP against a sidecar on an ephemeral port: solved by a port wildcard.** Measured
2026-08-14 with a real Tauri 2 release build on WebKitGTK, a listener on port 0, and a fetch from
the webview - the observable is whether the request *arrived*, not what the console said.

| `connect-src` | sidecar reached |
|---|---|
| omits the sidecar (control) | **no** |
| `http://127.0.0.1:*` | **yes** |
| `http://localhost:*` | **no** |

So none of the three workarounds research offered - fixed port, port range, routing through Rust
commands - is needed; a build-time CSP can name a runtime port. **The control is what makes this
mean anything**: without it, "the wildcard works" is indistinguishable from "CSP was never
blocking this in the first place".

⚠ **`localhost` and `127.0.0.1` are distinct CSP host-sources**, and `security.py` accepts both as
`Host` headers. The CSP must name whichever the frontend actually puts in the URL; `session_link`
writes `127.0.0.1`. Listing one and using the other fails silently at the fetch.

## Open

**Playwright cannot drive a Tauri window** (system webview, no CDP outside WebView2). The official
path is WebDriver: `tauri-driver` is Windows and Linux only, but `@wdio/tauri-service` runs an
embedded WebDriver server and **is documented to work on macOS as well** - verified against the
live page 2026-08-14, after an earlier reading of mine generalised the `tauri-driver` limit into a
limit on the approach. Plan: keep the full Playwright suite against the frontend in a real
browser, and add a *thin* WebdriverIO smoke test for shell-only concerns. Do not port 55 files.
`tauri-plugin-playwright` (0.3.0, first published March 2026) stays a spike, not a plan.

## Which tests move with which screen

**A screen's tests move in that screen's commit, not at the end.** Measured 2026-08-14 by
attributing each e2e file to the screen whose elements it drives (per browser; the lane runs two).

| screen | tests | files |
|---|---:|---:|
| Settings | 76 | 12 |
| Stats | 39 | 6 |
| Find | 14 | 1 |
| Backups | 54 | 10 |
| Trips & events | 32 | 7 |
| Import | 22 | 3 |
| **Organize** | **154** | **22** |
| the shell | 96 | 14 |

⚠ **The first attempt at this table put Organize at 24 and it was wrong**, because Organize is the
`class="screen active"` default: its tests never call `open_screen`, so a navigation-based
attribution swept them into "shell" and made the largest migration look like the smallest.
Attribution is now by the element ids a file drives. It is still first-order - a file touching two
screens is split evenly - so treat these as the shape, not a contract.

**The shell's 96 do not move with any screen, and that makes them the early-warning system.**
Rail, wordmark, fonts, type scale, harness, server retirement: they outlive every individual
migration and are the thing that keeps the app coherent while half of it is React. They are also
**the ones most likely to break first**, because an island changes the DOM around them without
touching a line of their own screen.

> **Run the shell's 96 after every island lands, not once at the end.** Nothing else owns them:
> each screen's commit carries that screen's tests, so the shell's would otherwise be checked only
> by the final gate, which is the run that cannot tell you *which* island broke them. This is the
> one part of the suite whose value comes from being run at the wrong-looking time.

Organize carrying a third of the suite is the second reason it goes last, after the risk argument.

## Order

⚠ **RULED 2026-09-03 (P194): ONE CUTOVER, BUILT IN PARALLEL, FLIPPED BY ONE TEMPLATE - NOT ISLAND
BY ISLAND.** The paragraphs below are the plan as recorded on 2026-08-14 and are kept as the record.
What P194 measured, and the mechanism that replaces them:

- **The mechanism below does not exist.** `vite.config.ts` has no `build.manifest` and no `server`
  block, `home()` is four `str.replace` calls, `npm run dev` is `vite build --watch`; there is no
  dev server and no client injection. The tree builds to `static/dist/` and the template loads it.
- **`app.js`, measured**: 3,260 code lines under 4,548 (24% comments); rendering 57%, wiring 18%,
  plumbing 11%, state 9%. 152 of 204 definitions touch no screen id; the genuinely shared set is
  four functions. Coexistence would cost two style paths (`app.css`: 1,716 lines, 262 selectors,
  19 e2e files asserting computed styles), a readiness contract with one writer (`settleScreen`),
  a silent `window.*` seam per island, the shell picker reached from five screens, and the two
  `app.js`-keyed censuses alive until the last screen.
- **The strangler pattern's justification is absent**: live users and unpausable feature work.
  `(ajv)`: the published v0.1.0 carries no bundle, so no React has ever reached a user.
- **The mechanism**: the React app is built beside `app.js` and wired to a second template that
  loads only the bundle; `home()` picks it from `TRUESTILL_UI=react`, read once at startup, default
  unchanged. The browser lane runs against both (`make e2e`, `make e2e-react`); the unchanged suite
  is the differential oracle, green against `app.js` and required green against React before the
  flip. **The flip is one commit** - the template, the switch and the old template - and `app.js`
  stays in the tree for one release; `git revert` of that commit is the rollback. Every id, class
  and `data-ready` write is kept, so restyling is a separate arc.
- **Prerequisites, in order**: `(ajv)`; the browser lane under ~8 minutes (`-n auto`, the lever
  `ci.yml` names) so the flip is verified per push and not nightly; an import-free equivalent for
  the two e2e files that call `fmtBytes` and `fmtDuration` as globals; then `app/` and `api/`
  first, screens in the risk order below, Organize last, the flip, the deletion.
- **The structure**: `app/` (the shell: 18 ids, the picker, the registry), `api/` (`client.ts`
  keyed on the generated `paths`, `stream.ts` yielding the frame union as sent with no `ok`
  adapter, `job.ts` as one state replacing `runJob`'s twenty options), `run/` (the four-state
  result region the island models, the progress block's eight instances), `lib/format.ts`, `ui/`,
  and `screens/<data-screen value>/` with one `index.ts` each, no screen importing another, pinned
  by a Python import guard because there is no linter. Tests stay in `tests/e2e/`.
- ⚠ **The table above says 487 and `--collect-only` says 510**; the table is the 2026-08-14 shape
  and is not re-derived here.

Vite **backend-integration mode** during the transition - `build.manifest`, `server.origin`, and
the Jinja template injecting the dev client - so the Starlette server keeps serving one URL and
`boot_app` keeps returning it. Islands, one React root per screen, mounted into containers the
existing shell owns; `root.unmount()` on teardown, never `innerHTML = ''`.

Screens in ascending order of risk, each landing green before the next: **Settings** (a shelf, no
job), then **Stats** (read-only), then **Find**, then **Backups**, then **Trips & events**, then
**Import**, and **Organize last** - it owns the job stream, the typed confirm, the undo, and the
result grid.

⚠ **THIS ORDER IS BLOCKED ON `(ahn)` STAGE 5, AND UNTIL 2026-09-02 THIS PLAN DID NOT SAY SO.**
`PROJECT_STATUS.md` §1b orders engine, then contract, then UI, and the contract is `(ahn)`: an
OpenAPI spec emitted from the TypedDicts, `openapi-typescript` generating the types, the frontend
importing them. This plan named no payload contract at all - its only contract was the selector
set above - and its first screen, Settings, reads a payload on load (`loadLayout`). A screen
written before stage 5 hand-types that shape, which is the drift `main.tsx`'s
`Record<string, unknown>` already commits. **What can start now**: stage 5's own prerequisites
(the type-to-schema mapping, `NotRequired`, the emission script, the contract test - and only once
the maintainer has ruled on the emission shape and the dependency) and the shell rail, which reads
no payload. **What cannot**: any screen that reads a payload, which is every one of the seven.
