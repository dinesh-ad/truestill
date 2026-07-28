# Default layout correction: year-first with side bins - Phase 1 (recon + design)

Status: **Phase 1 deliverable, awaiting approval. No code written.** This document is the
review gate.

Changes the default destination structure from `{category}/{yyyy}/{mm}` (source above timeline)
to a year-first timeline at the drive root, with non-camera categories kept as labelled side
bins. Layout and defaults only: dating, dedup, custody, events clustering and every §1 invariant
are untouched.

---

## 1. Recon - what the layout engine actually is today

**One template rules every file.** `layout.LayoutTemplate` is a `/`-separated token string
parsed once and rendered per file. There is exactly one template per catalog, stored under the
settings key `layout_template` (`layout.py:58`) and resolved by `layout.resolve_template`
(`layout.py:97`) as *stored, else `DEFAULT_TEMPLATE`*.

**Three render sites**, all funnelling into `LayoutTemplate.render`:

| Site | File | What it has in hand |
|---|---|---|
| Non-event files | `organizer.build_relative` (`organizer.py:218-231`) | the label **string** only |
| Named-event members | `organizer.apply_events` (`organizer.py:377-383`) | the full `Decision` (so `category.rule` is reachable) |
| Migration re-render | `migrate.plan_migration` (`migrate.py:80-86`) | catalog rows only |

**Two behavioural rules** the engine already guarantees, both of which the new design must
preserve (`layout.py:16-24`, `layout.py:165-190`):

- **Undated collapse** - a file with no date drops every date-derived segment and gets a single
  `Undated` folder instead. `{category}/{yyyy}/{mm}` → `{category}/Undated`.
- **Event append** - an event member's date tokens resolve from the *event start* (so a
  cross-month event stays whole under its start month), and if the template has no explicit
  `{event}` token the event folder is appended.

**Validation is real and worth keeping**: unknown tokens, empty segments, illegal path
characters and Windows reserved names are rejected at parse time (`layout.py:124-155`); token
values are sanitized so a value can never inject a directory level (`layout.py:88-94`);
`preview` surfaces the data-dependent risks - empty token values, near-260-char paths, and
case-insensitive collisions (`layout.py:218-251`).

**Presets are a plain dict** (`layout.py:260-266`) read dynamically by every consumer: the CLI
derives `--preset` choices from `tuple(PRESETS)` (`cli.py:263`) and lists `PRESETS.items()`
(`cli.py:1065`); the app serves `dict(PRESETS)` (`service.py:711`) and the Settings dropdown is
built by iteration (`app.js:844`). **One dict entry reaches both front-ends.**

### 1.1 What the recon changes about the proposal

Five findings that the design has to answer. Two of them change the shape of the work.

**F1 (blocking, changes the design) - the default flip is silent for existing libraries.**
`layout_template` is written **only** when a user explicitly sets it (`cli.py:1080`,
`service.py:732`). Nothing persists it at organize time. So every library organized with the
defaults has `stored = None`, and `resolve_template` hands it whatever `DEFAULT_TEMPLATE`
happens to be. **Changing the constant would silently re-shape the next run of every existing
library** - new files landing year-first while the existing tree stays category-first, with no
prompt and no migration. That is precisely the split the "new default applies forward,
migration offered never forced" rule exists to prevent, and the rule does not currently have a
mechanism behind it. §4 proposes the pin.

**F2 (blocking) - routing cannot key on the label string.** With `--by-device` the timeline
label is the hardware name, not `Camera` (`categorize.py:228-231`). A router that tests
`label == "Camera"` sends every `--by-device` user's entire timeline into a side bin. The
robust key is `CategoryMatch.rule` (`models.py:126`): exactly one rule - `device` - produces the
timeline; `screenshot_metadata`, `screenshot_name`, `filename_convention`, `software`,
`saved_heuristic` and `fallback` all produce side bins.

**F3 - the rule is available at organize time but not at migration time.** `build_relative`
currently receives the label string only, though its caller has the full `CategoryMatch`
(`organizer.py:285`) - a one-argument change. The catalog is the harder half: `files` stores
`category` (the label) and **no rule** (`catalog.py`, `files` DDL), and
`copies_for_migration` selects `category, captured_at, event_slug, event_start`
(`catalog.py:373-391`). A migration therefore cannot reproduce organize-time routing from
stored data. §4 resolves this **without a schema change**.

**F4 - the event's human name is destroyed before it reaches the layout.** `slugify` casefolds
and hyphenates (`events.py:165-168`), `event_dirname` emits `YYYYMMDD_slug`
(`events.py:171-173`), and `event_review` puts only `(start, slug)` into `assignments`
(`event_review.py:129`). "Goa Trip!" → `goa-trip` is **not reversible**, so
`2014-08-20 - Goa Trip` cannot be reconstructed from the slug. The name *is* stored -
`events.name` (`catalog.py:57`) - it is simply never plumbed to the render. Fixing this is
plumbing plus one extra column in the migration SELECT, not a schema change.

**F5 - a settings key is free.** `settings` is a `(key, value)` table (`catalog.py`), so
persisting a richer layout scheme needs **no schema version bump**. v11 stays unspent.

---

## 2. The routing mechanism

**Recommendation: route-then-render, in the resolver - your prior is right, and for a reason
worth stating.** A `LayoutScheme` holds two parsed `LayoutTemplate`s and a routing predicate;
the resolver picks one and renders it. The template DSL does not change at all.

```
LayoutScheme
  ├── timeline : LayoutTemplate   "{yyyy}/{yyyy}-{mm}"
  ├── side_bin : LayoutTemplate   "{category}/{yyyy}/{yyyy}-{mm}"
  ├── events   : EventNaming      readable | slug
  └── route(match: CategoryMatch) -> LayoutTemplate      # rule == "device" -> timeline
```

**Why this and not the alternatives:**

| Option | Verdict |
|---|---|
| **A. Route-then-render (recommended)** | Each template stays independently parseable, validatable and previewable by the machinery that already exists. The routing decision is one predicate in Python, testable in isolation and inspectable in a preview. Cost: the persisted setting becomes a small structure rather than a bare string (F5 makes that free), and every `resolve_template` call site becomes `resolve_scheme`. |
| **B. Conditionals in the template DSL** (`{category:unless=Camera}/…`) | Rejected. It turns a validated 6-token grammar into a small programming language - conditionals, an escape story, and error messages a user cannot act on. `parse` currently proves a template safe from the string alone (`layout.py:124`); a conditional grammar makes that guarantee data-dependent. The DSL exists so the *structure* is data, not so the *policy* is. |
| **C. One template with a `{bin}` token** that renders `""` for camera and `Category/` otherwise | Rejected, and it is the tempting one. An empty segment is not the same as an absent segment - `_render` drops empty segments already (`layout.py:184`) so it *nearly* works, but the token's meaning becomes "sometimes a directory level, sometimes nothing", which defeats the sanitizer's guarantee that a value never changes the path's depth (`layout.py:88-94`). It also cannot express *different date shapes* per branch, which the target needs: root timeline is `{yyyy}/{yyyy}-{mm}`, side bins are `{category}/{yyyy}/{yyyy}-{mm}`. |
| **D. Two catalogs / two destinations** | Rejected outright: breaks custody (one drive, one marker, one `file_copies` set) for a presentation concern. |

**Routing predicate, stated exactly:** `match.rule == "device"` → timeline; everything else →
side bin. One rule, not a list of labels, which is what makes `--by-device` work (F2). It is a
single function with a single test per rule name.

**Undated under the new default** needs an explicit decision, because the collapse rule
(`layout.py:173-177`) will otherwise put timeline-undated files in a bare `Undated/` at the
drive root, next to the year folders. That is defensible - it is a real bin, and the target
puts the timeline at the root - and I recommend it, but flagging it because it is a visible
root-level folder nobody asked for. Side-bin undated is unchanged: `Screenshots/Undated`.

---

## 3. Presets

`PRESETS` gains the new default and keeps both philosophies one click away. Because every
consumer reads the dict dynamically (§1), this reaches CLI and app with no other change.

| Name | Shape | Role |
|---|---|---|
| `year-first` | timeline `{yyyy}/{yyyy}-{mm}`, bins `{category}/{yyyy}/{yyyy}-{mm}` | **new default** |
| `category-first` | `{category}/{yyyy}/{mm}` | today's default, preserved verbatim so a user can stay put or return |
| `category-last` | timeline `{yyyy}/{yyyy}-{mm}`, bins `{yyyy}/{yyyy}-{mm}/{category}` | considered as you asked. **Recommended: offer it, with a warning** - it scatters one category across every month, which makes "show me my screenshots" a filesystem-wide search rather than one folder, and it re-creates the junk-mixing the category split exists to prevent. It is coherent for someone who wants strict chronology, so it should exist; it should not be quiet about the trade. |
| existing five | unchanged | `category-year-month`, `category-year-month-day`, `category-year`, `flat-date`, `category-year-event` |

**Preset round-tripping is a guard test, not a hope.** Selecting a preset, persisting it,
reloading, and re-rendering the samples must reproduce the same paths - including the legacy
single-string presets, which must keep parsing after the stored format grows (§4, back-compat).

**Settings preview** (`service.py:711`, `_render_preview`, `SAMPLE_CONTEXTS` at
`layout.py:270-274`) must render *the shape*, which means the samples have to exercise the
router. Today all three samples are label-only. They need a rule attached, plus a fourth sample:
a **named-event** camera file, which currently has no preview representation at all and is the
single most visible part of the new structure.

---

## 4. Migration

Uses the shipped `migrate-layout` engine unchanged in mechanism: preview by default, journalled
(`migration_journal`, schema v8), crash-safe and resumable, connected-drive rules as they are.
Four things it needs.

**4.1 The pin (answers F1, and is the part I would build first).** Before the default constant
changes, an existing catalog must have its *current* layout written down. On first use of a
build that carries the new default: if the catalog has organized files and **no** stored
layout, persist `category-first` and say so once. The library keeps its shape; the new default
applies to genuinely new libraries; the migration is then an explicit, previewed choice. Without
this, "new default applies forward, migration offered never forced" is a sentence in a document
with no mechanism under it.

**4.2 Migration routing without a schema change (answers F3).** `plan_migration` cannot recover
`category.rule` from the catalog. Rather than add a column and backfill it with a guess, make
routing **per distinct label** and **show the user the map**. There are a handful of distinct
labels in any library, and the preview lists them:

```
  Camera        ->  timeline   2014/2014-08/          8,412 files
  Screenshots   ->  side bin   Screenshots/2014/…       391 files
  WhatsApp      ->  side bin   WhatsApp/2014/…        1,204 files
  Saved         ->  side bin   Saved/2014/…             117 files
```

Defaulted from the rule chain (`Camera`, or the recorded device labels under `--by-device`) and
**confirmable**, so a `--by-device` library is never silently mis-binned. This is the
never-silent rule applied to a routing decision, and it is strictly more honest than a
persisted guess.

**4.3 Event folders need the name (answers F4).** `copies_for_migration` adds `e.name` to its
SELECT - one column, no schema change - and `assignments` carries the name alongside
`(start, slug)`. `EventNaming.readable` renders `YYYY-MM-DD - Name`; `EventNaming.slug` keeps
`YYYYMMDD_slug` for the legacy presets, so switching preset round-trips. Sanitization stays
exactly as it is underneath (`_sanitize_value`, reserved-name check), which is what keeps a
name like `AUX` or `Trip: Goa/2014` safe. Cross-month-under-start-month is untouched - it is a
property of `RenderContext.date` (`layout.py:111-114`), not of naming.

**4.4 Acceptance on the real library.** `truestill migrate-layout` preview against **The Memory
Cabinet**, showing the full old→new plan, the label routing map, the counts and every warning -
and stopping there. No file moves without your explicit confirm.

---

## 5. Honest scope, and what the recon says to flag

**Untouched:** dating and its tier order, dedup (both tiers), the catalog's custody tables,
drive identity, verify, backup, reclaim, undo, events *clustering* and its signature/skip
memory, and every §1 invariant. Copy-only holds; dry-run-is-default holds; a read never writes -
with the one exception the pin (§4.1) deliberately makes, which is a settings write on an
explicit run and must be stated plainly rather than slipped in.

**Flags the recon raises that the design must carry:**

1. **The default flip is the risky part, not the layout** (F1). The structure is easy; not
   splitting an existing library across two shapes is the work.
2. **Root-level namespace collision.** With the timeline at the root, a side-bin category whose
   label looks like a year - `software` labels are dynamic and user-data-derived - would land
   beside the year folders. Rare, but it is a real collision on a real filesystem and wants a
   guard test.
3. **Path length grows.** `2014/2014-08/2014-08-20 - Some Long Trip Name/` is longer than
   `Camera/2014/08/20140820_slug/`. `PATH_LENGTH_WARN` (200, `layout.py:75`) already warns, and
   the preview surfaces it, but the new default sits closer to the Windows limit than the old
   one. Worth measuring against your real library during the acceptance preview.
4. **`{event}` token semantics** interact with the append rule. The scheme's event naming and
   an explicit `{event}` token must not double-render; the existing `category-year-event` preset
   pins the legacy behaviour and should be part of the round-trip test.
5. **This changes what "organized" looks like in every screenshot and doc.** The README tree,
   `docs/CLAUDE.md`, `IMPLEMENTATION_STANDARDS.md` §4 and the QA screenshots all show
   `<Label>/YYYY/MM/`. §4 of the contract is normative and must change with the code, in the
   same commit.
6. **Backlog item (w)** (self-describing months) is absorbed by this and should be closed as
   delivered-by rather than left open.

**Not proposed, deliberately:** letting a user nominate additional rules as "timeline" (e.g.
scanned negatives), any change to how categories are *derived*, and any use of the
`{category}`-less timeline as a lever to revisit the `Saved/` heuristic. Each is a separate
argument on its own evidence.

---

## 6. Build plan, on approval

1. `LayoutScheme` + router + `EventNaming`, with the legacy string format still parsing.
2. The pin (§4.1) and its test, **before** the default constant moves.
3. Default flip + presets + `SAMPLE_CONTEXTS` gaining a rule and an event sample.
4. Migration: `e.name` in the SELECT, the label routing map, preview rendering.
5. Docs: contract §4, README tree, `docs/CLAUDE.md`, CHANGELOG, close backlog (w).

**Guard tests:** routing per rule name (all seven, including `--by-device` labels); event folder
naming both ways incl. sanitization of hostile names; preset round-trip through persistence for
every preset; undated collapse on both branches; the pin (existing library keeps its shape,
fresh library gets the new default); migration preview correctness old→new incl. the label map;
root-level year-lookalike collision.

**Then:** `make check` green, all four CI lanes green, and the `migrate-layout` preview on The
Memory Cabinet presented for your confirm before anything moves.


---

## 7. Addendum (2026-07-28): what the Settings surface must report - decided in 2c

Building the live `Current:` label forced a choice the design had not pinned, recorded here
because getting it wrong would have flipped the default a step early.

**The label reports the layout *in force*, not the layout we are heading towards.** The obvious
implementation - show `DEFAULT_PRESET` for a library that has stored nothing - is wrong until
the flip lands: an organize run still renders through `DEFAULT_TEMPLATE_STRING`, so Settings
would have advertised a year-first shape while runs produced category-first. That is the same
class of defect the soak found eight times (the screen describing something the system did not
do). The label derives from `effective_layout_string`, so **the flip in 2d makes Settings and
runs agree in a single move**, with no second edit here.

**"Legacy" means a library with its own category-first layout written down** - pinned or chosen -
not "a library whose current default happens to be category-first". Before the flip every fresh
library sits on a category-first default; framing those as legacy would tell a brand-new user
their empty library needs migrating. So the flag is `stored is not None and scheme.is_legacy`.

**Rejected: showing the new default with a "will apply after you switch" caption.** It puts two
shapes on screen and makes the reader work out which one governs their files. One truthful
answer beats two hedged ones.

**Purity, restated because the surface is a read.** Everything in `layout_state` derives from
`effective_layout_string`, which never writes. A library that qualifies for the pin can be
inspected indefinitely without the pin firing; only a real run persists it. Pinned by
`test_opening_settings_never_writes_a_setting`.
