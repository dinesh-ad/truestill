# (ahm) SIX OF NINE RUNS WRITE A HISTORY NOTHING READS.

*Body of backlog entry `(ahm)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahm) SIX OF NINE RUNS WRITE A HISTORY NOTHING READS.** Filed 2026-08-25 (P81), split out of
  `(agm)`'s closing report rather than folded into `(ahl)`.

  ## THE NULL, AND THE CHECK THAT ESTABLISHED IT

  `grep -rn 'record_path_for\|run_index_for\|runs_dir_for\|superseded_record_path\|last-run\|index\.jsonl'`
  over `packages/*/src`, minus the two modules that own the artefacts, returns **three** mentions:
  `migrate.py:_plan_relatives` (a docstring), and `cli.py:29` / `cli.py:_print_capped`, which are a **write** path.
  Zero in `static/app.js`. Zero in `frontend/src/`. **Nothing reads a run record.**

  The one human affordance is `truestill organize --report PATH` (`cli.py:_add_common_options`), whose help says
  *"write this run's record here instead of beside the catalog"* - it moves the file, it does not
  read one. It exists for `organize` alone. No app route serves a record.

  ⚠ **`(afl)`'s stated value was NAMING WHAT FAILED.** Six surfaces now do that into a file nobody
  opens, which satisfies the letter of it and none of its purpose.

  ## ⚠ RULED OUT OF CONDITION 3, DELIBERATELY

  A written file with no reader looks like a computed field with no consumer, one layer up. It is
  **not** `PROJECT_STATUS.md`'s condition 3, for three reasons, and the ruling is recorded here so
  it is not re-argued:

  1. **A record has a designed consumer; a dead payload key has none.** `--report PATH` exists so a
     person can open the file. Thin, and real. A dead key cannot acquire a reader without a UI
     change.
  2. **Condition 3's subject is the route-to-surface contract** - what step 2 makes STABLE and step
     3 rebuilds in React. A file beside the catalog is not on that contract.
  3. **Condition 1 already owns records.** Folding them in would make condition 3 unclosable for a
     reason unrelated to its subject, which is the defect `(agm)` just repaired in condition 1's
     own wording.

  **So `(ahl)`'s count stays 34 and this is separate.** ⚠ But the ranking is the other way round:
  by this condition's scope it is fourth; **in absolute terms it is larger than all three of them
  together** - nine runs' worth of history against thirty-four fields.

  ## THE CANDIDATES, and what each would need

  | candidate | what it answers | what it needs |
  |---|---|---|
  | **`truestill status`** | *"what happened recently"* | tail `runs/index.jsonl`. The cheapest by a wide margin: the index is append-only and **119 B a line**, measured. A reader and its wording |
  | **`truestill where <term>`** | ⚠ *"what happened to THIS file"* | a reverse lookup. Records are keyed by **run**, so a per-file answer means scanning every detail file, or building an index that does not exist |
  | a new `truestill runs` | the whole history | a subcommand, a reader, a truncation policy - and `(ahj)`'s guard would then require it to declare itself non-mutating |
  | an app screen | the same, in a browser | a route - **whose payload lands straight back in `(ahl)`'s scope** |

  🔑 **`truestill where` is the one that satisfies `(afl)`'s PURPOSE rather than its letter**, because
  naming what failed is a per-file question and `where` is the per-file command. It is **also the
  only one whose cost is not trivial.** Those two facts belong in the same sentence; picking
  `status` because it is cheap would answer a question nobody asked of the records.

  ⚠ **This entry does not choose.** It records the null, the ruling, and the four shapes.

  ## RELATED

  `(afl)` (the record, and the value this fails to deliver), `(agm)` (migrate's and bake's, the
  commit that made it six), `(ahi)` (the remaining three runs), `(ahl)` (condition 3, which this is
  ruled out of).
