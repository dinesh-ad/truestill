# (agy) FIVE THINGS THE CATALOG WRITES AND NOTHING READS - a census, not a verdict.

*Body of entry `(agy)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(agy) FIVE THINGS THE CATALOG WRITES AND NOTHING READS.** Filed 2026-08-24 (P47). ⚠ **NOT A
  DEFECT ON ITS FACE, and this entry deliberately rules nothing.** It records a family and the
  question nobody has answered for it: *recorded on purpose for a surface not yet built, or dead
  weight to delete?* Each row may have a different answer, and one of them already does.
  - **Found by generalising a single instance.** `migration_runs.completed_at` turned up while
    proving a `(agm)` mutation in P46 - the mutant survived because the column it changed has no
    reader - and the census asks what else is shaped that way.

## The census

**A column counts as READ if it appears in a `SELECT` list, a `WHERE`, a `JOIN` or an `ORDER BY`**
- not merely in an `INSERT` column list or an `UPDATE SET`.

| written and never read | its writer | the only reads of its table |
|---|---|---|
| `migration_runs.completed_at` | `finish_migration_run`, `catalog.py:1471` | `SELECT run_id ... ORDER BY started_at` (`catalog.py:1481`) |
| `file_copies.copied_at` | `record_copy` / `record_uploaded` INSERTs | six queries over `file_copies`, none names it |
| `reclaim_journal.reclaimed_at` | the journal INSERT | `SELECT source_path, sha256, freed_bytes` |
| `skipped_clusters.skipped_at` | the skip INSERT | `SELECT signature` |
| **`file_albums` - the whole table** | `INSERT OR IGNORE`, `catalog.py:3039` | **none in shipped code** |

🔑 **WHY THIS CENSUS IS A PROOF RATHER THAN A SUGGESTION, and it is an interlock the repo already
owns**: `IMPLEMENTATION_STANDARDS.md` requires that *"every catalog query names its columns; none
selects `*`"*, pinned by `test_queries_name_their_columns.py`. Without that rule a `SELECT *`
somewhere could be reading any of these and no grep would show it. With it, **"named in no query"
really does mean "never read"**.

**The check, so the next reader re-runs rather than re-derives:** for each column, compare its
appearances against every SQL string in `packages/*/src/`. For `file_albums` the whole answer is
three lines - `grep -rn "file_albums" --include="*.py" packages/*/src/` returns the `CREATE TABLE`
in the schema, the same statement in the v5 migration, and the `INSERT OR IGNORE`. **No SELECT.**

## The shape it belongs to

This is the **`verified: Literal[True]` family at the schema layer** - a value that carries no
information to any reader. The precedent is `(afw)` Stage 4, where a backup summary's `verified`
*"stopped being a constant"* (`IMPLEMENTATION_STANDARDS.md:835`): a field that can only ever say
one thing is a field that answers no question. A column nothing selects is the same defect one
layer down, and it costs a little space, a little write time, and a reader's assumption that
somebody must be using it.

## ⚠ `file_albums` IS NOT ORPHANED - it has an owner, and that is the answer for one row

**Checked outside the product code, which is where the answer was.** `file_albums` has three
consumers, none of them shipped code:

- **`(acg)`** - an **open backlog entry** whose entire subject is this table: *"album membership
  cannot leave this machine"*, because `PRIMARY KEY (file_id, album_id)` is two catalog rowids.
- **`docs/decisions-on-drive-research.md:110`** - the drive-document design, which states that
  album membership **must travel** and how.
- **`packages/truestill-cli/tests/test_ingest.py:88`** - a test that reads it back through a JOIN,
  so the write is pinned even though no product surface consumes it.

**So for this row the question is already answered: deliberate, and waiting.** `--map-albums`
populates it, `(acg)` owns what has to change before it can be used, and deleting it would delete a
feature's persistence rather than dead weight. ⚠ **Recorded because the census alone would have
read as five orphans, and one of them is a half-built feature with a named owner** - which is
exactly why this entry rules nothing.

⚠ **AND `(acg)` CARRIES A CLAIM WORTH RE-CHECKING BEFORE ANYONE ACTS ON IT**: *"the albums tables
are empty today"*. That is true of a catalog nobody has run `--map-albums` against, and
`test_ingest.py` demonstrates rows arriving when somebody has. Not corrected here - it is that
entry's sentence, and this one only notes that it is conditional.

## The four timestamps - the open question

`copied_at`, `reclaimed_at`, `skipped_at` and `migration_runs.completed_at` are all **provenance
timestamps**, and provenance is a legitimate reason to write something nothing queries: it is there
for a human reading the database after something went wrong. **That is a real answer and it may be
the right one for all four.** What this entry records is that **nobody has said so**, and the two
readings are indistinguishable from outside:

- *deliberate audit trail* - keep, and say so where the column is defined, the way
  `file_copies.missing_at` already explains itself; or
- *left over from a query that was removed or never written* - delete, with the migration that
  drops it.

⚠ **`migration_runs.completed_at` is the one with a consequence beyond tidiness**, and it is why
this was noticed at all: `run_migration` decides whether to call `finish_migration_run` based on
`migrated == total`, so **that decision currently has no observable effect**. A mutation flipping
the condition killed no test, and none could - which means the close condition is unguardable until
something reads the column or the call is removed. Whoever answers this row answers that too.

## Null reported

**`file_copies.date_baked_at` is NOT write-only**, though a first pass flagged it: it is read at
`catalog.py:1712` and `catalog.py:1733`, both in `WHERE` clauses. The first pass searched only
`SELECT` lists. Recorded because it is the same mistake this census exists to avoid - **a `WHERE`
is a read** - and because that column is `(agv)`'s subject, where a false "nobody reads it" would
have been expensive.
