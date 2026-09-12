# truestill - the frontend contract

**Written 2026-09-12, for a tool or a person with no access to the conversation that produced
this code.** It is the set of constraints a change to the seven screens has to satisfy, with the
evidence for each and the command that checks it. It is not a style guide and it is not a wish
list: everything here has already cost something once.

**Read `docs/design-system.md` for what the screens should look like** and
`docs/IMPLEMENTATION_STANDARDS.md` for the binding repo-wide rules. This document is the part a
frontend change can break without anything going red.

**Every number below is a reading with the command beside it.** Run the command. A number in a
document is a claim about the day it was written; this repo has been bitten by that class four
times, and the entries are `(akm)`, `(aka)`, `(ago)` and `(afx)`.

---

## 1. The single most expensive thing you can do: rename an id

`static/app.js` opens with `"use strict"` and is loaded as a **classic script**
(`templates/index.html`, `<script src="/static/app.js"></script>` - no `type="module"`). Its
first helper is:

```js
const $ = (id) => document.getElementById(id);
```

**There is no guard in it.** `getElementById` returns `null` for an id that is not in the
document, and the file then does this, twenty-five times, at **top level**:

```js
$("org-preview").onclick = guarded(async () => { ... });
```

Setting a property on `null` throws `TypeError`. An uncaught throw at the top level of a classic
script **stops the rest of that script from executing**. The twenty-five bindings run from about
a third of the way into the file to near its end, so a single renamed id silently disables every
binding after it - and the page still renders, because the markup is server-side Jinja. **The
screen looks finished and nothing on it works below the break.**

```sh
grep -cE '^\$\(' packages/truestill-app/src/truestill_app/static/app.js   # 25 on 2026-09-12
```

### The binding list is a command, never a list

A hand-written inventory of hooks is the same stale-literal class this repo keeps paying for, so
this document does not carry one. **These four commands are the inventory**, and they are the
only form of it that cannot go stale:

```sh
cd packages/truestill-app/src/truestill_app

# Every id app.js asks the document for - 111 distinct on 2026-09-12.
grep -oE '\$\("[^"]+"\)' static/app.js | sed -E 's/\$\("(.*)"\)/\1/' | sort -u

# Every id the served markup declares - 142 distinct.
grep -oE 'id="[^"]+"' templates/index.html | sort -u

# Every non-id hook app.js selects on. Rename one of these and the same silence follows.
grep -oE '\.querySelectorAll?\(`?"[^"`]+"' static/app.js | sed -E 's/.*\("?//' | sort -u

# Every test id the browser suite drives - 42 distinct.
grep -rhoE "data-testid='[^']+'" tests/e2e | sed -E "s/data-testid='(.*)'/\1/" | sort -u
```

### Where the 111 ids actually come from, because three answers are wrong

Classified by script on 2026-09-12:

| source | count | what it means for you |
|---|---|---|
| declared in `templates/index.html` | 101 | rename it there and in `app.js` together |
| stamped at runtime by `app.js:mountRunBlocks` | 2 | **not searchable in the template** |
| written only by `innerHTML` inside `app.js` | 8 | not in any file as an `id=` attribute you can grep for in markup |

The eight that exist only inside a template literal are `account-error`, `account-file`,
`custody-catalog`, `org-undo-preview`, `org-undo-stage`, `rc-unpack`, `where-next`, `where-prev`.
**A tool that rewrites markup and leaves `app.js` alone will not see them at all.**

`mountRunBlocks` is the second trap. It runs before every binding, clones `<template id="tpl-run">`
into each `[data-run]` mount, and rewrites each `data-id="x"` into `id="<prefix>-x"`:

```sh
grep -oE 'data-run="[^"]+"' templates/index.html | sort -u | wc -l   # 9 mounts
sed -n '/id="tpl-run"/,/<\/template>/p' templates/index.html \
  | grep -oE 'data-id="[^"]+"' | sort -u | wc -l                     # 8 slots
```

Nine mounts times eight slots is **72 ids that exist only after `app.js` has run**. Deleting one
`data-run` mount deletes eight ids; renaming `data-id` renames nine. The function deliberately
has no `if (!template) return`, and says why in its own comment: a missing template would
otherwise surface as thirty unrelated null-dereferences instead of one.

### The three `name=` attributes that are hooks, not markup

`app.js` selects `input[name="org-mode"]`, `input[name="text-size"]` and `input[name="theme"]`.
`org-mode` is read three times, including `input[name="org-mode"]:checked` for the value the
Organize run is submitted with. **The radio inputs must stay in the DOM and stay visible** -
`app.css` records the four separate ways hiding them broke the screen. A design that replaces a
radio with a styled div has to keep the input, its name, its value, its `checked` state and its
focus behaviour.

### So: what is allowed

- **Add** ids, classes, `data-*` and `data-testid` freely.
- **Restyle** anything. Change any class used only by CSS.
- **Do not rename or remove** an id, a `data-*` hook, or one of those three `name=` values
  without changing `app.js` in the same commit.
- If you must rename, run the first and second commands above **before and after** and diff the
  two id sets. Nothing else will tell you.

**Nothing in `make check` catches this.** There is no test that resolves `app.js`'s ids against
the markup - checked 2026-09-12, and the absence is stated here rather than left to be discovered.
The only thing that catches a renamed id is the browser lane, and only on the screens it drives.

---

## 2. React and vanilla, and exactly where the seam is

**There are seven screens** and **six and a half of them are vanilla.**

```sh
grep -oE 'id="screen-[^"]+"' packages/truestill-app/src/truestill_app/templates/index.html | sort -u
```

gives `screen-backups`, `screen-events`, `screen-find`, `screen-import`, `screen-organize`,
`screen-settings`, `screen-stats`. All seven are server-rendered Jinja in one page; switching
screens is a class toggle, not a navigation.

**React owns four nodes, all on Organize**, mounted by `frontend/src/main.tsx:mountAt`:
`org-result`, `org-stepper`, `org-source-counts`, `org-summary`. Plus the "Look inside" card in
`frontend/src/inventory.tsx`. That is the whole of React in this product today.

`mountAt` is `document.getElementById(id)` and **returns quietly when the node is absent**, which
is the opposite failure mode from `$`: delete `#org-result` and React renders nothing, throws
nothing, and the Organize screen simply has no result region.

### The seam runs in both directions and both halves are load-bearing

**Vanilla to React** - `main.tsx` publishes one object on `window`:

```js
window.organizeResult = { set: store.setResult, setForm: store.setForm };
```

`set` is the only way the result region is written. It is on `window` rather than imported
because **`app.js` is a classic script and cannot import a module**.

**React to vanilla** - `main.tsx` publishes `window.truestillMarkup`, which renders React
components **to HTML strings** for the `app.js` builders that still compose markup: the
completion card's chips and legend, Import's match lists and date notes, and Backups' by-format
drive list. It is published **before** the islands mount, so no click can find it absent.
`inventory.tsx:toHtml` is the renderer, and it throws a named error rather than returning an
empty string if it is called during a React render, because `flushSync` does not flush inside one
and the block would vanish with nothing failing.

**Each `truestillMarkup` entry disappears when its last string consumer becomes a component.**
That is the migration, one entry at a time.

### THE FORM GOES LAST, and the reason is parse time

`docs/react-migration-plan.md` rules it: Organize is migrated **island by island**, and the
**form is the last thing converted**. `app.js` binds `#org-preview`, `#org-dedup`, the
`org-mode` radios and the library-root save **at parse time** (section 1), so React drawing the
form breaks `app.js` before it wires anything at all. **The work starts where `app.js` only
writes** - the result region, the stepper, the counts, the summary - and ends where it reads.

The cutover of any slice is **two commits, never one**:

1. a pure renderer swap: same DOM, same ids, same `data-*` hooks, the unchanged e2e suite green;
2. the appearance.

Not one commit, because **23 of the 74 e2e files assert computed styles** - moving the renderer
and the look together makes every style failure ambiguous.

```sh
grep -rl getComputedStyle tests/e2e | wc -l   # 23 on 2026-09-12
```

---

## 3. `backdrop-filter` is refused. This is not negotiable and it is not a taste

**`docs/DECISIONS.md` D15**, decided 2026-09-06. WebKit answers **`true`** to
`@supports (backdrop-filter: blur(1px))` **and paints nothing** - measured, entry `(ake)`, and
corroborated independently by block/buzz PR #3533 and Tauri #2976 and #2827. So the feature query
is a guard that cannot fire, and a design that leans on the property renders as flat translucency
on an engine this product must support.

**The binding form of the rule is additive**: a surface must be **complete, legible and correct
with `backdrop-filter` doing nothing**. The property may remain as a progressive enhancement on
chrome that already stands without it. The tree contains exactly one declaration today, on
`.modal-backdrop`, and it complies:

```sh
grep -cE '^\s*(-webkit-)?backdrop-filter:' \
  packages/truestill-app/src/truestill_app/static/app.css   # 2 = the `-webkit-` prefixed and standard halves of one declaration
```

Two further parts of D15 bind a design change directly:

- **Glass is for chrome only.** Rail, top bar, floating panels - over the gradient this product
  owns, because translucency is only computable when you own what is behind it. It is **refused
  on anything a person reads to make a decision**: the grid card, the tally, the amber notices.
  `design-system.md` §6 reaches the same rule from the other direction - **never behind a form
  field, because a path is checked character by character.**
- **No glassmorphism library, generator or component may be adopted.** Checked 2026-09-06:
  shadcn.io's glass navbar, superdesign.dev's generator and every library examined emit
  `backdrop-filter`. That is not a detail to patch after installing; it is the implementation.

The technique that is used instead is the pre-2022 one and is already encoded in `--glass-bg`,
`--glass-border` and `--glass-shadow`: layered translucency as a real colour, a hairline gradient
border via `background-clip`, an inner highlight, a soft shadow, and - where a real blur is
wanted - **a blurred copy of the gradient placed behind the panel**, which is `filter: blur()` on
an element and therefore paints everywhere.

---

## 4. No new dependency. Icons are inlined, with per-icon provenance

`frontend/package.json` is the whole dependency surface: `react`, `react-dom`, `radix-ui`,
`clsx`, `class-variance-authority`, `tailwind-merge`. **There is no icon library.**
`lucide-react` is deliberately not a dependency.

Icons are **inlined SVG path data**. Nothing is fetched at runtime.
`static/LICENSE-icons.txt` is the notice and it is **per icon, not per set**, for a measured
reason: Lucide is ISC, but many Lucide icons are derived from Feather and remain MIT under Cole
Bemis's copyright, so a blanket ISC line would be a licence claim the project cannot support.
Six of the eight nav icons turned out to be Feather-derived MIT.

**If you add an icon**: inline the path data, add a row to `LICENSE-icons.txt` naming what it is
used for, its origin and its licence, and check it against Feather's own set before writing the
licence down.

⚠ **Three shipped icons have no row today** - the `.mode-badge` glyphs beside Copy, Move and
Reorganize in place on Organize - and `templates/index.html` points at `LICENSE-icons.txt` for
them, a pointer that resolves to nothing. Recorded in that file on 2026-09-12 as an outstanding
check rather than guessed at. Count against it rather than trusting either:

```sh
grep -c '<svg' packages/truestill-app/src/truestill_app/templates/index.html   # 12
```

Twelve is eight nav icons, one brand mark (ours, in `brand/`, covered by `brand/PROVENANCE.md`)
and those three.

---

## 5. `tokens.css` is the source of truth. Tailwind consumes it and defines nothing

`static/tokens.css` holds every colour, size, space and radius. It is served **standalone** by
the Python app to the non-React page, and it is **never imported into the React bundle** -
`test_tokens_css_is_not_imported_into_the_bundle` refuses that, because a second copy drifts the
first time either is edited and nothing in the Python gate reads CSS.

Tailwind's entry stylesheet under `frontend/src/styles/` is the only place Tailwind is imported,
and **every value in it is a `var()` pointing at `tokens.css`.** Four details there change what
you may write:

- **`@theme inline`, and the `inline` is load-bearing.** Without it Tailwind emits its own
  `--color-*` properties holding **copies** - a parallel palette that would not follow
  `tokens.css` into dark mode. With it, `bg-surface` resolves to whatever `--surface` is at that
  moment, dark mode included.
- **The namespaces are deliberately disjoint.** `tokens.css` uses `--space-*` not `--spacing-*`,
  `--type-*` not `--text-*`, `--corner-*` not `--radius-*`, `--line-*` not `--leading-*`, because
  `tokens.css` is **unlayered** and unlayered wins the cascade: a colliding name there would
  silently redefine a Tailwind utility with nothing erroring.
- **Never `--namespace-*: initial`.** Resetting a namespace removes the **utilities** with it -
  measured in the 4.3.3 spike, `rounded-md`, `text-sm` and `text-muted` stopped generating at
  all, which breaks the shadcn components that ship those class names.
- **Preflight is not imported, on purpose.** `app.css` is a complete hand-written stylesheet that
  normalises what it needs; adding a global reset halfway through the life of seven finished
  screens is a visual change.

⚠ **Tailwind scans markup that is not under the frontend root, and only because two `@source`
lines say so** - `templates/` and `static/app.js`, which builds card markup as strings. **A class
written anywhere else generates no utility, silently**: the build succeeds, the CSS is emitted,
and the element is simply unstyled.

### The type scale - five steps, all rem

```sh
grep -nE -- '--type-(sm|base|lg|display|3xl):' \
  packages/truestill-app/src/truestill_app/static/tokens.css
```

| token | clamp | renders | role |
|---|---|---|---|
| `--type-sm` | `0.875rem` -> `0.984375rem` | 14 -> 15.75px | section labels, field labels, metadata, hints |
| `--type-base` | `1rem` -> `1.125rem` | 16 -> 18px | body |
| `--type-lg` | `1.125rem` -> `1.265625rem` | 18 -> 20.25px | card titles, and every compact metric |
| `--type-display` | `2rem` -> `2.25rem` | 32 -> 36px | page titles, a **separate role** from a big heading |
| `--type-3xl` | `2.5rem` -> `2.8125rem` | 40 -> 45px | **the metric, and nothing else** |

Every step is `rem` and fluid via `clamp(min, rem + vw, max)`. Each step's **floor** is its own
token (`--type-sm-min` and siblings) so the rail and the page cannot become two scales;
`test_the_rail_runs_the_same_scale_as_the_page` holds the pair together.

Three of these are guarded, and the guards are worth knowing before you propose a change:

- **`--type-3xl` is the metric's alone.** `tests/e2e/test_shared_pattern.py::test_only_the_metric_uses_the_metric_size`
  asserts `users == [".metric-value"]`. A heading that takes it stops the metric being the
  biggest thing on the screen, and the hierarchy argument goes with it. A 45px page title above a
  small number is homepage styling; a loud metric under a modest heading is a control panel, and
  this product is the second one.
- **`--type-xs`, `--type-xl` and `--type-2xl` were removed on 2026-09-10 and are not coming
  back.** The app computed **eight** distinct sizes on one screen before that - 11, 12, 12.09, 14,
  14.11, 16.12, 18 and 32.25 - which is the absence of a hierarchy, because no two adjacent sizes
  differed enough to read as different. The ruling's ceiling is six steps.
- **Icon size is not on the type scale**, by design: `--icon-size` is 16px and separate, because
  the nav icons are Unicode glyphs whose size happens to be a `font-size`. They reached 13px once
  by silently inheriting `--type-sm` from their row.

### The spacing scales - and there are TWO of them, one px and one rem

```sh
grep -nE -- '--space-[0-9]+:' packages/truestill-app/src/truestill_app/static/tokens.css
```

`--space-1: 4px`, `--space-2: 8px`, `--space-3: 12px`, `--space-4: 16px`, `--space-5: 24px`,
`--space-6: 32px`, `--space-7: 48px`.

⚠ **Stated explicitly because it is the natural thing to assume wrongly, and it changes what your
design does at the user's text size**: type is rem and follows the root font size;
**`--space-*` is px and does not**. A user who raises their text size gets larger type inside
unchanged padding.

⚠ **AND THERE IS A SECOND SPACING SCALE, WHICH IS REM, FOUND WRITING THIS DOCUMENT ON
2026-09-12.** Every other Tailwind namespace is aliased to `tokens.css` in the theme block -
`--color-*`, `--text-*`, `--radius-*`, `--font-*`, `--leading-*`, `--shadow-*`, the easings -
and **`--spacing` is the one that is not**. So the React and shadcn components run Tailwind's
own default, in rem, proved from the shipped bundle rather than from the source:

```sh
grep -oE -- '--spacing:[^;]*;|\.p-4\{[^}]*\}' \
  packages/truestill-app/src/truestill_app/static/dist/main.css
#   --spacing:.25rem;
#   .p-4{padding:calc(var(--spacing) * 4)}
```

**The two scales agree at 1x and only at 1x.** `--space-1` through `--space-4` are 4/8/12/16px
and `p-1` through `p-4` compute to the same four values at a 16px root, which is why nothing has
ever looked wrong. The app ships a **text-size setting** that sets `:root { font-size: 75% }` and
`125%` (`tokens.css`, `:root[data-text-size="small"]` and `"large"`), so at **large** a shadcn
`p-4` renders **20px** beside an `app.css` `--space-4` of **16px**, and at **small**, **12px**
beside 16px. Past step 4 even the names stop lining up: `--space-5` is 24px, `p-5` is 20px.

**What this means for you**: a React component you add takes the rem scale unless you write
`var(--space-n)` explicitly, and it will drift from the vanilla surface beside it the moment the
user touches the text-size setting. **Do not resolve this by converting `--space-*` to rem as
part of a visual change** - that is a behaviour change to all seven screens and belongs in its
own commit with its own argument. Until it is resolved, prefer `var(--space-n)` over a `p-*`
utility on anything that sits next to vanilla markup.

One related gap, same block: **`--type-display` has no `--text-*` alias**, so a React component
cannot reach the page-title step through a utility at all - only by writing the var.

---

## 6. How to check your work

**In order, cheapest first.**

```sh
# 1. Rebuild the React bundle. Its output is static/dist/{main.js,main.css}.
make frontend

# 2. The whole Python suite plus the contract guards, against a 90 s ceiling. ~40 s.
#    NEVER pipe this - `| tail` returns zero on a red suite. Capture the exit code.
make check; rc=$?; echo "check rc=$rc"

# 3. The e2e files whose subject your diff touches. About two minutes. Iterate HERE.
uv run pytest tests/e2e/test_<the ones you touched>.py

# 4. The whole browser lane, ONCE, before the commit.
make e2e-loop     # chromium only, in parallel, ~95 s on 16 cores - for iterating
make e2e-fast     # both engines, in parallel, ~289 s - the once-before-the-commit run
```

**`make check` cannot see a screen.** It runs with no browser installed and is green with none.
Everything in section 1 - a renamed id, a deleted `data-run` mount, a hook `app.js` still selects
on - is invisible to it. **The browser lane is the only thing that sees the screens.**

**Run the lane on both engines before you are done, not just chromium.** Two timing-dependent
defects in this project's history were WebKit-only, and `make e2e-loop` is chromium. `make e2e`
itself stays serial because that is the shape CI runs on four cores.

**Iterate on the affected files, never on the full lane.** One 28-minute full run returned six
red, and the finding in it - a wording collision two of the failing files assert directly - was
reachable in the first two minutes. The other fifty-eight were spent waiting.

### What the lane is, as a command rather than a number

```sh
uv run pytest tests/e2e --collect-only -q | grep -oE '[0-9]+ tests collected'   # 634
ls tests/e2e/test_*.py | wc -l                                                  # 74
```

### And the rules that will refuse a commit

- **Prose uses the ASCII hyphen, never an em-dash**, and the replacement preserves spacing: an
  em-dash with whatever whitespace hugs it becomes exactly `" - "`, never a hyphen glued to the
  preceding word. A pre-commit hook enforces it.
- **`ruff format` only the files you touched**, always with `--target-version py313`. Do not run
  it across the tree.
- **A living document cites a SYMBOL, never a line number** - `main.tsx:mountAt`, not
  `main.tsx:566`. `test_live_documents_cite_code_that_exists.py` refuses a line wherever a symbol
  encloses it, and `uv run python scripts/cite_symbols.py <doc>` converts one. **Records keep
  their line numbers** and that is a decision, not an unfinished migration: a living document
  must resolve today, a record says what was true when it was written.

---

## 7. The six things most likely to go wrong, in order

1. **A renamed id.** Silent, kills everything below it in `app.js`, invisible to `make check`.
   Section 1.
2. **A class written in `app.js` or `templates/` that Tailwind never scanned.** Silent, element
   unstyled, build green. Section 5.
3. **A design that needs `backdrop-filter`.** Passes on Chromium, flat on WebKit, and
   `@supports` will tell you it is fine. Section 3.
4. **Converting the Organize form to React early.** Breaks `app.js` at parse time, so the rest of
   the screen stops working rather than the form. Section 2.
5. **Moving the renderer and the appearance in one commit.** Twenty-three e2e files assert
   computed styles, and every failure becomes ambiguous. Section 2.
6. **Spacing a React component with `p-*` next to vanilla markup.** Correct at the shipped text
   size, 25% out at the other two. Section 5.
