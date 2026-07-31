# Organize preview performance profile (backlog ss)

**Status: Research / measurement only (2026-07-29). No product behaviour changed.**
Raw JSON from the runs lives in [`docs/profile-runs/`](profile-runs/).

**Corpus fence (2026-07-30):** these numbers were taken on
`Crypto Folder/Photos/Vintage/.../Wayanad '14`, which is now **OFF LIMITS** (see
`PROJECT_STATUS.md` §4). Do **not** re-run this script against that tree. Keep the
figures as a historical FUSE cold-preview record; any new before/after must use an
allowed target (relocated Memory Cabinet, Output, or `<cloud mount>/2015` -
see `PROJECT_STATUS.md` §4).

This answers the open question in `BACKLOG.md` **(ss)**: which of {stat, exiftool,
hash-worthy reads} actually dominates on a cloud FUSE folder, and what the
local-vs-FUSE delta is. It does **not** propose a fix.

---

## 1. What was measured

| | |
|---|---|
| **Corpus (historical, OFF LIMITS to re-run)** | Wayanad '14 - **2,064 media** (2,061 images, 3 videos), 0 documents / unrecognized |
| **Cloud (FUSE) path used 2026-07-29** | `<cloud FUSE>/Crypto Folder/Photos/Vintage/2014/Wayanad '14` - **do not re-profile** |
| **Local (ext4) twin used 2026-07-29** | `<local ext4>/TruestillLibrary/Input/2014/Wayanad '14` (byte-same library copy) |
| **Pipeline** | Same call sequence as `service.organize_preview` (walk → `read_metadata` → plan/index → `compute_hashes` → dedup classify → summarize) |
| **Catalog / cache** | **Cold** throwaway temp dir each run (empty `catalog.sqlite` + empty hash cache) - matches the first-preview cost (ss) recorded |
| **Host** | AMD Ryzen 7 4800H (16 threads), Linux, Python 3.13, exiftool present, default thread pool (`os.cpu_count()` workers) |
| **Method** | `scripts/profile_organize_preview.py` - wraps `Path.open`, `PIL.Image.open`, `sha256_file`, `perceptual_hash`, `_sizes`; times each phase. Complexity: **O(n)** files, same as preview |

Size pre-filter was live: **22 / 2,064 files** needed SHA-256 (**1.07%**); **2,042** unique-size skips. That path is already optimized; it is not the bottleneck.

---

## 2. Wall clock - local vs FUSE

| | Local ext4 | cloud FUSE | FUSE / local |
|---|---:|---:|---:|
| **Total wall** | **23.94 s** | **312.74 s** (~5.2 min) | **13.1×** |
| **files/sec** | 86.2 | 6.6 | - |
| Prior soak note (ss) | - | ~9.9 files/sec, ~8 min | same order of magnitude; cold throwaway catalog here |

Accounted phase sum matched wall within rounding (no hidden multi-minute gap).

---

## 3. Per-phase totals and per-file averages

Phases that compose the sequential wall (shares sum to ~100% of wall):

| Phase | Local s | Local ms/file | Local %wall | Cloud s | Cloud ms/file | Cloud %wall | FUSE/local |
|---|---:|---:|---:|---:|---:|---:|---:|
| **read_metadata (exiftool)** | **14.52** | **7.03** | **60.6%** | **230.73** | **111.79** | **73.8%** | **15.9×** |
| **compute_hashes (wall)** | **8.55** | **4.14** | **35.7%** | **80.68** | **39.09** | **25.8%** | **9.4×** |
| walk (`scan_source`) | 0.048 | 0.023 | 0.2% | 0.499 | 0.242 | 0.16% | 10.4× |
| catalog + plan + index | 0.118 | 0.057 | 0.5% | 0.129 | 0.062 | 0.04% | ~1× |
| dedup classify | 0.683 | 0.331 | 2.9% | 0.683 | 0.331 | 0.22% | ~1× |
| summarize | 0.014 | 0.007 | 0.06% | 0.012 | 0.006 | <0.01% | ~1× |

Inside hashing (instrumented; **summed** worker time can exceed wall because the pool runs in parallel):

| Sub-cost | Local | Cloud | Notes |
|---|---:|---:|---|
| `_sizes` stat pass | 0.007 s | 0.323 s | One `stat` per file inside `compute_hashes` |
| `sha256_file` (22 calls) | 0.22 s summed · 10.2 ms/call | 8.45 s summed · 384 ms/call | Almost none of the wall |
| `perceptual_hash` (2,064 calls) | 135.6 s summed · **65.7 ms/call** | 1254.9 s summed · **608 ms/call** | Dominates hashing work; parallelized into ~8.5 s / ~80.7 s wall |

Parallelism check: perceptual summed ÷ hash wall ≈ **15.9×** (local) and **15.6×** (FUSE) - close to the 16-thread pool. Worker count is **not** leaving the hash phase serial; FUSE still multiplies per-call cost ~9×.

---

## 4. File opens (more important than bytes on a network mount)

| Counter | Local | Cloud | Per media file |
|---|---:|---:|---:|
| exiftool file args (subprocess opens) | 2,064 | 2,064 | **1.00** |
| `PIL.Image.open` | 2,064 | 2,064 | **1.00** |
| `Path.open` (SHA-256 streams) | 22 | 22 | **0.011** |
| **Estimated opens / file** | | | **≈ 2.01** |

Every media file is opened **at least twice** on the cold path: once by exiftool, once by Pillow for dHash. SHA-256 adds a third open for the ~1% size-collision set only. There is **no** shared open across those stages today.

---

## 5. Plain verdict - what dominates, what headroom is honest

### Dominator

**`read_metadata` (exiftool) is the largest single phase on both filesystems**, and it is worse on FUSE:

- Local: 60.6% of wall (14.5 s)
- Cloud mount: **73.8% of wall (230.7 s)**

Second place is **`compute_hashes` wall**, almost entirely **unconditional `perceptual_hash` on every file** (SHA-256 is already nearly free thanks to `_needs_sha`). On the cloud mount that is 80.7 s (25.8%).

Walk, `_sizes`, catalog/plan, dedup classify, and summarize are **noise** even on FUSE (<1 s combined except walk at 0.5 s).

### Honest headroom (upper bounds if a phase went to zero - not a design)

| If this went away | cloud-mount wall left | Max speedup vs 312.7 s |
|---|---:|---:|
| exiftool only | ~82 s | **~3.8×** |
| perceptual only (keep exiftool + tiny SHA) | ~232 s | **~1.35×** |
| both exiftool + perceptual | ~1.6 s | **~195×** (inventory-shaped) |
| SHA-256 only | ~304 s | **~1.03×** - not worth touching |

So:

1. **Size-grouping / partial-hash SHA pipelines are the wrong target** here - SHA is already 1% of files and <3% of cloud-mount wall.
2. **(tt) cheap inventory** (walk + optional stats, no exiftool, no perceptual) sits under the largest measured cost and matches the "return something in seconds" need.
3. Any Commit-3 optimization that ignores exiftool and only trims hashing can win **at most ~1.35×** on this folder unless it also cuts opens/metadata work.
4. Consolidating opens (exiftool + Pillow + rare SHA) is only interesting if it reduces **FUSE round-trips**; CPU hashing is not the story on this mount.
5. Turning down worker count for FUSE is **not** supported by this profile: the pool already overlaps ~16× on the perceptual phase. Tuning workers without a new measurement would be guessing.

### Local vs FUSE delta (what FUSE actually costs)

| Phase | Extra seconds on FUSE | Share of the 288.8 s gap |
|---|---:|---:|
| exiftool | +216.2 s | **74.9%** |
| compute_hashes wall | +72.1 s | **25.0%** |
| everything else | +0.5 s | 0.2% |

FUSE pain is **open/read latency on the two full passes (exiftool + Pillow)**, not directory walk and not SHA-256.

---

## 6. Reproducibility

**Do not re-run against `Photos/Vintage`.** The commands below are historical only; they
document how the JSON in `docs/profile-runs/` was produced. New profiles must use an
allowed corpus (`PROJECT_STATUS.md` §4).

```sh
# HISTORICAL - path is now OFF LIMITS; do not execute against Photos/Vintage
uv run python scripts/profile_organize_preview.py \
  --source "/path/to/Wayanad '14" --label local \
  --json-out docs/profile-runs/wayanad-local.json

uv run python scripts/profile_organize_preview.py \
  --source "/path/to/cloud-mount/.../Wayanad '14" --label cloud \
  --json-out docs/profile-runs/wayanad-cloud.json
```

A locked Crypto Folder mount returned `PermissionError` mid-hash once during the original
session before a successful re-run.

---

## 7. Follow-up measurement - metadata cache (2026-07-29, same historical corpus)

After extending `HashCache` to store requested exiftool tags (same path+size+mtime_ns key).
**Same OFF-LIMITS Vintage Wayanad '14 cloud folder** as §1-§5 (not Memory Cabinet / Output /
2015). Catalog + hash-cache sidecars were throwaway temp dirs; warm numbers are that
sidecar, not a write into the photo tree.

| Pass | Wall | Notes |
|---|---:|---|
| Cold preview | **243.5 s** | First write into empty sidecar |
| Warm preview | **1.43 s** | Zero exiftool subprocess calls |
| Speedup | **170×** | Saved ~242 s |

Remaining warm cost is hashing/perceptual (and walk/stat), not metadata. Force re-read
(`--refresh-metadata` / app checkbox) bypasses the metadata half when an editor changes tags
without bumping mtime.

A later cold re-profile of the same OFF-LIMITS folder (after 3a, still empty throwaway
caches) measured **~180 s** wall (exiftool ~56%, hashing wall ~43%) - same corpus
attribution; variance vs 243 s is mount/cache-state, not a different folder.
