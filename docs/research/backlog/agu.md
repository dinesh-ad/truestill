# (agu) THE APP'S CLEAN-EMPTY APPLY DELETED OUTSIDE EVERY LOCK.

*Body of entry `(agu)`. **Filed and FIXED in one commit, 2026-08-24** - found by an outside
audit (P34's F2), verified, reproduced, closed. The index is [`SHIPPED.md`](../../SHIPPED.md).*

- **The defect.** `server.py`'s apply route ran `service.clean_empty_apply` through a bare
  `run_in_threadpool`: no in-process occupancy, no `(aaw)` DriveLock - while the CLI declared
  the same command locked (`cli.py`: ``"clean-empty": "path"``). The one app route that
  DELETES, and the only mutating route outside every serialization.
- **Reproduced before fixing, on ext4 scratch, attempt 1 of 300**: an organize's just-created
  destination folder swept by a concurrent clean-empty between `mkdir` and the copy -
  `FileNotFoundError` at the copy. Not theoretical.
- **The fix is `jobs.claim`** - the exclusion HALF of `jobs.start`: same occupancy dict, same
  busy wording, same DriveLock, no job machinery. Ruled against routing through
  `_start_drive_job` deliberately: apply is a sub-second synchronous call whose screen contract
  is the result; a job id would have changed what the browser receives for lock reasons only,
  with the browser lane off-limits to verify it. The lock was the requirement; the job wrapper
  was one client of it. Key parity is by construction: `drive_identity` (CLI) and
  `drive_ref_for` (app) write the same ``uuid:``/``path:`` spellings, one flock file.
- **The guard was half the defect** (`(agn)`'s shape): `test_every_job_declares_whether_it_mutates`
  parsed only `_start_drive_job` call sites. Its REACH is fixed, not its knowledge: every route
  handler is enumerated, every bare `service.X` reference must carry a recorded classification
  (read / catalog-row / named exemption), and a deleting call outside job-or-claim fails the
  build generally. First run of the widened collector caught its own vacuity: a Call-only walk
  saw 17 handlers where 50 exist, because routes hand `service.X` to `run_in_threadpool`
  UNCALLED.
- **The census** (P37): clean-empty apply was the ONLY direct drive-file writer. `fs_create`
  (mkdir, idempotent, cannot destroy), `thumbnail_bytes` (app cache only) and
  `reveal_in_file_manager` (spawns a viewer) are the named exemptions; every settings/names
  route writes catalog ROWS, serialized by SQLite plus `(agp)`'s busy handling.
- **Ghost check, measured null**: at an unmounted drive's stand-in, apply removes nothing -
  its candidate set is the previous run's `emptied` list and none of those paths exist there
  (`plan_cleanup` skips absentees; the root itself is never a candidate). removed=0,
  failures=[], stand-in intact.
