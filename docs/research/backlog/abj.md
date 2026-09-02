# (abj) Find matches one substring; a two-word query finds nothing, and only the CLI is silent about it.

*Body of backlog entry `(abj)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abj) Find matches one substring; a two-word query finds nothing, and only the CLI is silent about it.** Recorded
  2026-08-05. `find_copies_query` builds `%term%` and ORs it across `original_name`, `relative`
  and `source_path` - no whitespace split, no AND. So `beach 2019` matches only that literal
  string, and a photo at `2019/2019-07/2019-07-04 - Beach/` never has it. **The placeholder that
  taught exactly this query is fixed; the search is not**, because splitting is a behaviour
  change and belongs in its own commit.
  - **The shape of the fix:** split on whitespace and AND the terms, one `LIKE` per term over
    the same three columns. `2019 beach` and `beach 2019` then both match, which is what a
  person expects from a search box.
  - **What it costs:** three `LIKE '%x%'` per term, all unindexable. `(bbb)`'s paging guard
    `EXPLAIN`s the shipped statement, so the cost is measurable before it is accepted, and
    `FIND_PAGE_SIZE` already bounds what is returned rather than what is scanned.
  - **Not free to get wrong:** an empty term, or a term that is only spaces, must not become
    an unfiltered scan of every copy.
  - **MEASURED 2026-08-09, and it reframes the whole entry: this is an FTS5 question, not an
    index question.** `find_copies` plans as `SCAN file_copies` on the real catalog, and **no
    index can change that** - a leading-wildcard `LIKE` defeats a B-tree by construction, so
    adding one would cost writes and buy nothing. The 2026-08-09 catalog audit checked every
    other query for missing indexes and found none; this is the only scan that is a *design*
    consequence rather than an oversight. Measured cost today: **4.59 ms at 2,695 files, 2.15 ms
    once `ANALYZE` had run** - so the AND-the-terms fix above is affordable now, and FTS5 over
    the searchable columns is the answer if Find ever needs to be fast rather than correct.
    See `PERFORMANCE.md` §7.
