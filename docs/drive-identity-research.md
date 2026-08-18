# Drive Identity, Offline Catalog & Verify - research & plan (Phase 1)

Reconnaissance (code truth) + community research (practitioner truth) for BACKLOG item (e).
Ends with recommended scope answers and an implementation plan. **No code yet** - this
document is the review gate.

> **Historical note.** This document predates the `vaeon` → `truestill` rename and refers to
> the marker as `.vaeon-drive.json` throughout. The marker written today is
> `.truestill-drive.json`; the old name is still read for drives initialised before the
> rename. The binding rules are `IMPLEMENTATION_STANDARDS.md` §3.1 - the design reasoning
> below is unchanged.

> ⚠ **AMENDED 2026-08-18: ONE PROPOSAL BELOW READS AS BUILT AND IS PART-BUILT.** The record is
> **not edited** - a record rewritten to stay correct stops being one - so the status is stated
> here instead, next to the header a reader meets first.
>
> **§B3's clone proposal has three parts** (*"treat same-uuid as the same logical drive; **warn**
> when one uuid is seen at two distinct mount paths in a single run; `drives init --relabel` mints
> a fresh uuid for a diverged clone"*). Two shipped; one did not, and the prose gives no way to
> tell them apart:
>
> | part | status |
> |---|---|
> | same-uuid is one logical drive | ✅ built |
> | a fresh uuid for a diverged clone | ✅ built, as `--force-new-identity` |
> | **warn when one uuid is seen at two distinct paths** | ⚠ **registration only** (`cli.py:893-918`); **`verify` has no such check** |
>
> Traced 2026-08-18: a cloned tree verifies clean, silently moves the remembered path to the
> clone, and leaves one `drives` row - so custody reports one copy where two exist. **The ruling
> that clones share identity until they diverge is unaffected and stands**; what is missing is the
> disclosure the same paragraph specified. Carried as `BACKLOG.md` `(adx)`.

---

## Part A - Reconnaissance (code truth, file:line)

### A1. The catalog has no destination/drive identity, and is one-row-per-content
`catalog.py` `files` table stores `relative` (a POSIX path *within* a destination) and
`source_path` (the **source**, not the destination). There is **no** column identifying which
destination/drive a copy went to. Worse for this feature: `files.sha256` is `NOT NULL UNIQUE`
and `record_uploaded` does `ON CONFLICT(sha256) DO UPDATE` - so the catalog holds **exactly one
row per unique content**. Copying the same photo to two drives collapses to one row; the second
write **overwrites** `relative`/`copy_sha256` with the second drive's.

> **Consequence (the load-bearing finding):** the schema cannot currently represent "this
> content lives on drive A *and* drive B." `where` (which drives) and `status` (single-copy
> detection) are impossible without a new **per-(content, drive) location table**. A `drives`
> table alone is not enough.

### A2. `copy_sha256` - where it is written, where it is NULL
`organizer.execute` sets `copy_sha256` for **every** row it writes: `copy_sha = source_sha` for
the byte-identical normal path (`organizer.py` ~line 391), or the post-write hash for Takeout
(`_upload_with_metadata_write`, ~line 322). The metadata-write path arrived **with** schema v5.
Therefore:

- Rows written by current (v5) code always have `copy_sha256`.
- `copy_sha256` is NULL **only** for rows inserted by pre-v5 code and then migrated. Every such
  copy was byte-identical (no metadata writes existed before v5), so its `sha256` (source hash)
  equals the on-disk bytes.

> **Proposed NULL policy for verify:** compare the on-disk hash against `copy_sha256` when
> present, else fall back to `sha256`. Safe by construction - NULL implies byte-identical.

### A3. "A drive" - LocalDestination vs RcloneDestination
- `LocalDestination(root: Path)` → `describe()` = `local:{root}` (`destinations/local.py`). A
  local directory = a mounted drive. A marker file at `root` and verify-by-rehash are natural.
- `RcloneDestination(remote)` → `describe()` = the remote spec, e.g. `remote:Photos/Backup`
  (`destinations/rclone.py`). An always-online cloud remote - not a drive in a drawer.

> **Scope proposal:** v1 drive-identity = **LocalDestination only** (the validated "unplugged in
> a drawer" pain). rclone remotes are a different model (always online; verify would use
> `rclone hashsum`); note as future, do not build now.

---

## Part B - Community research (practitioner truth)

Sources at the bottom. Priority order honoured: tool trackers + practitioner threads.

### B1. The micro-market is real, and catalog-only
[catcli](https://github.com/deadc0de6/catcli) indexes external media into a catalog, searches
and navigates it **while the media is disconnected**, and stores size + md5. JSON catalog,
git-versionable. It validates the demand - and the gap: **none of these do
organize + dedup + backup + verification in one tool.** truestill already has the first three.

### B2. Drive identity: filesystem UUID is the wrong primary key
- Identity mechanisms are **OS/filesystem-inconsistent**: Linux/macOS expose a UUID; Windows/NTFS
  uses a **64-bit volume serial** (half a UUID); FAT uses a **32-bit** serial - small enough to
  collide. Reformatting changes it.
- **The cloned-drive problem (repeatedly cited):** cloning a disk copies its UUID/serial, so two
  physical drives share one identity and "create confusion in the database if you use both."
- Mount points and drive letters change per session/OS (the reason identity must not be the path).

> **Recommendation:** identity = a **marker file with our own `uuid4`** (`.vaeon-drive.json`),
> not the filesystem UUID. It is OS/FS-independent, collision-free, survives remount, and travels
> with the data. This matches the feature spec's instinct and the research.

### B3. Marker-file edge cases users actually hit
- **Cleanup tools delete dotfiles.** A missing marker must not silently create a "new unknown
  drive." Proposed: `verify`/`where` refuse to guess; `truestill drives init --uuid <known>` re-attaches
  a known identity (content-hash match can suggest which drive it was).
- **Cloning copies the marker too** → duplicate `uuid4`. Fundamentally, clones are identical at
  clone time, so sharing identity is *correct* until they diverge. Proposed: treat same-uuid as the
  same logical drive; **warn** when one uuid is seen at two distinct mount paths in a single run;
  `truestill drives init --relabel` mints a fresh uuid for a diverged clone. Do not auto-disambiguate -
  surface it, let the human decide.
- **Verify UX praised vs cursed:** progress on huge drives, resumability, and honest reports are
  what users want; a silent multi-hour hash with no output is what they curse. Proposed: worker-pool
  hashing (reuse `scan.compute_hashes`), stream one pass, a progress line, per-copy `last_verified`
  so re-runs can skip/`--since`, and a verified / MISSING / MISMATCH report listing the mismatches.

---

## Part C - Recommended scope answers (for your approval)

1. **Identity = marker file (`.vaeon-drive.json`: `uuid` (uuid4), `label`, `created`)**, never the
   mount path; filesystem UUID explicitly rejected as primary key (B2).
2. **v1 = LocalDestination only.** rclone remotes deferred (A3).
3. **New schema (v6):** a `drives` table **and** a new **`file_copies`** location table
   (per-content-per-drive) - the latter is required, not optional (A1).
4. **Verify NULL policy:** compare vs `copy_sha256`, else `sha256` (A2).
5. **Cloned/missing-marker policy:** warn + manual re-init/relabel; never auto-guess (B3).

---

## Part D - Implementation plan (Phase 2, on approval)

- **`truestill-core/drive.py`** (pure): read/write/validate `.vaeon-drive.json`; mint `uuid4`; the
  marker dataclass. No mount-path logic in identity.
- **Catalog v6** via the migration framework + migration test:
  - `drives(uuid PK, label, first_seen, last_seen, last_verified, notes)`.
  - `file_copies(sha256, drive_uuid, relative, copy_sha256, size, last_verified, status,
    PRIMARY KEY(sha256, drive_uuid))` - authoritative per-drive locations; `files` stays the
    content identity/dedup/date/category record.
  - `record_uploaded` also upserts a `file_copies` row; the CLI resolves the destination's drive
    uuid (from its marker) and passes it in. `files.relative/copy_sha256` retained as "latest copy"
    for back-compat.
- **`truestill drives`** - list known drives (uuid, label, counts, sizes, last_seen/verified). `init`
  subcommand to create/re-attach a marker.
- **`truestill where <term>`** - offline catalog query → drive label(s), path(s), last-verified.
- **`truestill verify <label>`** - connected drive; worker-pool re-hash of truestill-managed files vs
  `file_copies.copy_sha256` (else `sha256`); report verified/MISSING/MISMATCH; **read-only** (never
  repairs without an explicit re-copy). Resumable via `last_verified`.
- **`truestill status`** - content with a single `file_copies` row → "at risk: N single-copy files"
  (the 3-2-1 nudge, stated once).
- **Capability seam:** Pro-tier candidate (convention). Pure logic in core; thin subcommands in cli.
- **Tests:** two tmp "drives" + markers; corrupt one file + delete another on drive B → verify
  reports exactly those; `where` answers with drives unmounted/renamed; duplicate-marker (clone)
  behaviour per approved policy; v5→v6 migration test; re-run idempotency; `.as_posix()`-safe
  assertions; dry-run report first. `make check` green.

---

## Sources
- catcli - offline catalog tool & feature set: <https://github.com/deadc0de6/catcli>
- Cloned-drive duplicate serial/UUID confusion: Tom's Hardware
  <https://forums.tomshardware.com/threads/exact-disk-clone.2535798/>; Linux Mint forums
  <https://forums.linuxmint.com/viewtopic.php?t=143560>
- UUID vs NTFS/FAT volume serial sizes & OS differences: cyberciti
  <https://www.cyberciti.biz/faq/linux-finding-using-uuids-to-update-fstab/>;
  thelinuxvault <https://www.thelinuxvault.net/blog/how-to-retrieve-and-change-partition-s-uuid-universally-unique-identifier-on-linux/>
- Catalog showing wrong location after drive change (path-as-identity failure): Adobe community
  <https://community.adobe.com/questions-716/new-catalog-showing-wrong-photo-location-after-hard-drive-upgrade-1206414>
