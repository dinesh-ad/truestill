# (aaf) Persisted skip record - "show me what was skipped last week".

*Body of backlog entry `(aaf)`, under **Records - evidence, explicitly not work**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aaf) Persisted skip record - "show me what was skipped last week".** Ruled by the
  maintainer, 2026-07-31, from the duplicate-naming gap check. **Record only - do not build.**
  - **What is already done, and what is not.** The *current run* now names every match it
    skipped, on both surfaces (`duplicate_explain`, `organize._duplicate_report`). What is
    missing is asking **afterwards**. `stats.py` states the reason in its own payload today:
    `"exact_duplicates_found": None`, because *"Exact-duplicate skips are not stored in the
    catalog; computing this would require a new scan outside the read-only stats contract."*
    That sentence was written as `(ddd)`'s "intentional omission"; this entry is that omission
    promoted to an item of its own.
  - **Why it is (m)-sized rather than another payload fix.** `Resolution` objects live only for
    the duration of the job and are discarded with it. Nothing persists a skip, so there is no
    row to read later and no amount of payload plumbing produces one - **it needs a new table**,
    plus a retention policy (a 40,000-file re-run would write 40,000 rows nobody asked for) and
    a decision about whether an undone organize retracts its skip records.
  - **Market evidence, recorded because it will not be re-derivable later.** The single
    most-repeated complaint about photo tools, unchanged 2007-2026, is a tool that declares a
    file a duplicate and will not show *which* file it matched. One Lightroom thread has been
    open since **2018** with **21,798 views**, and users call it an *"absolute dealbreaker"*.
    The live half of that complaint is answered; this is the historical half.
  - **Open questions for the design pass:** which table and whether it belongs beside the
    catalog or in it; retention; whether the record survives `undo-organize`; and whether this
    is the same surface as (m)'s inventory of unknown media or a different one.
