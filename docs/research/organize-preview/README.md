# The Organize preview's source, kept

**The design spike's live source, committed 2026-09-04 (P215) so the direction survives the
folder.** `docs/organize-preview-record.md` is the record of what it established and why; this is
the artefact that record was written to outlive, and it said so: *"The spike is 144 MB with
`node_modules`; its `src/` is small and could be kept deliberately, and that is a choice someone
still has to make. If the folder is deleted before then, what is below is what remains."*

**It is reference, not code.** Nothing imports it, nothing builds it, and it is not in any
package. It does not compile here and is not meant to: it depends on `framer-motion` and
`lucide-react`, both of which this project refuses by ruling (`docs/agent-tooling.md`,
`DECISIONS.md` D12).

## What is here, and what deliberately is not

| file | why |
|---|---|
| `TruestillApp.tsx` | the unified layout - the direction itself |
| `main.tsx` | its entry, four lines, kept so the tree is readable |
| `index.css` | the Tailwind entry and the rail scrollbar treatment |

⚠ **The four dead iterations are NOT kept** - `AppShell.tsx`, `OrganizePreview.tsx`,
`Sidebar.tsx`, `OrganizePage.tsx`. `organize-preview-record.md` already records them as
*"dead iterations nothing imports"* (corrected 2026-09-02, P192), and `main.tsx` imports only
`TruestillApp`. Preserving superseded drafts beside the thing that superseded them is how a
reference becomes debris.

## What to take from it, and what to leave

The record's five findings are the answer, and its own warning is the important half: *"Take the
five findings; leave the four dependencies."* Two further constraints were added by P214/P215:

- ⚠ **Its palette is not this product's.** The README calls it *"rose/coral"*; the app's accent is
  `#4c63c4` and *"rose"* appears nowhere in `static/`. Porting the colour installs a second palette.
- ⚠ **Its surface treatment is refused.** *"liquid-glass"* is decoration, and the target recorded
  in `react-migration-plan.md` is **trustworthy, not friendly** - no glass, no motion, no
  illustration. **Take the structure: dark rail, light canvas, layered active state, the spacing
  rhythm. Leave the surface.**
