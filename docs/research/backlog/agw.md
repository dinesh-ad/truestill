# (agw) `last-run.json` IS WRITTEN OUTSIDE THE LOCK THAT GUARDS THE REST OF THE RECORD.

*Body of entry `(agw)`, under **Internal / tooling**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(agw) `last-run.json` IS WRITTEN OUTSIDE THE LOCK THAT GUARDS THE REST OF THE RECORD.**
  Filed 2026-08-24. **This is `(afw)`'s third NOT DECIDED item coming due**, quoted from its own
  text: *"One rolling file per catalog, with a job runner. The app can have two jobs in flight on
  two drives; `(aaw)`'s lock makes that safe per drive and does not serialise different drives, so
  one rolling `last-run.json` would be overwritten by whichever finished last. **This is the part
  to design before any second writer is added**, and `(afu)` did not hit it because organize is
  currently the only writer."*
  - ⚠ **THREE WRITERS EXIST NOW**, checked rather than assumed:
    `grep -rn "record_organize\|record_undo" --include="*.py" packages/truestill-app/src/`
    → `service/organize.py`, `service/backup.py`, `service/organize_undo.py`. The condition
    `(afw)` said to design before was passed **twice** without being designed.
  - **What IS already handled, so the entry is not overstated.** `run_record.record_run` takes
    `lock_for(runs, operation="run-record")` around the index append, the supersede and the
    prune. Two runs on two drives therefore cannot tear `runs/index.jsonl`.
  - **What is not.** `write_run_record(record_path_for(catalog), payload)` is the **last line of
    `record_run` and sits OUTSIDE that block**. Two runs finishing together can interleave
    supersede and write, so one run's detail can be demoted or lost while its index line stands.
  - 🔑 **Bounded by design rather than by luck, which is why this is a design item and not a
    defect:** `IMPLEMENTATION_STANDARDS.md` §1 already rules that *"a line never says whether its
    detail still exists - a reader looks"*, and that a run recorded with no detail **is the same
    state a pruned run is in**. So the failure costs DETAIL and can never cost the FACT.
  - **The question to answer**, and it is `(afw)`'s: whether `last-run.json` stays one rolling
    file per catalog now that several drives can be written at once, or becomes per drive. Both
    have costs and neither is a bug fix. **Measure the window before choosing.**
