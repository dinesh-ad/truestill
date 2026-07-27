# truestill - UI v2: Usability & Design Pass (Phase 1: research + design)

Status: **Historical (2026-07-27) - built and since superseded in parts.** Recorded as
*Phase 1 deliverable, awaiting approval; no build* and approved and built as such. The
progress display, completion cards and Backups screen described here were **rebuilt during
the soak test** (`PROJECT_STATUS.md` §2.1); where this document and the shipped UI differ,
the shipped UI and `IMPLEMENTATION_STANDARDS.md` §9 win. Nothing below is rewritten.

Original status line: *Phase 1 deliverable, awaiting approval.* No build. Presentation + UX over the existing
working API; the engine is untouched. Constraint held: vanilla JS + server-rendered HTML + a
hand-written design-tokens CSS layer, no toolchain, no heavy deps.

## Why (first-user verdict)

The engine passed the acceptance walkthrough; the interface failed. From that real session:
he **ran against the wrong folder** (a placeholder path looked like a real value), got **raw JSON**
as his result, **saw an error before touching anything**, and rated the design **unacceptable for
launch**. Every fix below traces to one of those.

---

## 0. Tooling inventory (addendum)

- **frontend-design plugin** (`frontend-design@claude-plugins-official`) - **already installed**
  (`~/.claude/plugins`), skill loaded and its framework applied in §2 below.
- **Visual verification for Phase 2** - the **Claude-in-Chrome MCP** (`mcp__claude-in-chrome__*`)
  is available; it renders the local app and takes screenshots, so Phase 2 is screenshot-driven,
  not blind CSS. No Playwright needed; nexdue ships no `.mcp.json`, so nothing to borrow there.
- **nexdue** - mirrored only its *documentation discipline* (`docs/BRAND_COLORS.md`: named hex +
  role table + CSS-var mapping + do/don't). **Not** its stack: no React/Next/Tailwind/TypeScript,
  no violet brand. truestill gets its own identity (§2).
- Other marketplace plugins (LSPs, code tools) - not design-relevant.

---

## 1. Research - folder selection (server-backed picker)

Settled backend fact: browsers deliberately withhold absolute host paths from file inputs and
drag-drop, so a web app needing the *server's own* path must **list its own filesystem** and let
the client drill through it. A bare text path field is the universal failure - it's filed as a bug
against every tool below, and it's exactly what bit truestill's first user.

**What the category does (with sources):**

- **Jellyfin - the best-in-class model** (Immich/qBittorrent users cite it as the target). Adding a
  library opens a **modal directory picker**: server-provided **drives/roots**, click-to-descend
  directory list, and a **manual field** as an escape hatch. Backend =
  `GET /Environment/Drives` (roots) + `GET /Environment/DirectoryContents?path&includeFiles=false`
  (children, dirs-only is a first-class flag) + `GET /Environment/ParentPath` (up).
  [Jellyfin libraries](https://jellyfin.org/docs/general/server/libraries/),
  [Environment API](https://typescript-sdk.jellyfin.org/classes/generated-client.EnvironmentApi.html)
- **Filebrowser - the drill-down reference.** A **breadcrumb bar** of clickable path segments (click
  an ancestor to jump up - no separate up-button needed) + a **single-click-to-descend** list; the
  route reflects the path. [github.com/filebrowser/filebrowser](https://github.com/filebrowser/filebrowser)
- **Syncthing #7418** - a repeatedly-refiled demand for a graphical picker; the reporter's argument:
  users *"have pretty much no idea what is a path… but can navigate a directory hierarchy with a
  graphical tool"* (lineage: #2958, #6242). Syncthing shipped only **type-ahead autocomplete**
  (`GET /rest/system/browse?current=`), which proved brittle around `~`, trailing slashes, and roots
  (#4590, #9990) - a datapoint that **click-to-drill beats autocomplete-only**.
  [#7418](https://github.com/syncthing/syncthing/issues/7418),
  [browse REST](https://docs.syncthing.net/rest/system-browse-get.html)
- **Immich #17765** (external libraries still manual, users asking for "list `/share/Photos…` to
  click, like Jellyfin") and **qBittorrent #16195** (no filesystem browser; fixed only by alt
  front-ends) - both confirm the pain is live and the expected mental model is Jellyfin's.

**Recommended model for truestill - a "Browse…" button → Jellyfin-style modal:**

1. **Common-roots rail** (server-enumerated, never hardcoded): Home, Pictures, Downloads, Desktop,
   and **mounted drives** (`/media/*`, `/mnt/*`, `/run/media/*`; `/Volumes/*`; drive letters).
2. **Breadcrumb** of clickable segments across the top (Filebrowser's up-navigation) + a list of
   **directories only**, single-click to descend, with a real empty state.
3. **Recent locations** persisted (the **`settings` table exists since v7**) - highest-value for a
   repeat-run backup tool.
4. **Text field retained** for power users, kept two-way in sync with the tree (autocomplete as an
   accelerator, never the only path).
5. **The differentiator none of them nail - inline validation + count on the confirm button.** The
   primary button reads **"Use this folder · 37 photos here"** (or **"No photos or videos here ⚠"**),
   so the exact absolute path *and* a right-folder signal are visible **before** the pipeline runs -
   directly fixing the wrong-folder incident.

**Endpoint shape (one read-only route, guarded by the existing `LocalGuard`):**
`GET /api/fs/dirs?path=<abs>` → child **directories** of `path` (or the **roots/shortcuts** when
`path` is empty), each `{ name, path, has_children }`. Companion `GET /api/fs/validate?path=<abs>`
→ `{ exists, is_dir, readable, writable, media_count }` powers the confirm-button preview.
**Rules:** dirs only; `os.path.realpath` normalize server-side (client never constructs paths);
refuse traversal outside permitted roots (path-traversal guard); same token auth as everything else.
This lists directories only - it does **not** touch the pipeline (see NOT-in-scope).

---

## 2. Design direction (frontend-design framework, applied)

### Purpose / subject (pinned)

truestill takes the chaotic pile of someone's photos and videos - **irreplaceable memories** - and
quietly sorts them, removes duplicates, and makes sure they exist in **more than one place**. The
home screen's single job: let a non-technical person point at a messy folder and **trust** that
truestill will organize it *without losing anything*. The product's real material is **custody of
memories**; trust is the whole product.

### Tone

Calm, precise, trustworthy - Immich/Linear restraint. For a trust utility the deliberate
**aesthetic risk is radical calm**: one quiet signature, everything else disciplined and silent.
No flourish, no hero gradient, no marketing voice. (Explicitly rejects the three AI-default looks:
warm-cream+serif+terracotta, near-black+acid-green, broadsheet hairlines - and nexdue's violet.)

### Constraints

No build step; hand-written CSS custom properties only; zero external requests (local-first, CSP -
so **no web-font CDN**, no third-party files). Must theme light + dark, be keyboard-accessible, and
respect reduced motion.

### Differentiation - choices specific to *this* subject

- **Type is the signature, and it's true to the subject.** truestill's world is filenames, counts,
  dates, and `sha256` - so **data speaks in monospace**. Body/UI uses the system sans; every
  **path, count, hash, and the wordmark** use the system **monospace** stack. This costs zero
  bytes (no web font), reads "precise file tool that respects your data," and separates truestill from
  the all-sans SaaS default. Structure is information: monospace *is* the vernacular of the subject.
- **The custody strip (the one memorable element).** truestill's promise is 3-2-1: your memories live
  in more than one verified place. That truth is made ambient as a tiny monospace indicator -
  `▪ ▪ ▫` filling by verified-copy count, **in the green "safe" semantic** - shown beside each drive
  and in a persistent library line (`1,240 photos · safe in 2 places`). It encodes something real
  (redundancy), stays quiet, and becomes truestill's mark. **Not** a big number with a gradient.

### Design tokens - the accent decision (revised after the §3 survey)

**Changed from my first pass, and why.** My first pass proposed a *verified-teal* accent. The
visual survey (§3) shows every restraint-first peer - Immich `#4250AF`, Linear `#5E6AD2`,
Filebrowser `#8EB2FF` - independently converges on a **muted indigo-blue**, and flags that a
backup tool should keep **green reserved for "verified / backed up."** Teal (a blue-green) would
*compete* with that green-means-safe semantic - the exact thing truestill's custody strip depends on.
So the accent becomes a **calm indigo (`#4C63C4`)** and **green (`#2f9e57`) becomes the "safe"
semantic**. This is the more subject-specific choice, not less: two meanings, cleanly separated -
**indigo = act, green = safe** - with the boldness spent on the *monospace-data + custody-strip*
signature, not the accent. (Indigo-for-trust is a genuine category convention here, not an AI-art
default like terracotta/acid-green; adopting it inherits the peers' credibility.)

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--accent` | `#4C63C4` | `#A9B6F0` | indigo - primary action, active nav, focus |
| `--accent-subtle` | `#eef1fb` | `#1c2030` | selected / active-nav tint |
| `--bg` | `#f7f8fa` | `#0b0c0e` | app canvas (never pure white/black) |
| `--surface` | `#ffffff` | `#16181c` | cards |
| `--border` | `#e2e5ea` | `#24272e` | hairline borders (structure by luminance) |
| `--text` | `#16181d` | `#e7e9ee` | headings / high-emphasis |
| `--text-secondary` | `#6b7280` | `#a3a9b5` | secondary text |
| `--text-muted` | `#9aa1ad` | `#6f7681` | captions, example hints |
| **`--success`** | `#2f9e57` | `#46b46a` | **verified / backed up - the custody strip** |
| `--warning` | `#c98a1a` | `#d69a3a` | in-progress / "no media here" |
| `--danger` | `#cf4b52` | `#e0686e` | failed / destructive confirm (muted, not vermilion) |

- **Neutrals carry all structure** (7 cool-gray steps); surfaces separate by **luminance + 1px
  hairlines**, not shadows; text hierarchy by luminance tier, never color.
- **Type:** `--font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;`
  `--font-mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;` - paths,
  counts, hashes, wordmark, custody strip all in **mono** (the type signature). Scale (px):
  `12 · 13 · 15 (base) · 18 · 22 · 28`; weights 400/500/600; negative tracking on ≥18px.
- **Spacing** 4-based: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`. **Radius** one family:
  `sm 6 · md 10 · lg 14 · pill 9999` (restrained; not zero). **Shadow** minimal: `0 1px 2px
  rgba(16,24,40,.05)` on light cards; **off in dark** (luminance does the work).
- **Buttons:** primary (filled indigo, **one per view**) · secondary (outline) · ghost (text) ·
  danger (filled `--danger`, destructive only). Focus: 2px `--accent` ring at 45%, offset 2px.
- **Table/list:** row hairlines only (no vertical grid), muted medium-weight headers, whole-row
  hover - a quiet ledger; byte counts / paths / hashes in mono so data columns align.

The full `tokens.css` (plain custom properties) + a small `app.css` reimplement all of this; both
themes via `@media (prefers-color-scheme)` and a `data-theme` override; no framework, no web font.

---

## 3. Research - visual language survey

Three restraint-first UIs, read for concrete, reusable specifics. **Headline: all three land
independently on a muted blue/indigo single accent** - the strongest signal for a trust utility.

- **Immich** (the category analog - local-first photo library). One desaturated-indigo accent
  (`#4250AF`) that **inverts lightness in dark mode** (`#ACCBFA` on `#0A0A0A`); backgrounds are
  near-white/near-black, never pure; surfaces stack in near-neutral grays; **one chromatic accent,
  neutrals do the structural work.** The newer `@immich/ui` formalizes this as oklch semantic scales
  (`primary/success/danger/warning/info` × 11 steps). *Why it reads calm:* nothing competes with the
  single desaturated accent; dark mode softens (`#0A0A0A`, not `#000`) so surfaces separate by
  luminance. [styling system](https://deepwiki.com/immich-app/ui/3.3-styling-system),
  [theme PR #14298](https://github.com/immich-app/immich/pull/14298)
- **Linear** (the restraint reference). Single lavender-blue accent `#5E6AD2` used *only* on the
  mark, focus ring, and primary CTA. Depth from a **luminance ladder + 1px hairlines, no drop
  shadows on dark**. Text in four luminance tiers (`#F7F8F8 → #8A8F98 → #62666D`) - hierarchy by
  luminance, never color. Strict **4px spacing**; radius `4/6/8/12/16/24/pill`; 2px focus ring.
  [Linear tokens](https://github.com/voltagent/awesome-design-md/blob/main/design-md/linear.app/DESIGN.md),
  [redesign notes](https://linear.app/now/how-we-redesigned-the-linear-ui)
- **Filebrowser** (modern theme - corroborating self-hosted read). Accent `#8EB2FF` (soft
  periwinkle - again blue, again desaturated); dark slate ladder `#1F2330 → #292D3E → #383D51` by
  luminance; near-invisible borders; **one radius token (~11px)** everywhere.
  [modern theme](https://github.com/Teraskull/file-browser-modern-theme)

**Cross-tool synthesis adopted into §2:** one desaturated blue/indigo accent; neutrals carry
structure (5–7 near-neutral steps, separated by luminance); never pure black/white canvas;
dark-mode accent lightens + desaturates; 4px spacing, 1px hairlines, minimal/no shadows, one radius
family; text hierarchy by luminance tier. The §2 token table is the concrete result - with truestill's
own move of **reserving green for the "safe/verified" custody semantic**, which the survey
explicitly recommends for a backup pipeline.

---

## 4. Copy audit - replacement list

Rule applied: *name things by what a person controls and recognizes, never by how the system is
built; active voice; the button's verb is the outcome.* System jargon **out of the UI** (it stays
in code, the CLI, and docs).

| Where | Current (system voice) | Replacement (person's voice) |
| --- | --- | --- |
| Organize source | `Source folder` + placeholder `/photos/dump` | **Folder to organize** · empty field, grey *example* hint, **Browse** primary |
| Organize dest | `Destination (drive root)` `/mnt/DriveA` | **Organized folder** (where your sorted copies go) · Browse. *Not* "Backup folder" - this folder is the organized **result**, not the backup; "backup" is reserved for the drives on the Backups screen where it is literally true. |
| Organize run btn | `Run for real` | **Organize N files** (names the outcome; N from the preview) |
| Preview btn | `Dry-run preview` | **Preview** (subtext: "see what would happen - nothing is changed") |
| Skip-undated | `Skip undated files (don't copy to Undated/)` | **Skip files with no date** (they won't be sorted into an Undated folder) |
| Drives screen | `Drives` | **Backups** |
| Verify | `Verify a connected drive at …` | **Check a connected backup drive** |
| Search screen | `Where is…?` / `Find (offline)` | **Find a file** / **Search** |
| Events screen | `Event review` · `Camera photos only · name / skip / merge / split` | **Trips & events** · "Group your camera photos by when they were taken" |
| Rescue screen | `Rescue a Google Takeout export` | **Import from Google Photos** (Takeout) |
| Settings note | `… existing files stay where they are (split-era).` | "**Changing this only affects files you organize from now on.** Files already sorted stay put." - **"split-era" never appears in the UI** |
| Migrate | `Move the files` | **Move existing files to match** |
| Category `Saved` (`saved_heuristic`), `device` rule | shown raw | friendly labels: **Camera**, **Screenshots**, **Saved images**, **WhatsApp**, … (rule names never shown) |
| Footer | `Nothing is written until you choose "Run for real".` | "**Nothing is changed until you choose to organize.**" |

---

## 5. Design proposal

### 5.1 Navigation - one screen at a time

Replace the single scrolling page (all six sections stacked, everything firing on load) with a
**left sidebar** and one active screen. Sidebar is calm: wordmark (mono) on top, the persistent
**custody line** at the bottom (`1,240 photos · safe in 2 places`).

```
┌──────────────┬─────────────────────────────────────────────┐
│ truestill        │                                             │
│              │   [ active screen: cards ]                  │
│ ▸ Organize   │                                             │
│   Trips      │                                             │
│   Import     │                                             │
│   Backups    │                                             │
│   Find       │                                             │
│   Settings   │                                             │
│              │                                             │
│ 1,240 photos │                                             │
│ safe · 2 pl. │                                             │
└──────────────┴─────────────────────────────────────────────┘
```

Screens: **Organize** (home/default) · **Trips & events** · **Import** · **Backups** · **Find** ·
**Settings**. On narrow widths the sidebar collapses to a top row of tabs.

### 5.2 Results are cards, never JSON

Every operation renders a **human summary card**, not `JSON.stringify`. Example - organize preview:

```
┌ Preview ─────────────────────────────────────────────┐
│  1,240 photos and videos found                       │
│                                                      │
│  1,180  new - will be organized                      │
│     54  duplicates - already backed up, will skip    │
│      6  no date - will go to “Undated”               │
│                                                      │
│  Into these folders:  Camera 980 · WhatsApp 150 · …  │
│                                                      │
│  ⚠ 3 files skipped (not photos/videos)   [details ▾] │
│                                                      │
│                         [ Organize 1,186 files → ]   │
└──────────────────────────────────────────────────────┘
```

`details ▾` expands the skipped-by-extension table and any warnings. The raw JSON endpoints stay
for the API; the UI never shows them.

### 5.3 Guardrails (each maps to a session failure)

- **a. Paths.** Fields start **empty** with a grey *example* hint styled unmistakably as an example
  (`e.g. /home/you/Pictures`, `--muted`, italic), never a value-looking placeholder. **Browse** is
  the primary affordance → server-backed folder modal (§1). On pick, inline validation:
  **"37 photos and videos here"** (accent) or **"No photos or videos here ⚠"** (warn).
- **b. Zero-media.** A preview over a folder with no media shows a prominent card:
  **"Nothing to organize here - is this the right folder?"** with **Browse** re-offered. Choosing
  to organize a zero-media folder requires an extra **confirm** (there's nothing to do).
- **c. No error before action.** Screens load **neutral** - an empty Backups screen reads
  "No backup drives yet. Connect one and click Check." Empty states are invitations, not errors.
  Nothing calls the API and paints red on load.
- **d. Disabled buttons say why.** A disabled **Organize** shows, inline, "Preview first" or "Pick
  a folder to organize" - never a dead grey button with no reason.

### 5.4 Progress

Keep the working SSE bars, restyled: a thin accent bar, a **mono count** (`412 / 1,186`), the
current phase ("Copying…"), and a real **Cancel** that reports what completed ("Stopped - 412
organized, the rest untouched"). Reduced-motion: the bar fills without easing.

### 5.5 Screen-by-screen wireframes

Below are the six screens (markdown wireframes). Copy uses §4; every result is a card (§5.2).

**Organize (home)**
```
Organize
Point truestill at a messy folder; it sorts copies into an organized folder - originals untouched.

Folder to organize   [ /home/you/Pictures/dump          ] [ Browse ]   37 photos here
Organized folder     [ /media/BackupA                   ] [ Browse ]   ✓ backup drive
[ ] Skip files with no date

              [ Preview ]   ( Organize … - disabled: Preview first )

┌ Preview card (§5.2) ┐         ┌ Progress (§5.4) when running ┐
```

**Trips & events**
```
Trips & events
Group your camera photos by when they were taken, then name the trips.

Folder   [ … ] [ Browse ]      [ Find trips ]

┌ cluster ┐  Aug 14–21, 2023 · 240 photos · ~Goa      [ name it… ] [ split ] [☐ merge ]
┌ cluster ┐  Sep 3, 2023 · 60 photos                  [ name it… ] [ split ] [☐ merge ]
[ Merge checked ]                                   [ Save names → ]
```

**Import (Google Photos / Takeout)**
```
Import from Google Photos
Bring in a Google Takeout export - truestill recovers the real photo dates and removes duplicates.

Takeout folder [ … ] [ Browse ]   Organized folder [ … ] [ Browse ]   [ Preview import ]

┌ report card: 12,401 photos · 3,100 duplicates removed (~8.2 GB) · dates recovered … ┐
```

**Backups**
```
Backups                                                  1,240 photos · safe in 2 places
┌ drive ┐ BackupA   1,186 files · 24.1 GB · checked 2d ago     ▪▪▫   [ Check ] [ Find here ]
┌ drive ┐ BackupB     980 files · 20.3 GB · checked 5d ago     ▪▪▫   [ Check ]
⚠ 54 photos exist in only one place.   [ see which ▾ ]
Connect a drive and click Check to verify its copies.
```

**Find**
```
Find a file
Search your whole library - works even when the drives are unplugged.

[ beach 2019                       ]  [ Search ]
┌ result ┐ IMG_20190612.jpg   BackupA · Camera/2019/06/   · checked 2d ago
```

**Settings**
```
Settings

Folder layout   Current: Camera / 2023 / 08 / …            [ change ▾ ]
   Preview:  a beach photo →  Camera/2023/08/IMG_… 
   Changing this only affects files you organize from now on. Files already sorted stay put.

Move existing files to match   [ pick a connected drive ] [ Browse ]  [ Preview move ]

Appearance   ( ) Light  ( ) Dark  (•) Match system
```

### 5.6 Explicitly NOT in scope (v2)

- **No new features and no engine changes** - presentation + UX only over today's API (one new
  read-only `GET /api/fs/list` for the picker is the sole addition, and it lists directories, it
  does not touch the pipeline).
- **No build toolchain** - vanilla JS, server-rendered HTML, hand-written `tokens.css` + `app.css`.
  No React/Tailwind/TS, no bundler, no web-font CDN.
- **No native shell** (Tauri/Electron) - still deferred.
- **No account/multi-user, no theming beyond light/dark, no i18n** in v2.
- **App reclaim/move-source surface stays deferred** - destructive actions remain CLI-only (per
  the (k) decision).

---

**Stopping here for approval** of: the navigation split, results-as-cards, the four guardrails, the
copy replacements, and the **design direction** (cool-neutral ground · calm **indigo** accent with
**green reserved for "safe/verified"** · monospace-for-data type signature · the custody strip). On
approval, Phase 2 builds it screen by screen with screenshot verification via Claude-in-Chrome.
