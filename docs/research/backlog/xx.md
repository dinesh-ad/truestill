# (xx) Absolute-path columns and hash-cache keys are not machine-portable.

*Body of backlog entry `(xx)`, under **Records - evidence, explicitly not work**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(xx) Absolute-path columns and hash-cache keys are not machine-portable.** Ruled by
  the maintainer from the 2026-07-30 move audit. **Record only - do not fix in the loud-failure
  series.** Commits 1-3 (**(ww)** path hints, catalog startup announcement, reclaim/undo
  staleness) made a machine move **survivable by failing loudly**; the remaining work is
  **portability**, not safety. User procedure:
  [`docs/moving-machines.md`](../../moving-machines.md).
  - **`files.source_path`** - absolute. Used by reclaim and by display labels (`where`,
    near-dup "matched" paths). After a move the recorded sources are gone; reclaim reports
    the missing count rather than a silent empty plan. A future rewrite (relative-to-drive,
    or clear-on-reclaim-only) is product design, not a hotfix.
  - **`inplace_runs.source_root` / `dest_root`** - absolute. Undo refuses unreachable stored
    roots and points at `--source-root` / `--dest-root`. Making the journal remount-native
    (uuid + relatives only) is later work; the overrides already exist.
  - **`reclaim_journal.source_path`** - absolute. Crash/audit resume only; stale after a
    move. Low urgency once reclaim no longer pretends mid-flight old paths are live.
  - **Hash-cache non-portability** (`catalog.cache.sqlite`, keyed by absolute path + size +
    `mtime_ns`, plus a tag-set fingerprint for metadata). Machine-local and disposable by
    design (`IMPLEMENTATION_STANDARDS.md` §8). Copying the sidecar to a new machine does
    **not** preserve the ~170× warm metadata win; first preview is cold.

    | | Absolute keys (today) | Drive-relative (`uuid` + relative) |
    |---|---|---|
    | Survives remount with preserved mtimes | No | Yes for **organized drive copies** |
    | Helps arbitrary unmarked `--source` trees | Yes (path-scoped) | No |
    | Cross-machine copy that resets mtime | Miss anyway | Miss anyway |
    | Wrong-file collision risk | Lower | Higher if relative reused / wrong root |
    | Matches custody model | Intentionally **not** in the catalog | Closer to custody, couples cache to "is this a drive?" |

    Prefer leaving the cache disposable over a half-portable key until a concrete trigger
    (measured remount pain that loud failures do not cover) appears.
  - **Not fixed here, on purpose** - recorded only, per instruction.
