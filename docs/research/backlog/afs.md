# (afs) A DESTRUCTIVE MIGRATION MAY NOT RUN WITHOUT A PRE-UPGRADE COPY, AND NOTHING SAYS WHICH ONE IS DESTRUCTIVE.

*Body of backlog entry `(afs)`, under **Internal / tooling**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afs)** Recorded 2026-08-22, split out of `(ady)` while building it. **Split rather than
  folded in, and the reason is what it is**: `(ady)` is a copy-before-upgrade fix, and this is a
  **policy change about what a migration is allowed to do**. Arriving inside the fix would have
  made it invisible as one.

  ## WHAT `(ady)` SHIPPED, AND THE ONE THING IT DELIBERATELY DID NOT

  A copy is now taken before the chain runs, and **a failure to take it degrades**: the catalog
  still opens, the failure is reported, the upgrade proceeds. That is correct **today** and its
  correctness has a stated expiry, quoted from `(ady)`'s own reasoning: every shipped migration
  is additive, so refusing to open would trade a certain harm - the user cannot reach their
  library - for a hazard that is currently **zero**.

  ⚠ **The day a migration is destructive, "degrade and proceed" is the wrong answer**, and it is
  wrong silently: the copy fails, a line is printed, the destructive step runs anyway, and the
  data it removed is gone with the only route back never taken.

  ## THE PROPOSAL

  A migration **declares** whether it destroys data. A declared-destructive step **refuses to run
  without a copy** instead of degrading. Nothing else changes: the copy stays unconditional on a
  non-empty chain, and the declaration only escalates a warning into a refusal.

  ## ⚠ WHY THE DECLARATION MUST NOT GATE THE COPY ITSELF

  The obvious economy - *"only copy when a destructive step is coming"* - is refused, and the
  reason is `(ady)`'s own thesis. **Intent is what cannot be rolled back**, so gating the copy on
  a declaration would trust the same judgement that wrote the destructive migration. A person who
  forgets to declare it is exactly the person whose migration needed the copy. The copy is cheap
  (**18.66 ms** on the real catalog, once per upgrade) and its cost is not worth that risk.

  ## THE GUARD, DEMONSTRATED RATHER THAN PROPOSED

  §4's twenty-seventh member: a rule that depends on somebody remembering to read it is not a
  control, and *"write it more clearly"* is not one of the two acceptable answers. This one **can**
  be made executable, because the discriminator is a pattern rather than a judgement - the SQL is
  in the function.

  Run 2026-08-22 over `catalog.py`, walking each migration's AST for string constants and matching
  `DROP TABLE` / `DROP COLUMN` / `DELETE FROM` / `UPDATE … SET` / `RENAME TO`:

  ```
  forward-chain functions scanned: 20   flagged: 1
    _add_* / _drop_redundant_sha256_index  (19)   no
    downgrade_v12_to_v11                          YES   ['DROP TABLE']
  ```

  ✅ **That is a real positive control from live code, not a synthetic one**: the one function in
  the module that genuinely destroys a table is the one it flagged, and it is correctly **outside**
  the forward chain. The synthetic half - `ALTER TABLE files DROP COLUMN x` - matches too, so the
  scan is not merely reporting an empty corpus (§4's fifty-second member).

  **Same shape as the guards this repo already trusts**: `test_ci_bounds_apt_in_one_place` reads
  `ci.yml`, the letter-uniqueness test reads `BACKLOG.md`, `test_timeline_rules_membership` reads
  every source file. Those work because the claim is machine-checkable **by construction**.

  ## NOT DECIDED

  - **Where the declaration lives.** A third element in each `_MIGRATIONS` tuple, a decorator, or
    a set of names beside the chain. The tuple is the least indirection and the most churn.
  - **What a refusal SAYS.** It is the harshest refusal in the product - the user cannot open
    their library until they free space - so the sentence has to name the copy, why it is
    required *for this upgrade specifically*, and what to do. `(afh)`'s rule applies:
    **ceremony tracks stakes**.
  - **Whether an escape hatch exists.** A `--upgrade-without-a-copy` flag is the obvious relief
    valve and the obvious footgun. `(afn)`'s `--force-new-identity` is the precedent for one done
    well; `(adz)`'s no-users rule says it costs nothing to omit until someone asks.
  - **Whether the guard also refuses a migration whose SQL it cannot read** - one built from a
    variable, or an `executescript` of a constant defined elsewhere. Today every migration's SQL
    is a literal in its own body, so the scan is complete; that is a property of the code as
    written, not of the mechanism, which is the same distinction `(ady)` draws about additivity.

  ## RELATED

  `(ady)` (the copy, shipped 2026-08-22 - this is the policy it deliberately left out), `(adl)`
  (the per-step transaction, which closes interruption), `(adb)` (why a filesystem copy is the
  wrong tool), `(aef)` (whether this blocks a release is not recorded anywhere, which is that
  entry's whole subject).
