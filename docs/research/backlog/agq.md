# (agq) THE FIRST SCHEMA BUILD RUNS INSIDE A USER REQUEST.

*Body of entry `(agq)`. **CLOSED 2026-08-23, unbuilt - the work was already shipped in `b0a5d7e` on 2026-08-14, nine days before this was filed.** The index is now [`SHIPPED.md`](../../SHIPPED.md).*

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

## ⚠ Narrowed 2026-08-23, while building `(agp)` part 1

`create_app` already opens an **existing** catalog at construction (`server.py:153`,
`service.prepare_catalog` -> `inspect_catalog` -> `Catalog(...)`), so migrations of an existing
catalog run at boot today. **What runs in-request is the fresh-CREATE case only** - a missing
file is described (`WILL_CREATE`) and not opened, per `catalog_startup.py:242`'s deliberate
choice. This entry is about that remaining case, not about migration.

---

## ✅ CLOSED 2026-08-23 - already built, and the premise was false when filed

**`migrate_catalog` (`catalog_startup.py:332`) - *"Create and migrate `db` now, so nothing
serving requests has to... ⚠ This CREATES the file"* - runs at every app boot** via
`prepare_catalog` (`drives.py:700-707`) from `create_app` (`server.py:153`). It landed in
`b0a5d7e` (2026-08-14), whose commit message carries its own measurement (run `31821214510`:
7,828 opens reaching `_migrate`, waits to 2,832 ms) and its own answer to the reversal question
this entry asked: WILL_CREATE's honesty survives because presence is captured **before** the
create, fused into one function *"because two calls at a call site can be reordered by anyone
and nothing would say so."*

**How the false premise got filed, named because the mechanism matters more than the miss**: the
`(adt)` investigation read `inspect_catalog:242` - *"Does not create"*, which is **true** - and
stopped three functions short of `migrate_catalog:332`. The filer and the fixer were the same
person, nine days apart. Fifth instance of the fixed-under-another-name family; now
`ENGINEERING_STANDARD.md` §4's sixty-ninth member.

**What the design pass verified before closing** (P17):

- The field-failure cases were already guarded in live behaviour: unpreparable location reported,
  not raised (`(aen)`); unusable catalog refused **before** the socket bind (`__main__:309`,
  `(adr)`); zero-byte its own refused state.
- `(ady)`'s copy fires only `if version < CURRENT_SCHEMA_VERSION` (`catalog.py:1157`) - a fresh
  build stamps v21 first, so no chain, no copy. Unchanged by any of this.
- Measured on real ext4 NVMe: a fresh build is **1.0 ms median, 1.4 ms max** - the seconds only
  ever existed on contended 2-core CI I/O. There was no wait to move.
- The declaration-seam alternative was withdrawn by the maintainer: the catalog's location is
  app-owned and known at boot, so "create when the destination is known" conflated the library's
  seam with the catalog's.
- CLI divergence is real and benign: the CLI creates in-command, single-process, blocking nothing
  of its own; each surface's banner sentence is true for that surface. Timing, not capability -
  no parity row.

## ⚠ MEDIUM CORRECTION, 2026-08-23

"Measured on real ext4 NVMe: 1.0 ms median, 1.4 ms max" above ran on **tmpfs** (`/tmp`, the
ad-hoc scratchpad - P22's finding). Re-measured on real ext4 (`/data`): **4.6 ms median, 6.8 ms
max** over 20 fresh builds. **The conclusion stands exactly as stated** - milliseconds, not
seconds; there was never a wait to move - and the corrected number replaces a false label with a
measured one.
