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
| `tokens.css` stays the source of truth | Tailwind consumes it via `@theme inline`; **verified in a 4.3.3 spike**, not read: the utility resolves at use site against our var, Tailwind emits no global of its own, and all three of our dark blocks survive. The widely-repeated "`@theme inline` breaks dark mode" describes writing a literal, not a `var()` reference. |
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

## Open, and to be settled by a build rather than a decision

**Tauri's CSP against a sidecar on an ephemeral port.** Tauri injects a static CSP; the server
picks its port at runtime. No authoritative guidance was found for that combination. The usual
answers are a fixed port, a port range, or routing through Rust commands - all three have costs,
and the spike that settles it should run before the first Tauri build, not after.

**Playwright cannot drive a Tauri window** (system webview, no CDP outside WebView2). The official
path is WebDriver: `tauri-driver` is Windows and Linux only, but `@wdio/tauri-service` runs an
embedded WebDriver server and **is documented to work on macOS as well** - verified against the
live page 2026-08-14, after an earlier reading of mine generalised the `tauri-driver` limit into a
limit on the approach. Plan: keep the full Playwright suite against the frontend in a real
browser, and add a *thin* WebdriverIO smoke test for shell-only concerns. Do not port 55 files.
`tauri-plugin-playwright` (0.3.0, first published March 2026) stays a spike, not a plan.

## Order

Vite **backend-integration mode** during the transition - `build.manifest`, `server.origin`, and
the Jinja template injecting the dev client - so the Starlette server keeps serving one URL and
`boot_app` keeps returning it. Islands, one React root per screen, mounted into containers the
existing shell owns; `root.unmount()` on teardown, never `innerHTML = ''`.

Screens in ascending order of risk, each landing green before the next: **Settings** (a shelf, no
job), then **Stats** (read-only), then **Find**, then **Backups**, then **Trips & events**, then
**Import**, and **Organize last** - it owns the job stream, the typed confirm, the undo, and the
result grid.
