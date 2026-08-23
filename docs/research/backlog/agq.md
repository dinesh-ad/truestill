# (agq) THE FIRST SCHEMA BUILD RUNS INSIDE A USER REQUEST.

*Body of entry `(agq)`. **OPEN.** The index is [`BACKLOG.md`](../../BACKLOG.md); the provenance index is [`SHIPPED.md`](../../SHIPPED.md). Split out of `(adt)` when it closed, 2026-08-23; ranked below `(agp)`.*

## The defect

A fresh catalog is built by whichever request happens to open `Catalog` first
(`catalog.py:1111`: `BEGIN IMMEDIATE`, the full `_SCHEMA_STATEMENTS`, one commit). Measured in
`(adt)`'s M4 census: up to **5091.2 ms** on a contended 2-core runner, against **9.0 ms** max for
all 32,119 ordinary commits. Any concurrent catalog user during that window waits up to the 5 s
`busy_timeout` or is refused with `(agp)`'s message.

**In production the window opens exactly once per catalog - at the user's first ever action.**

## The structural fix, and what it reverses

Open the catalog once at **boot**, before the first request can, so the build happens off the
request path. This also disarms `(agp)` for most users, because the commonest cause of the busy
message stops being reachable.

⚠ **THIS REVERSES A DELIBERATE CHOICE, AND THE BUILDING COMMIT MUST SAY WHY THE CHOICE WAS MADE
AND WHY IT NO LONGER HOLDS - never quietly flip it.** `inspect_catalog` does not create a missing
catalog at startup (`catalog_startup.py:242`: *"Does **not** create a missing catalog (`Catalog`
would)"*), and its docstring context records why: startup describes the catalog **before** opening
it, so a missing file reads as *"No catalog yet. Truestill will create catalog file ... on first
use"* rather than as a failure - and `(adm)`/`(aen)` built reporting on top of that order. A
boot-time open must preserve that reporting order (describe first, then create), not trade it
away.

## Constraints for whoever builds it

- The build must stay **off the request path** for the CLI too, or the fix is app-only and the
  parity table gains a row (`cli-app-parity.md`'s completeness test will not see this by itself).
- The two-openers race is already safe (`catalog.py:1085-1128`, forced in
  `test_two_openers_build_the_schema_once`) - a boot-time open adds a third opener class, not a
  new race.
- `(ady)`'s pre-upgrade copy fires on *migration*, not on a fresh build - verify the boot-time
  open does not change when that copy is taken.
