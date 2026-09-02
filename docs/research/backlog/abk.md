# (abk) The library has no per-folder view - "where is all this actually sitting".

*Body of backlog entry `(abk)`, under **Ideas / deferred**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abk) The library has no per-folder view - "where is all this actually sitting".** Recorded
  2026-08-05, dropped from the resting panel because the data does not exist rather than because
  it is not wanted. A person with 2,300 files knows the total and knows nothing about the shape
  of it on disk.
  - **The query shape.** `files.relative` already holds the organized path, so the folder is its
    parent. One aggregate, no new column and no new table:
    `SELECT substr(relative, 1, length(relative) - length(replace(relative, '/', '')) ...)` is
    the fiddly way; cleaner is to compute the parent in Python over
    `SELECT relative, size FROM files` for a first cut, and only push it into SQL if the row
    count makes that slow. Group by parent, `COUNT(*)` and `SUM(size)`, order by size, cap the
    list and state the total - the `{total, shown}` discipline, not a silent top-N.
  - **Which parent depth.** `2019/2019-07/2019-07-04 - Wayanad/` is three levels; grouping at
    the leaf gives one row per day and is useless at library scale. The useful grouping is
    probably the YEAR or the event folder, and that is the design question, not the SQL.
  - **Where it goes:** the Organize resting panel, and Stats' Shape card, which already answers
    the same question by year and by format and is the natural home for a third axis.
  - **Not a payload key going unused** - unlike the facts already surfaced, nothing computes
    this today, so it is a new aggregate rather than a wiring job.
