# (agr) THE APP'S FOURTH MINT SITE HAS NO GHOST CHECK, AND BACKUP REACHES IT.

*Body of entry `(agr)`. **OPEN - designed, not built; the refusal shape is RULED.** The index is [`BACKLOG.md`](../../BACKLOG.md). Filed 2026-08-23 from the `(abs)` verification sweep; **ranked at the top of the engine list by the maintainer.***

## Part 1 - the data-loss door (the rank-carrying part)

`attach_drive` (`drives.py:242`) mints a marker at `drives.py:345` with **no ghost check**, and
`backup_run` calls it `write=True` on **both user-supplied paths** (`backup.py:633-634`). Its only
gate, `_adoption_block`, is content-based - and `ghost_drive_at`'s own docstring names that guard
as blind to exactly this case: *"it recognises a folder that HOLDS a known library, and this one
holds nothing"* (`drive.py:609-611`).

**Demonstrated on scratch (`abs-repro`, kept as evidence), not described**: at the recorded path
of an unplugged drive, `attach_drive(ghost, db, write=True)` returned `registered=True`,
`blocked_by=None`, and minted uuid `51beda0d...` - the catalog then held the real drive
**offline** and a phantom **connected**, on the local disk, at the real drive's own path.

**The person and the moment**: a user whose backup drive failed to mount runs *"Copy your library
to another drive"* at its usual path. The copy succeeds onto their own disk under a second
identity, and the files are **shadowed the moment the real drive remounts - invisible while still
consuming space** (`ghost_drive_refusal`'s third fact). They learn it when the disk fills, or
never. This is `(aap)`'s data-loss door, app-side - the door `(afc)` closed on the CLI.

## The census that found it - four mint sites, three guarded

| mint | guard | escape |
|---|---|---|
| `cli.py:1197` (`drives --init`) | `ghost_drive_at` at `cli.py:1170-1174` | `--force-new-identity` |
| `cli.py:2570` (CLI organize) | `_approve_registration` -> `_registered_or_refused`, exit 4 | same flag |
| `organize.py:1109` (app organize) | `_approve_registration` (`organize.py:1015`, raises `DriveGhostError`) | recorded in `(abs)` |
| **`drives.py:345` (`attach_drive`)** | **none** | - |

`attach_drive`'s only `write=True` caller is `backup_run`; the CLI, migrate and bake never import
it (checked). `(abs)` counted *"the two places that MINT an identity"* - the sixty-ninth member's
own shape, self-applied: the entry that documented the guard was a partial read of the mint list.

## ✅ THE RULED DESIGN - refuse the run, never a soft-fail

Maintainer's ruling, verified here: *a second soft-fail beside a failed one is not a guard* -
`_adoption_block` already soft-fails and is structurally blind to this. The three read-only
surfaces refuse at the door; a write path minting a phantom identity must be at least as strict.

- **Q112 - the seam.** The guard is ONE implementation in core (`ghost_drive_at` +
  `ghost_drive_refusal` + `DriveGhostError`, all `drive.py`); the three guarded sites are
  *callers* with an identical three-line shape. The check goes **inside `attach_drive`, before
  `create_marker` at `drives.py:345`** - guarding the mint itself, so any future caller of
  `attach_drive` inherits it. A fourth caller of one core function, not a third implementation.
- **Q113 - how the refusal reaches the user.** `DriveGhostError`'s own docstring is the answer:
  *"One type in core rather than one per surface, so `jobs.py` reports the same `code` the CLI
  exits on"* - raise it in the job target and `jobs.py:350` ships `message=str(exc)`,
  `code="DriveGhostError"` to the browser verbatim. **Zero new mechanism.** `(agp)`'s app-level
  handler does NOT fit and must not be stretched: it lives in the HTTP exception path, and
  `backup_run` raises inside a worker thread that never crosses the ASGI layer.
- **Q114 - both paths.** With the guard in the mint, a run whose SECOND path is the ghost refuses
  after the first path attached - and that partial effect is harmless: attaching a legitimate
  source is idempotent, marker-reusing work the run needed anyway. The user sees the ghost
  refusal naming the offending path. Both-paths-ghost costs two round trips; accepted, rare
  (both drives unplugged), and preferable to a second check site in `backup_run` - callers
  knowing the rule is exactly what `(abs)` warned about.
- **Q117 - the regression test must fail today by MINTING.** Assert `read_marker(ghost) is None`
  **after** the attempt - never merely that a refusal was returned, because a refusal that still
  writes the marker passes the weaker assertion. Cry-wolf halves: a guard that refuses a
  *legitimate* new folder (no recorded hint - must still register), and one that refuses the
  reattach of the REAL drive at its own path (marker present - `ghost_drive_at` never fires on a
  marked path, pinned).

## Part 2 - the forbidden sentence (wording, lower rank)

`verify_run`'s soft-fail at a ghost path says *"...or register this drive first"* with
`can_register: true` (`service/verify.py:80` area) - the one suggestion `(afc)` forbade, at the
one path where following it mints the phantom. `can_register` is consumed by **nothing** in
`app.js` (zero hits) - advice text, not a button - which is why this ranks below part 1. The fix
is the ghost-aware sentence, not new detection: the payload already soft-fails; it should say the
`ghost_drive_refusal` facts when `ghost_drive_at` answers.

## Part 3 - the phantom already minted (reported, NOT designed here)

Nothing detects or repairs a catalog that already holds the pair. `_say_if_two_places`
(`cli.py`) detects the inverse - **one identity at two paths** (`(adx)`) - and nothing scans for
**two identities whose recorded hints name one path**. Worse, the phantom self-heals its own
appearance: at the ghost path the phantom's marker answers, so the phantom reads *connected and
healthy* while the real drive reads *offline* forever. `abs-repro` holds a live specimen.
Repair is `(aba)`'s reconciliation territory and is deliberately not designed in this entry.
