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
  - **Not investigated here, and named so nobody assumes it was:** whether SQLite's own
    facilities make this cleaner than hand-rolled ordering, what `BEGIN DEFERRED` upgrading to a
    write actually does to the race, and whether the migration decision can be made idempotent
    rather than exclusive so that two openers building the same schema is harmless instead of
    prevented. **No route is recommended; none has been tested.**
  - **What must be true of any answer**, from §5.4's own evidence rather than from principle:
    two processes opening one fresh catalog must not both build the schema, and a catalog from a
    newer Truestill must still be refused before anything touches it.
  - **Cross-references.** `(ads)` - the journal mode, which this gates rather than the other way
    round. `(adt)` - the in-process race whose refusal survives a switch to WAL *because* of this
    entry. `(adn)` - two processes, one catalog, whose correctness now rests on `BEGIN IMMEDIATE`
    alone, so it is this entry's dependent and not `(ads)`'s. `(adl)` / `(adm)` - behaviour under
    the same lock. `PERFORMANCE.md` §5.4 (what the lock bought), §5.5 (what it costs) and §7 (the
    WAL decline it invalidated five days later, without either document noticing).
