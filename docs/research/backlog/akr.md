# (akr) THE RUN RECORD WAS BUILT WHOLE IN MEMORY AND SERIALISED AT THE LAST MOMENT.

*Body of backlog entry `(akr)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

## THE DEFECT

`write_run_record` did `json.dumps(payload, indent=2, sort_keys=True)` over the entire assembled
record, then wrote it to a `.partial` and renamed. **A cliff, not a curve**: it fires at the end of
a run, after every photograph has already been copied, and it takes the whole record with it.

Measured on the real anchor - `Test 1/look-2026-09-05/last-run.json`, **3,826 entries in 3,605,952
bytes = 942 B/entry** (a 166-entry record agrees at 953 B). At 300,000 files that is ~270 MiB of
JSON, built as one string.

## WHAT IT ACTUALLY COST, one process per point

`scripts/measure_run_record_memory.py`, entries shaped from that real record:

| files | on disk | RSS peak | serialisation alone |
|---|---|---|---|
| 75,000 | 59.6 MiB | 223.8 MiB | 119.3 MiB |
| 150,000 | 119.2 MiB | 399.5 MiB | 238.5 MiB |
| 225,000 | 178.7 MiB | 574.9 MiB | 357.6 MiB |
| **300,000** | **238.3 MiB** | **750.2 MiB** | **476.8 MiB** |

⚠ **The serialisation figure is ~2x the file on disk**, because the encoder's `str` and its UTF-8
encoding are both live at the moment of the write. The estimate this work started from was
"260-335 MiB"; the real peak is **750 MiB**.

## ⚠ THERE WERE THREE CLIFFS AND ONLY ONE HAD BEEN NAMED

The two nobody had found are on the **read** side, in `_supersede`, and they fire at the *start* of
the next run rather than the end of this one:

1. **`json.loads(current.read_text())`** parsed the whole previous record to recover **three header
   fields** for the rotated filename. A 238 MiB file read, decoded and built into Python objects to
   learn a timestamp, a kind and an id.
2. **`gzip.compress(target.read_bytes())`** held the whole file *and* its compressed image at once.

Both are gone. The format is what made it cheap: identity is on line one, so `readline` answers the
naming question, and `shutil.copyfileobj` streams the compression in 64 KiB chunks.

## THE FORMAT

JSON Lines, `RUN_RECORD_FORMAT = 4`. One self-contained object per line, `type` discriminating:

```
{"type":"run","format":4,"run":{"kind":"organize","source":"…","destination":"…","written_at":"…"}}
{"type":"file","source":"/src/IMG_0001.jpg","status":"uploaded","landed_at":"…", …}
…
{"type":"end","intended_total":4105,"attempted":4105,"entries":4105,"stopped":null}
```

- **Counts are on the trailer, never the opening line.** They are not true until the last entry is
  written; a header asserting them would promise what the run has not yet done.
- **A missing trailer means interrupted**, derived by looking - `(aem)`'s precedent, and a
  behaviour format 3 could not have at all, because it wrote one document at the very end and an
  interrupted run therefore left **nothing**.
- **`entries` is derived by the writer**, not taken from the caller, so a truncated record is
  detectable by comparing it against `attempted`.

## WHY IT IS WRITTEN AT ITS FINAL NAME

`decisions.write_decisions` states the rule this departs from - *"A truncated file at the right path
is worse than no file, because it looks like a backup."* That reasoning is about a document someone
**restores from**, and does not transfer: a run record is a log, **nothing in the product reads
one**, and staging-then-renaming is precisely what makes the failure all-or-nothing - the defect
this entry exists to remove. Stated at the site, per `ENGINEERING_STANDARD.md` §5.

## FLUSHING - and a surviving mutation is what settled it

**`flush`, never `fsync`, and never per file.** 300,000 files would be 300,000 device waits. This is
**group commit** (PostgreSQL `commit_delay`, MySQL binlog group commit) applied to a log. A run
record is not a durability primitive: nothing acks on it, nothing reads it, and re-running is free -
the warm re-run of an organised library uploads **zero**.

⚠ **The first version was `FLUSH_EVERY_ENTRIES = 1000` and it was INERT.** Deleting the flush killed
no test. `io.DEFAULT_BUFFER_SIZE` is **131,072** bytes, which at 942 B/entry fills every **139**
entries - the interpreter had flushed seven times over before entry 1000 arrived. An entry count
also means a different real bound per surface: 1000 backup entries is 80 KiB, 1000 organize entries
is 920 KiB.

Now `FLUSH_EVERY_BYTES = 64 * 1024`, deliberately **tighter than the interpreter's 128 KiB** so it
is the bound that binds and it is ours. §4: *a binding clause that asserts a machine state expires
silently* - `io.DEFAULT_BUFFER_SIZE` is exactly such a state.

## THE RESULT

| files | RSS peak (generator) | traced, write only |
|---|---|---|
| 75,000 | 48.4 MiB | 0.1 MiB |
| 150,000 | 48.1 MiB | 0.1 MiB |
| 225,000 | 48.1 MiB | 0.1 MiB |
| 300,000 | **48.1 MiB** | **0.1 MiB** |

Flat. The ~48 MiB is the interpreter and its imports, not the record. A caller still holding a list
(backup, migrate, recover) pays for its own list and **nothing** for the write: 750.2 -> 273.7 MiB
at 300,000. The file is also **13.8% smaller** (215.4 MiB against 249.9 MiB) because `indent=2` is
gone.

## OLD RECORDS: ROTATED, NEVER PARSED

⚠ **Not a compatibility path, and `CLAUDE.md`'s rule is why.** No users exist, and **nothing reads a
run record** (`(ahm)`'s null, re-run 2026-09-15 and still true), so a reader shim would have no
beneficiary. What a pre-format-4 `last-run.json` would otherwise do is *sit there forever* beside
the new `last-run.jsonl`, superseded by nothing, looking current to a person reading the directory.
So `_supersede` moves it into `runs/` under its own **mtime** and never opens it - four lines of
housekeeping, not a migration.

## WHAT DOES NOT CHANGE

**Undo.** It reverses from the catalog's `inplace_runs` / `inplace_moves` journal
(`undo._resolve_run` -> `catalog.inplace_run`), never from the record. Proved rather than argued:
`test_a_run_recorded_as_jsonl_is_still_fully_reversible` organises in place, asserts the record is
format 4, undoes, and compares every photograph's bytes.

## RELATED

`(afl)` (the record itself), `(afw)` (the history/detail split, and the 36.9 MiB measurement),
`(ahm)` (**nothing reads a run record** - the null this rests on), `(aem)` (deriving "interrupted"
rather than trusting a flag).
