# (akb) NINE §9 RULES ARE ENFORCED ONLY BY THE FILE THE REACT REWRITE DELETES.

*Body of backlog entry `(akb)`, under **Conditional, and counted**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(akb)** Filed 2026-09-04 (P211), from a census of the truth contract against the migration plan.

  ## THE CHECK THAT FOUND IT, AND ITS COUNT

  `IMPLEMENTATION_STANDARDS.md` §9 is 48 rows. Counted over the section's table:

  ```sh
  # rows citing the file the flip deletes
  awk '/^## 9\. User-facing/,0' docs/IMPLEMENTATION_STANDARDS.md | grep -c '^| \*\*.*app\.js'
  ```

  **20 of 48 rows (42%) name `app.js`. Nine of those name NOTHING ELSE** - no core module, no
  service, no `jobs.py`:

  - Counts are grammatical.
  - A move says which files it did not take, and where they still are.
  - One vocabulary, one home: the skipped-census groups are produced once and rendered generically.
  - A summing block sums, on Import too.
  - The text-size preference ADJUSTS the reader's own default and never replaces it.
  - A tab older than the server says so.
  - One fact is stated once per moment.
  - A drawing constant is never the number in a claim.
  - Known values prefill; Browse is for overriding.

  ## WHY THIS IS THE CANON'S REAL EXPOSURE TO THE NEXT PHASE

  P211 measured whether the canon is scar tissue from finished engine work and found it is not -
  §4 is **91% universal methodology with one engine-specific member**. The rules are not the
  problem. **The enforcement is**: `react-migration-plan.md` says *"The flip is one commit - the
  template, the switch and the old template - and `app.js`"*, and on that commit nine binding rules
  stop having a named guard while remaining binding.

  ⚠ **They do not become false; they become unwatched**, which is worse than a rule that is
  wrong, because nothing reports it. This is `(ajv)`'s shape one level up: the browser lane was
  green for nineteen days over a bundle the release never built, because the test and the artifact
  were different things.

  ## WHAT WOULD CLOSE IT

  Before the flip commit, each of the nine either points at a guard that survives the rewrite, or
  is recorded as knowingly unenforced with the reason. **Not a new guard class** - most of these
  are asserted today by `tests/e2e/` files that select by rendered words and survive a renderer
  swap; the migration plan's own measurement is *"the other 52 assert on rendered words, so they
  survive a renderer swap and become the acceptance test for each migrated screen"*, corrected on
  2026-09-03 to **60 files, 510 tests** with **31 files reaching into the page through `evaluate`**.
  The work is re-pointing citations, not inventing coverage.

  ## THE CONDITION

  Fires at the `(adi)` cutover and not before. Nothing is wrong today - `app.js` exists and the
  guards run. **Counted: 9 rows of 48.**
