# (adu) EVERY CATALOG OPEN TAKES THE WRITE LOCK, INCLUDING ONE THAT WILL CHANGE NOTHING.

*Body of backlog entry `(adu)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adu) EVERY CATALOG OPEN TAKES THE WRITE LOCK, INCLUDING ONE THAT WILL CHANGE NOTHING.**
  Recorded 2026-08-18, split out of `(ads)` when its reframing found that `journal_mode` is not
  the variable it looks like. **This is the question that actually gates the catalog concurrency
  work**, and it was not asked because §5.4 answered a different one convincingly.
  - **The mechanism, one line.** `Catalog.__init__` calls `_migrate` (`catalog.py:781`), which
    executes **`BEGIN IMMEDIATE`** (`catalog.py:830`) *before* it reads `PRAGMA user_version`.
    It has to: reading the version and then acting on it is the check-then-act §5.4 closed. **So
    `Catalog(path)` is a write-lock acquisition, unconditionally**, for a process that may only
    ever read.
  - **This is not a defect and must not be filed as one.** §5.4 bought it deliberately and the
    price it paid for was real: **2,170 schema writes from 7,696 opens**, one holder at
    **20,260 ms**, and both observed failure shapes at once. `PERFORMANCE.md` §5.5 then measured
    the acquisition itself at **4-8 microseconds** with **zero busy refusals in 2,160 contended
    opens**. On the numbers this is close to free. **The question is not what it costs; it is
    what it forecloses.**
  - 🔑 **WHAT IT FORECLOSES, which is why it is worth an entry.** WAL's entire win is *readers
    proceed alongside one writer*. While every open is a writer, that win has nothing to act on -
    `PERFORMANCE.md` §7 measured **two writers blocking identically in both modes**. So:
    **`(ads)` cannot be decided, or even measured honestly, until this is answered.** A run
    comparing the two journal modes through a bottleneck identical in both will find no
    difference, which is exactly what §7 found on 2026-08-09.
  - **The shape of the question, stated so it is not answered by reflex:** can an open that will
    change nothing take a **read** path, while an open that will migrate still takes the lock -
    **without** reintroducing the check-then-act race, which is what happens if the version is
    read outside a transaction and acted on inside a later one? The naive answer ("read
    `user_version` first, only take the lock if it is behind") is precisely the code §5.4
    replaced. **A cheap-looking fix here is the old defect**, and this entry exists so that is met
    as a known trap rather than discovered again.
  - ~~**Not investigated here, and named so nobody assumes it was:** whether SQLite's own
    facilities make this cleaner, what `BEGIN DEFERRED` upgrading to a write does to the race,
    and whether the migration decision can be made idempotent. **No route is recommended; none
    has been tested.**~~ ⚠ **MEASURED 2026-08-18. All of it is below, and one route survives.**

  ## MEASURED 2026-08-18 - rig on ext4, `fsync` control 256x (tmpfs read 1.1x and was refused)

  Every figure here is a run, not an argument. The mutations went through `scripts/mutate_once.py`
  so the tree is restored and verified byte-identical afterwards. ⚠ **The scratchpad on this
  machine is tmpfs**; the first thing the rig did was measure `fsync` on both and refuse the one
  that does not durably write - §5.4's own recorded trap, met at the door rather than at the end.

  ### 🔑 U2 - THE LOCK PROTECTS EXACTLY ONE THING, AND IT IS NOT THE CASE THIS ENTRY IS ABOUT

  **On an already-migrated catalog the transaction writes nothing.** Five opens of a v19 catalog:
  `sha256` of the file **unchanged**, size unchanged at 159,744 bytes, `total_changes` **0** on
  every open, and **no journal sidecar** ever appears.

  **And with `BEGIN IMMEDIATE` removed, nothing goes wrong there** - the mutation *survives*,
  which is the finding. The same mutation is *caught* immediately on a fresh catalog. Forced-race
  harness, two openers held together at the `sqlite_master` read:

  | catalog state | lock | openers that built the schema | outcomes |
  |---|---|---:|---|
  | fresh | present | **1** | both ok |
  | fresh | **removed** | **2** ← the defect, reproduced | both ok |
  | already-migrated | present | 0 | both ok, file unchanged |
  | already-migrated | **removed** | **0** | both ok, file unchanged |

  **So the race §5.4 fixed is structurally confined to the fresh-schema branch, which happens
  once per catalog in the life of a library.** The lock is paid on every open thereafter to
  protect a state that cannot recur. That is the whole of `(adu)`.

  ### ⚠ AND A SEPARATE FINDING THE RIG TURNED UP: THE LOCK DOES NOT PROTECT THE MIGRATION CHAIN

  The incremental chain runs **after `conn.commit()`**, outside the transaction (`catalog.py`,
  the `for target, migrate in _MIGRATIONS` loop). So it is not serialised, and that is
  measurable rather than theoretical. A catalog stepped back one version, openers released
  together, **150 trials each**:

  | openers | ran the v19 migration: 1 | 2 | 3 |
  |---:|---:|---:|---:|
  | 2 | 149 | 1 | - |
  | 6 | 130 | **18** | **2** |

  **One in seven six-way opens ran the same migration twice or three times, today, with the lock
  in place.** No errors - the migrations happen to be idempotent - but the protection everyone
  assumes the lock gives the chain **is not there**. Recorded in `(adl)`, which owns it. It does
  not block `(adu)`; it is named here because `(adu)`'s route must not be credited with fixing it
  and must not be blamed for it either.

  ### U1 - THE FOUR ROUTES, TESTED

  | route | what it does | result |
  |---|---|---|
  | **R1** read `user_version` first, take the lock only if behind, act on the *first* read | the shape the entry warned about | ⚠ **IS §5.4's DEFECT.** Fails `test_two_openers_build_the_schema_once` on the *first* run. Named as the trap and it behaves as one. |
  | **R2** `BEGIN DEFERRED`, read, let the first write upgrade SHARED->RESERVED | avoids the lock until needed | ❌ **DEAD.** Measured: the upgrade is refused after **0.1 ms** with `database is locked`, against a `busy_timeout` of 5,000 ms - SQLite does not honour the timeout on this upgrade. It buys one writer by making the other a casualty, which the regression test's second assertion exists to reject. |
  | **R3** make the schema build idempotent so a double build is harmless | removes the *consequence* | ❌ **NOT AN ANSWER TO THIS QUESTION.** `_SCHEMA` is already `CREATE TABLE IF NOT EXISTS` throughout - building it twice already raises nothing, which is why the regression test asserts on the *writer count* and not on an exception. It changes nothing about whether the lock is taken. |
  | **R4** unlocked read that can only decide to **SKIP**; anything else falls through to today's `BEGIN IMMEDIATE` and **re-reads under it** | double-checked locking | ✅ **SURVIVES.** See below. |

  **Why R4 is not R1 wearing a hat, which is the distinction the whole entry turns on.** R1 acts
  on the unlocked read - it decides *to write* from data nobody was holding still, which is
  check-then-act. R4's unlocked read can only reach one conclusion, **"nothing to do, return"**;
  every path that writes re-reads the version and the table under the write lock and decides
  there. **The fast path is a skip, never a decision to act.** The regression test tells them
  apart on the first run, which is the strongest evidence in this entry: same idea, one line of
  difference, opposite results.

  ### U3 - WHAT A READER CAN SEE WITHOUT A WRITE TRANSACTION (reported, not invented)

  Measured on a real v19 catalog: `user_version` (19), `schema_version` (21), `data_version` (1),
  `journal_mode` (`delete`), `locking_mode` (`normal`), and the `sqlite_master` row for `files` -
  all readable with no transaction at all. **`data_version` does detect another connection's
  commit** (1 -> 2 across an external write), and is the only one of them that answers *"has
  anyone else changed this"*.

  ⚠ **`data_version` is deliberately NOT part of the proposed route.** It answers *"did something
  change since I looked"*, which is a cache-invalidation question. The question here is *"is the
  schema current"*, and `user_version` answers that directly. Reaching for `data_version` would
  be building a scheme rather than reading a fact.

  ### U4 - WHAT THE SURVIVING ROUTE MEASURES

  Full suite under R4: **2,471 passed, 1 skipped** - unchanged. The lock-arc regression test
  passes. Concurrency sweep, already-migrated catalog, 40 trials per point:

  | | shipped p50 | R4 p50 | shipped p99 | R4 p99 | shipped max | R4 max |
  |---|---:|---:|---:|---:|---:|---:|
  | N=1 | 0.575 ms | 0.670 ms | 0.695 ms | 0.774 ms | 1.04 ms | 1.08 ms |
  | N=4 | 2.286 ms | **0.807 ms** | 9.692 ms | **1.398 ms** | 19.0 ms | **1.70 ms** |
  | N=12 | 9.565 ms | **2.201 ms** | 181.9 ms | **3.93 ms** | 232.5 ms | **4.63 ms** |

  **At twelve concurrent opens the p99 falls 46x and the worst case 50x.** ⚠ **Uncontended it is
  very slightly SLOWER** (0.575 -> 0.670 ms, one extra read on the fast path), and that is stated
  rather than buried: R4 is not a free win, it is a trade of a fixed sub-millisecond cost against
  a contention tail.

  **And on a fresh catalog it changes nothing**, which is the property that matters most - the
  unlocked read landing while another opener is mid-build was R4's one real risk, and it does not
  bite. 40 trials per point:

  | | builders per fresh catalog | errors | open p50 |
  |---|---|---|---:|
  | shipped, N=6 / N=12 | **1 in every trial** | none | 19.99 / 56.67 ms |
  | R4, N=6 / N=12 | **1 in every trial** | none | 20.87 / 58.02 ms |

  Mid-chain behaviour under R4 is statistically identical to shipped (`{1: 129, 2: 21}` against
  `{1: 130, 2: 18, 3: 2}` at six openers) - R4 neither fixes nor worsens the chain race above,
  which is correct: that is `(adl)`'s.

  ### THE PROPOSAL, AND ITS LIMITS

  **One route survives: R4.** The fast path is `PRAGMA user_version`, `_refuse_if_newer`, and the
  `files` check; if the version is current **and** the table exists, return without opening a
  transaction. Everything else is today's code, unchanged, including the re-read under the lock.

  ⚠ **What it does NOT do, so it is not credited with it:** it does not make the migration chain
  atomic (`(adl)`), it does not fix `(adt)`'s 6.5 s settings write (`(adt)`'s own open question),
  and it does not decide `(ads)` - it only makes `(ads)` **measurable**, by removing the
  bottleneck that is identical in both journal modes.

  ⚠ **What must be proven at implementation time, not assumed:** the regression test must **fail**
  when R4's fall-through is removed. Every figure above says R4 passes; none of them says the
  guard would still catch a broken R4. That is `U4`'s remaining half and it is a mutation, not a
  measurement.
  - **What must be true of any answer**, from §5.4's own evidence rather than from principle:
    two processes opening one fresh catalog must not both build the schema, and a catalog from a
    newer Truestill must still be refused before anything touches it.
  - **Cross-references.** `(ads)` - the journal mode, which this gates rather than the other way
    round. `(adt)` - the in-process race whose refusal survives a switch to WAL *because* of this
    entry. `(adn)` - two processes, one catalog, whose correctness now rests on `BEGIN IMMEDIATE`
    alone, so it is this entry's dependent and not `(ads)`'s. `(adl)` / `(adm)` - behaviour under
    the same lock. `PERFORMANCE.md` §5.4 (what the lock bought), §5.5 (what it costs) and §7 (the
    WAL decline it invalidated five days later, without either document noticing).
