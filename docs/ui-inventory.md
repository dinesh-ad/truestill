# UI inventory - every surface a person reads, and what is wrong with it

**Rebuilt 2026-08-06 at `16fcdd7`. This is a REBUILD FROM SOURCE, not a recovery.**

## Read this first: it is tracked now, after being lost twice

This file was **untracked on purpose** - a working sheet, not a record, churning faster than a
commit-per-edit seemed worth. That choice had a cost and the cost was paid twice: **untracked
means git does not have it.** No history, no `git checkout`, no reflog, no stash, no blame. A
`git clean`, an editor mishap or a stray `rm` ended it with no trace and no warning. The second
loss, between two turns of one session on 2026-08-06, cost an hour to rebuild.

The previous version of this section closed with the condition for changing that: *if this
matters enough to rebuild a third time, track it.* It was rebuilt once and the rebuild is worth
keeping, so it is tracked from 2026-08-07. Churn in the history is the price, and it is lower
than rebuilding from source again.

The sections below remain **reconstructed by reading the shipped source at `16fcdd7`**, not
recovered - tracking it now does not recover what was lost then. Two items survive verbatim
because they were quoted back in a brief: the Trips empty state (was "item 2.2") and the Import
heading (was "item 5.4"). **The original numbering is gone and the numbering here is new.**
Where a heading below says the audit "had" something, that is inference from those two items
and the source, not a copy.

---

## The three buckets

Every finding lands in exactly one. The bucket is about **what kind of wrong it is**, because
that decides who fixes it and how it is proved.

1. **UNTRUE** - the screen states something that is not so. A count that does not sum, a
   sentence that describes different code than the one that ran, a scope claim wider or
   narrower than the feature. These are `IMPLEMENTATION_STANDARDS.md` §9 defects and each one
   ends as a row there plus a browser test on the rendered words.
2. **UNFINDABLE** - the thing is right, complete, and reachable only by someone who already
   knows it exists. No test can assert this; it is a judgement about routes.
3. **MISLABELLED** - the thing is right and its name is not, or two different things share one
   name. Cheaper than (1) because nothing is false; worse than (3) sounds, because a wrong name
   survives every gate.

---

## 1. UNTRUE - fixed

| # | Surface | Was | Fixed in |
|---|---|---|---|
| 1.1 | Organize tally | Four rows that did not sum: `undated` counted over two of the rows above it, while `unreadable` sat in a banner | `ab0a76a` |
| 1.2 | Organize "Look inside" | Said "nothing to organize here" about a folder it could not open | `ab0a76a` |
| 1.3 | Organize duplicates | "2,057 duplicates" with no statement of *where* the twin is | `521101e` lineage |
| 1.4 | Move result | A move left files behind and said nothing; the cleanup offer then tidied around them | `521101e` |
| 1.5 | Organize preview | Offered to rearrange a drive holding none of the matched files - `matched_path` names where content was first read, never where it sits | `a16735b` |
| 1.6 | Trips empty state | "needs enough camera photos taken close together" - describes within-day clustering while naming a trip, and states no number while that number is a Settings field | `74c48e4` |
| 1.7 | Import heading | "Import from Google Photos" while `ingest` reads any folder or archive from any source | `74c48e4` |
| 1.8 | Import tally | kept / duplicates / dates-recovered / undated shown as one block under "N files found" - the last two counted over `kept`, and `unreadable` on no surface at all | `74c48e4` |
| 1.9 | Stats empty state | Its way-in button carried the same service-scoped label as 1.7 | `74c48e4` |

## 1b. UNTRUE - still open

| # | Surface | The problem | Status |
|---|---|---|---|
| 1b.1 | Organize tally, first row | Labelled "new - will be organized" while a near-duplicate is **also** organized, so the row names less than the run does. Buckets are correct and disjoint; only the label is wrong, and it can only be fixed together with the second row | **Filed as `(abl)`**, waiting for whichever screen commit reaches that tally |
| 1b.2 | Find, drive column | `find_copies_query` joins `drives` with no drive filter, so on a shared catalog the column names another machine's drives | **Filed as `(abd)`**; pinned by a record-only test |

---

## 2. UNFINDABLE

No test asserts any of these. They are judgements about routes, recorded so the judgement is
re-examinable rather than re-derived.

| # | Thing | Reachable only by |
|---|---|---|
| 2.1 | **Trips & events** | Opening the rail item. Nothing at the moment of intent points at it - Organize's completion card is where someone has just finished the thing that *makes* trips possible, and says nothing about them. |
| 2.2 | **Import** | Same shape. One way in exists from Stats' empty state, which is the screen a new user has least reason to open. |
| 2.3 | **Rearrange your library** | Settings only. **Improved twice**: named (`93635af`), pointed at from an Organize preview that is nearly all library (`93635af`), and moved directly under Folder layout (`16fcdd7`). Still has no rail item, and it is the answer to the most-asked question in this space. |
| 2.4 | **Dates you have corrected** | Settings only, below Rearrange. Someone wanting "write my corrected dates into the files" has no route but scrolling Settings, and the card name does not contain the verb. |
| 2.5 | **The live panel** | Windows ≥ ~1336px. Deliberate and guarded - nothing needed to finish a task may live there - so this is a note, not a defect. |

### 2b. Dead space on large monitors - CLOSED 2026-08-06 (`9c79a3e`)

Was listed here as "the layout wastes a wide screen". **Measured** via mutter's `GetCurrentState`
rather than assumed, because `xrandr` under XWayland reports scaled framebuffers and gives a
number no browser sees:

| output | panel | mode | scale | **CSS px** | dPR |
|---|---|---|---|---|---|
| eDP-1 | AUO laptop | 1920x1080 | 1.00 | **1920** | 1.00 |
| HDMI-1 | BenQ PD2720U (4K) | 3840x2160 | **1.25** | **3072** | 1.25 |
| DP-3 | DELL S2721DS (QHD) | 2560x1440 | 1.00 | **2560** | 1.00 |

The 4K panel is **3072 CSS px, not 3840** - "a 4K is ~1920 CSS px" holds only at scale 2.0. Both
external panels are wider in CSS px than the laptop, so the QHD and the UHD failed together.
Dead space each side at the old 1080 cap: **144px at 1920** (never the complaint), **464px at
2560**, **720px at 3072**.

Now: column ceiling **1600px** (defended by the widest real element - a Find row with a full
event-folder path, measured at ~1030px natural width), panel `clamp(320px, 20vw, 440px)` with its
floor unmoved so the 1336px threshold still means something, and the type scale fluid via
`clamp()` with **rem bounds** so the root still governs. **Fluid type stops at the rail** - `vw`
asks how wide the window is and the rail is 232px at every window size.

**Still open from that pass:** at 3072 with an *empty* library there is no panel, so the column is
~56% of the track. That is the honest worst case and also the case with least on screen.

**Considered and rejected:** `.metrics` on `auto-fit`. It reintroduces the 3+1 wrap an existing
guard prevents, and no minimum avoids it - there is always a width band where three of four fit,
and at any minimum that band lands inside the 1080-1700px range this app is used at, including a
rotated QHD at 1440.

**The pattern's own answer**, established on Backups and applicable to 2.1-2.4: put the remedy
on the screen where the person already is, rather than adding nav. Not built for any of these -
each would need its own commit on its own screen.

---

## 3. MISLABELLED

| # | Surface | The mismatch | Severity |
|---|---|---|---|
| 3.1 | Settings, two fields | **`#mig-path` and `#bake-path` are both labelled "Connected drive folder"** on one screen. Read in order, or announced by a screen reader, the two are indistinguishable | **Real.** Two controls, one name, one screen |
| 3.2 | Find | Field label "Search" and button "Search" - the label names the action rather than the input | Minor |
| 3.3 | Find / Stats | Rail says "Find" and "Stats"; the `<h1>`s say "Find a file" and "Library stats" | Cosmetic; the rail is width-constrained and the expansions are honest |
| 3.4 | Import field | `#rc-takeout` - the id keeps a vendor's name. **Correct and deliberate**: `takeout.py`, `scan_takeout` and the sidecar parsing are Google's own format, and SHIPPED (jj) says so explicitly to stop a future sweep "fixing" it | Not a defect - listed so it is not re-reported |

---

## 4. What changed under this document while it was gone

Most of what an older copy said is **stale rather than merely absent**. Since it was written:

- **Five screens went onto the shared pattern** - Organize (`ab0a76a`), Find (`d95ba7e`), Stats
  (`752fbd4`), Backups (`e8dec5c`), then Trips & events and Import together (`74c48e4`).
- **Settings did NOT**, and that is a finding rather than a gap (`16fcdd7`): the pattern's unit
  is a surface with one job, and Settings holds five cards with five. Its *components* are in
  use; its *lifecycle* is not. Two of its cards are themselves complete run flows.
- **The sidebar** became a dark rail with a collapse control on the boundary, a custody strip,
  and a real top bar below 720px.
- **The palette** replaced black-and-white with warm neutrals and indigo; amber and green are
  status-only. Measuring found a pre-existing AA failure (amber 2.94:1, green 3.42:1).
- **The type scale** became rem, so a raised browser default reaches the app; a text-size
  setting was then added on top of it as percentages of that default (`16fcdd7`).
- **The wordmark and icon set** collapsed to one mark, the pillar T.
- **The content column and the type scale** were sized against the maintainer's real monitors
  (`9c79a3e`): ceiling 1080 -> 1600, panel 320 -> fluid, type -> `clamp()` with rem bounds.

**A gap this document should carry, found while checking a "nothing happens" report:** the app is
a single page, and a tab left open across an upgrade keeps the old `index.html` and `app.js`
indefinitely. `_static_fingerprint` warns when the *server process* is older than the files on
disk; **nothing warns when the open BROWSER TAB is older than the server.** A new control simply
does not appear, and there is no route by which a user would know to reload. Not built.

Any statement in an older copy about screen chrome, colour, spacing or type predates all of
that and should be assumed wrong.

---

## 5. How each bucket gets proved

- **(1) UNTRUE** - a browser test on the **rendered words**, plus a service test where the
  payload is stubbed in the browser (a payload key can be correct while nothing reads it, and
  the reverse: a browser stub hides a server that stopped sending it). Then a §9 row.
- **(2) UNFINDABLE** - not testable. Recorded here and in the relevant commit message.
- **(3) MISLABELLED** - a source guard on the shipped string, keyed on the **shape** rather than
  the specific wording, so a reintroduction in different words fails the same way. See
  `SERVICE_SCOPED_IMPORT` in `test_user_facing_copy.py`.

**And the gate has a stylesheet-shaped hole.** `make check` reads no CSS, so a malformed comment
can delete a design token in silence. `ENGINEERING_STANDARD.md` §4, eleventh member.
