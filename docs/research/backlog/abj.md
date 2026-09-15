# (abj) Find matches one substring; a two-word query finds nothing, and only the CLI is silent about it.

*Body of backlog entry `(abj)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ✅ BUILT 2026-09-15 - and the entry below is the reasoning that produced it, kept as written
>
> **The rule, from two documented positions rather than invention.** Google Issue Tracker's query
> language treats *"the space character separating search criteria as an implicit AND operator"*
> and lets *"quotation marks specify that a multi-word string is to be considered as a single
> keyword"*. GitLab, on why tokenising alone fails: users *"are actually expecting code search to
> be more like a grep experience or the find function in their IDE. These almost all behave, by
> default, as an exact substring match."* Combined: **each word is a substring, the words are
> ANDed, quotes make a phrase, and order does not matter.**
>
> **What shipped**: `catalog.parse_search_terms` splits the box (honouring quotes) and
> `catalog._search_where` builds one OR-group per term over the three columns, ANDed - **shared by
> `count_copies` and `find_copies_query`**, which is the "must change together or paging breaks"
> line below, made structural instead of remembered.
>
> ⚠ **TWO HAZARDS THIS ENTRY NAMED, BOTH CONFIRMED ON THE REAL CATALOG AND BOTH CLOSED.** A blank
> query returned **3,828 of 3,828** rows; a bare `%` did the same, because `LIKE` metacharacters
> were passed straight through, and `_` silently matched any character inside every `IMG_0001`
> somebody types. Terms are escaped now, and no terms means no rows.
>
> ⚠ **THE COST PREDICTION BELOW WAS RIGHT AND ITS SCALE WAS UNTESTED.** Re-measured at 300,000
> rows rather than extrapolated: **229 ms for one term, 285 ms for four - N terms is 1.24x, not
> Nx**, because the scan and the two joins dominate and SQLite short-circuits the AND. `PERFORMANCE.md`
> §7.1 carries the table, the refusal to index, and the FTS5-trigram price.
>
> ⚠ **THE SUBJECT PROBLEM IS REAL AND IS NOT FIXED HERE**, so it is recorded rather than implied:
> Find searches `original_name`, the drive-**relative** organized path and the source path. It does
> **not** search the drive root - that lives in `settings` as a `drive_path_hint` and is not
> joinable - so an **absolute** organized path pasted from a file manager still matches nothing.
> Nor does it search the drive **label**, which every result line prints. Both measured; neither is
> what this entry was filed about.

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
