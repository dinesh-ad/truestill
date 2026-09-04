# The Organize preview - what it established, and what it borrowed

**A record of a design spike, not a plan.** Written 2026-08-15 because the spike lives in
`.scratch/organize-preview/`, which is **gitignored** - so it exists on one disk with nothing in
the repository pointing at it. That is the same leak as a week-old stash and an unpushed branch,
one layer sideways: the first thing in this project that looked like a product survives only as
long as one folder does.

⚠ **THIS RECORD PRESERVES THE DECISIONS, NOT THE ARTEFACT.** Filing it does not commit the code.
The spike is 144 MB with `node_modules`; its `src/` is small and could be kept deliberately, and
that is a choice someone still has to make. If the folder is deleted before then, what is below is
what remains.

## What it establishes

Five things, and they are the reason it read as an application rather than as a page:

1. **Mode options as selectable cards** - copy / move / reorganize presented as choices you pick
   between, not radio buttons stacked in a fieldset. The option carries its own consequence.
2. **Hierarchy in the library panel** - the panel states one thing loudly and the rest quietly,
   instead of six items at one weight.
3. **Weighted buttons with exactly one primary** - a screen with one obvious next action, and
   everything else visibly secondary. The current screens give several buttons the same weight.
4. **A visible active state in the rail** - the current screen is legible at a glance rather than
   inferred.
5. **Content filling its space** - no 55-character paragraph inside a 1500px card. The same defect
   the Settings pass named as the single biggest reason the app reads as a broken web page.

**None of these needs the stack below.** They are layout and weight decisions, expressible in
`tokens.css` plus Tailwind utilities, and that is the point of recording them separately from the
tools the spike happened to reach for.

## What it uses that the real app does not

| in the spike | in `truestill-app` | note |
|---|---|---|
| `framer-motion` | **absent** | ~34 kB and animation the product has not asked for. `(ado)`-era rules already refuse marketing-page motion. |
| `lucide-react` | **absent, deliberately** | the eight nav icons are inlined SVG path data, licensed per icon in `static/LICENSE-icons.txt`; `components/ui/icons.tsx` inlines three more for shadcn. Installing it would reverse a recorded ruling. |
| no shadcn | **shadcn installed** | the app now has eight components aliasing `tokens.css`. The spike predates them. |
| its own theme ("rose/coral liquid-glass") | `tokens.css` | the spike's palette is **not** this product's. Its README calls it a "unified rose-theme shell". |

⚠ **These are decisions to make deliberately, not to inherit.** Porting a screen from the spike
would drag three of them in by copy-paste, and each one reverses something this repo has already
ruled on with evidence. **Take the five findings; leave the four dependencies.**

## Where it is

⚠ **Corrected 2026-09-02 (P192): four unused files, not two** - `src/AppShell.tsx` and
`src/OrganizePreview.tsx` are also dead iterations nothing imports. Verified against the folder on
disk, which is still 144 MB, still gitignored, and still imported by nothing. The original follows.

`.scratch/organize-preview/` - `src/TruestillApp.tsx` is the unified layout; `src/Sidebar.tsx` and
`src/OrganizePage.tsx` are earlier, unused iterations. It runs standalone on `127.0.0.1:8766` and
is not wired into `truestill-app` in any way.

> ⚠ **The choice this record left open was made 2026-09-04 (P215): the live source is now
> COMMITTED, at [`research/organize-preview/`](research/organize-preview/).** This record's own
> words were *"its `src/` is small and could be kept deliberately, and that is a choice someone
> still has to make. If the folder is deleted before then, what is below is what remains."* Three
> files are kept - `TruestillApp.tsx`, `main.tsx`, `index.css` - and **the four dead iterations
> are not**, on this record's own finding that nothing imports them. The gitignored folder is
> still the only place the spike *runs*; what is committed is the direction, not a build.
