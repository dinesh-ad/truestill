# (aba) Nothing reconciles the catalog's recorded location with where a file actually is.

*Body of backlog entry `(aba)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aba) Nothing reconciles the catalog's recorded location with where a file actually is.**
  Found 2026-08-03 by tracing what happens when a user tidies by hand - the maintainer moved a
  file out of `Saved/` into its trip folder after an organize. **Three symptoms, one root
  cause**, filed together because they share it and would otherwise be fixed three times; each
  is separately actionable and separately ranked below.
  - **The good news first, so nobody "fixes" it into a regression.** With the catalog that
    recorded the run, **no organize path undoes a hand-move**. `DedupIndex.from_catalog_rows`
    seeds from `(source_path, sha256, perceptual)` - **content, not location** - so a re-run
    matches the unchanged source and `execute` skips it before any write path:
    `if resolution.exact_duplicate is not None: ... continue`. The destination is never
    examined. Confirmed on a real 2,109-file re-preview: 2,108 exact duplicates.
  - ✅ **SYMPTOM 1 SHIPPED 2026-09-01 (P184).** `verify.CopyStatus.MOVED`, decided by
    `verify._locate_moved`: on a miss the drive is walked once, candidates are narrowed by
    recorded byte size and settled by SHA-256, and the two claims get one wording home in
    `verify.VERIFY_WORDING`. **The cost is charged only to the run that is about to claim a
    loss** - a clean verify still never walks, which `test_a_clean_verify_never_walks_the_drive`
    pins. Measured on a real 109,431-file library: the walk is **1.73 s at 63,000 files/s**, and
    the size index bounds the hashing at a **median of 10 candidates** per miss.
    ⚠ **The harm was wider than this entry said**: `MISSING` drives `mark_copy_missing` at both
    surfaces, so the false alarm also wrote `missing_at`, which `single_copy_shas` and
    `custody_floor` read - the library reported itself less redundant than it was. That is fixed
    with it and is pinned separately at the CLI.
    ⚠ **The app screen changed** (`app.js` renders a *"moved, not lost"* tally) **and the browser
    lane was NOT run** - this session was instructed not to. It needs one before the next release.
    **Symptoms 2 and 3 below are untouched, so this entry stays open.**

  - **SYMPTOM 1 - `verify` reports a hand-moved file as MISSING. A real defect, and the one to
    fix.** It re-hashes each recorded copy, finds nothing at `files.relative`, and returns
    `CopyStatus.MISSING` - *"the file is gone from the drive"* - while being entirely blind to
    the same bytes sitting safely at the new path. **This is the worst possible place for a
    false alarm**: `verify` is the feature whose whole value is being trustworthy, and a user
    who tidies one folder and is then told twelve files are missing learns to ignore the report
    - including the run where something really is gone. The likely fix is cheap: on a miss,
    look for the content elsewhere on the drive before saying "gone", and distinguish *"not at
    the recorded path"* from *"not on this drive"*. **Do not simply reword it** - a file that
    genuinely vanished must still be loud.
  - **SYMPTOM 2 - `--in-place` on a FRESH catalog silently reverts the move.** Narrow, but it
    is literally "Truestill undid my tidying". `_already_at_target` is the only thing that
    would move a file back, and it sits *downstream* of the duplicate skip, so a live catalog
    never reaches it - its own docstring says so: *"With a live catalog dedup catches this
    first; on a fresh catalog this is the only thing that does."* With a different `--db`, a
    lost catalog or a re-clone, dedup is empty, the check compares the file's current path
    against the **rule-derived** target, finds they differ, and moves it back. Journalled, so
    `undo-organize` reverses it - but silent at the time.
  - **SYMPTOM 3 - a changed-layout migration halts on a path that no longer exists.**
    `plan_migration` plans from the catalog, so it computes `old -> new` from the recorded
    `relative`. With the layout unchanged the file falls into `plan.unchanged` and nothing
    happens; with the layout changed it plans the move, `relocate` finds `old` absent and
    raises `cannot relocate missing copy: <old>`, **halting the whole migration**. Loud, which
    is right, but it names a path and not the cause - a user who tidied three weeks ago cannot
    connect the two.
  - **`ALREADY_PLACED` never covered this**, checked rather than assumed: set in exactly one
    place, gated on `relocation is not None` (in-place only), and it asks
    `(dest_root / computed_relative).samefile(source)` - *"is this file where the rules say"*.
    A hand-moved file is by definition not, so it reads as "needs moving". It recognises a file
    **Truestill** placed, never one the user did.
  - **Why one entry and not three, stated because three were asked for.** The three share one
    cause - a recorded location that nothing ever re-checks - and the fix for symptom 1 (find
    the content elsewhere before declaring it gone) is most of the fix for the other two. Three
    entries would fragment one design question and invite three partial repairs. All three are
    named, ranked and separately actionable above.

## The drive-identity sibling - `(agr)` part 3 closed into here, 2026-08-23

Two drive identities at one path - the phantom `attach_drive` used to mint at an unplugged
drive's recorded path - is this entry's family of harm carried by different evidence: **drive
rows and marker uuids** where the symptoms above are file rows and content hashes. Ruled
**NO BUILD**, and the argument that survives users arriving is the cry-wolf one, not the
population:

- **The signature is inexact by construction.** Two `path_hint.drive.*` values equal with a
  marker present for one identity is byte-identical to a legitimate re-registration at a reused
  mountpoint: the old drive's hint is deliberately kept (`drives.py:list_drives` - it is what lets an
  absent drive read OFFLINE rather than UNKNOWN), and `--force-new-identity` records nothing
  (`cli.py:_print_adoption_refusal` skips the check and mints). Since `(agr)` part 1 shut the silent mint, every
  future occurrence of the signature is an explicit human ruling - **a detector built now would
  fire only on people who followed our own instruction.**
- **Population zero, measured 2026-08-23**: eleven catalogs censused - both live catalogs,
  seven soak/scratch, the fenced mounts pruned not walked - and only the manufactured specimen
  carries the signature. No release, no tag: no other machine has run the minting code.
- ⚠ **This ruling is conditional on `(agr)` part 1 holding** (`_refuse_ghost_before_minting`,
  `drives.py:_refuse_ghost_before_minting`). If that guard is ever removed or bypassed, the population argument and the
  cry-wolf argument both die, and this ruling dies with them.
- **Detection's would-be home, named and deliberately not built**: the converse of `(adx)`'s
  `second_location_note` - one identity at two paths, mirrored to two identities at one path -
  at the same call site, `service/verify.py:verify_run.target`, before the two writes that destroy the evidence. Zero
  new mechanism if it is ever justified.
- **The remedies, named not designed.** (1) Report only - the honest floor: the shadowed files
  are on THIS computer's disk, unmount to see them. (2) Merge the phantom's copies into the
  real identity - ⚠ **the one an anxious user would want and must not be offered**: the bytes
  are NOT on the real drive, so it asserts custody of bytes the drive does not hold, the exact
  overcount `drive-identity-research.md` refused. (3) Delete the phantom row - destroys the only
  record that the shadowed files exist. (4) Rescue and re-point - unmount, move the shadowed
  files somewhere visible, verify by hash. (1) and (4) are the honest pair.

**The specimen**: `/data/TruestillLibrary/abs-repro-2026-08-23` - 244 KB, **all durable,
nothing regenerates**. Copied off session tmpfs on 2026-08-23; the original would not have
survived a reboot. `c.sqlite` is the evidence: two drive rows whose hints both name `lib/`, the
marker there answering as the phantom while the real drive's marker sits in
`lib-actually-unplugged/`. The hint values name the tmpfs path it was built at - a record, not
an error. `c.cache.sqlite`, `last-run.json` and `runs/` are the run's ordinary residue, kept
because 244 KB is cheaper than a wrong deletion.
