# (ajo) THREE CORE HELPERS ANSWER "IS THIS FILE IN TWO PLACES?" THREE WAYS, AND THE STATS SCREEN IS THE ODD ONE

*Body of backlog entry `(ajo)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md);
the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-09-01 (P180), split out of `(aiy)` as that entry's own §6 required: **"wrong today
independent of any device question - its own entry, not folded in here."** `(aiy)` closed the same
day; this is the remainder it named.

## 1. 🔑 THE DIVERGENCE, RUN RATHER THAN ARGUED

One catalog, one file, two registered drives, `verify` having found the second copy absent -
built and read in one process:

```
single_copy_shas         : 1 at-risk row(s)
single_copy_count        : 1
custody_floor            : {'no_copy': 0, 'one_copy': 1, 'floor': 1, 'held': 1, 'held_floor': 1}
stats_summary two_plus   : 1
holder_sets (P179)       : []
```

**`status` says the file is in one place. The custody strip says the file is in one place. The
Stats screen says it is on two or more drives.** Same catalog, same instant, opposite answers.

## 2. THE CAUSE IS ONE MISSING CLAUSE, AND THE OTHERS SAY WHY THEY HAVE IT

`stats_summary`'s rollup (`catalog.py:Catalog.stats_summary`) counts every row:

```sql
            WITH copy_rollup AS (
                SELECT
                    sha256,
                    COUNT(*) AS copies,
                    MAX(CASE WHEN last_verified IS NOT NULL THEN 1 ELSE 0 END) AS any_verified
                FROM file_copies
                GROUP BY sha256
            )
```

The other three exclude absent copies, and each states the rule. `single_copy_shas`
(`catalog.py:Catalog.single_copy_shas`) is the one that argues it:

> **A copy looked for and not found is not a place.** This sentence is a promise about now, so it
> excludes ``missing_at`` rows - see :meth:`list_drives` for why the drive list does the opposite.
> `(abg)`.

`single_copy_count` (`catalog.py:Catalog.single_copy_count`): *"Excludes copies known absent, on
:meth:`single_copy_shas`'s reasoning."* `custody_floor` (`catalog.py:Catalog.custody_floor`) does it in the join -
`ON fc.sha256 = f.sha256 AND fc.missing_at IS NULL` - and its docstring says *"The ``LEFT JOIN``
excludes copies known absent."*

🔑 **So this is not a live design disagreement. It is three sites carrying a rule and a fourth
that was written without it** - the rule is stated three times and implemented three times, and
the outlier cites nothing.

⚠ **`holder_sets` (added P179) is on the correct side** - `WHERE missing_at IS NULL` - so
`drive.library_independence` and `(aiy)`'s whole predicate already agree with the majority. This
entry does not touch them.

## 3. WHAT `list_drives` DOES, WHICH IS THE DELIBERATE OPPOSITE AND MUST STAY

⚠ **NOT every non-filtering site is a defect, and the codebase already drew the line.**
`single_copy_shas` points at `list_drives` for *"why the drive list does the opposite"*: a drive
list reports **history** - what was put there - and a copy that has gone missing is still part of
what that drive was asked to hold. **A promise about now filters; a record of the past does not.**

**So the fix is not "add `missing_at IS NULL` everywhere".** It is: `stats_summary`'s copy rollup
makes a promise about now - the Stats screen's *"on two or more drives"* is read as present-tense
safety - and it is on the wrong side of a line this codebase has already drawn and written down.

## 4. THE HARM, RANKED HONESTLY

**Lower than `(aiy)`'s, and it should be said plainly rather than inflated:** nothing here gates a
delete. `reclaim`'s guard reads `reclaim_candidates.copy_count`, not `stats_summary`.

What it costs is **a screen that contradicts two others about custody**, in the reassuring
direction, and only after `verify` has actually proved a copy gone - which is exactly the moment a
user is looking for a straight answer. `(aiy)` §2's finding one level down: a custody number that
does not vary with what the user cares about.

## 5. WHAT IS NOT ESTABLISHED

- **How many real libraries have any `missing_at` set at all.** It is written only by `verify`
  on a drive that was there (`catalog.py:Catalog.mark_copy_missing`), so an unplugged drive sets nothing. The real
  catalog was not probed for this; the divergence above is constructed.
- **Whether `files_on_two_plus_drives` is the only affected column.** The same rollup feeds
  `any_verified`, and that was not traced.
- **What the Stats screen should say for a file whose second copy is known absent** - one place,
  or one place with a named absence. A wording call, not settled here.

## RELATED

`(aiy)` (shipped 2026-09-01 - the device question this was deliberately kept out of),
`(abg)` (the `missing_at` rule the three filtering sites cite), `(ahg)` (app-only surfaces the
parity table cannot see).
