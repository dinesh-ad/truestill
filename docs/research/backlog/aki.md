# (aki) THE THREE REGIONS LEFT AROUND `#org-result` ARE ALL HELD BY SHARED MACHINERY

**Filed 2026-09-06 (P249). No work attempted, and the slice was refused rather than half-built.**

The React arc has taken `#org-result` in three slices - the inventory card, the dedup preview, the
completion card. The next slice was scoped as the typed confirm, the undo panel and the progress
block. **All three are blocked by the same thing**, and it is not difficulty: each is built from a
helper that six other screens use, so porting any of them either drags those screens into an
island scoped to Organize or leaves one DOM node with two owners.

## The census, which is the whole finding

| region | held by | call sites | screens |
|---|---|---|---|
| the progress card | `<template id="tpl-run">`, cloned by `mountRunBlocks` | **8 mounts** | org, ev, rc, verify, bk, mig, bake, undo |
| the typed confirm | `typedConfirm` | **6 callers** | Organize ×3, Trips/Settings undo, Settings migrate, Bake |
| both, plus the undo panel | `startRefusedCard` | **11 uses** | 8 distinct target fields across 6 screens |
| every card | `card()` | 54 | ten result regions across six screens |

`mountRunBlocks` clones the template into every `[data-run]` mount and stamps `<prefix>-<part>`
ids, which is the contract `createProgress(prefix)` reads - and `createProgress` is instantiated
eight times. **The progress block is the most shared thing on the page.**

`typedConfirm` is the typed-word widget. Organize uses it for the run confirm, the clean-empty
offer and the undo apply; `renderMigrateTypedConfirm` and `bakeDriveLines` use it on Settings and
Bake, and `startUndoPreview` uses it for the Trips and Settings undo panels.

## Why a partial move was refused

The tempting shape is React rendering the banner and leaving a host element for `app.js` to mount
`typedConfirm` into. **That is one node with two owners, and this arc has already paid for that
once**: the completion card's folder chips were built by asking the island for markup from inside
its own render, came back empty, and nobody noticed for a day because the only symptom was a block
that was not there. `toHtml` now throws on that specific shape, but the general hazard - React
reconciling a subtree that imperative code also writes - has no guard and would not be caught by
any assertion this suite makes.

The same reasoning is already recorded for `card()` in `frontend/src/main.tsx`'s opening comment:
*"Porting it would drag six unrelated screens into an island scoped to one region."* That was right
about `card()` and it is right about these three.

## What would unblock it, stated as options rather than a plan

1. **Convert by SHARED WIDGET rather than by region.** Port `typedConfirm`, `startRefusedCard` and
   the run block to components, each with every one of its callers, as their own slices. That is
   the honest order and it is larger than a screen.
2. **Convert the remaining screens first**, so that when Organize's neighbours move there is no
   caller left outside the island. This inverts `react-migration-plan.md:143`'s ruling that
   Organize goes first, which was argued from Organize being the only screen with a design.
3. **Accept a two-owner node for one region, deliberately and with a guard written first.** No
   guard for it exists and none is obvious; nothing in this repo can currently assert "React did
   not reconcile away something imperative code wrote".

⚠ **None of these is recommended here.** The point of this entry is that the next slice is a
DIFFERENT SHAPE from the last three, and choosing which shape is a ruling rather than an
implementation detail.

## What is still true and unblocked

The form remains last for the reason already recorded: `app.js` binds `#org-preview`,
`#org-dedup`, the mode radios and the library-root save at parse time, and it loads before the
module bundle, so a React form does not exist when those lines run. That is unchanged by this
entry and is not what blocks the three regions above.
