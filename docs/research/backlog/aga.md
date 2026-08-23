# (aga) THE TYPE FENCE WAS A DIRECTORY LIST, SO A FILE THAT SATISFIED ITS RULE SAT OUTSIDE IT.

*Body of entry `(aga)`, in [`SHIPPED.md`](../../SHIPPED.md). The letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(aga)** Shipped 2026-08-23, found while shipping `(afy)`.

  ## The rule and its implementation disagreed

  The `Makefile` states the rule twice, in its own words:

  > `scripts/` is in the type fence too: **it is real code that imports the core**, and the one
  > file left out of it silently imported a module that had not existed for two renames.
  >
  > `packaging/` is in the fence for the same reason `scripts/` is: **real code that imports the
  > core**.

  The rule is a **property**. The implementation was a **list of directories**
  (`CORE CLI APP SCRIPTS PACKAGING`). So a file could satisfy the rule and be outside the fence
  anyway, purely by living somewhere the list did not name - and two did:

  - **`suite_scratch.py`** decides where **every test in the suite writes** (`(afy)`).
  - **`conftest.py`** at the root decides what every test can **reach** - the data and cache
    directories `(aae)` was filed about.

  Neither contains a test, asserts anything, or is collected as one. Both import the core. Both
  were unchecked, and **being unchecked was never a judgement about them** - nobody decided;
  the list simply did not reach the repo root.

  ⚠ **The same shape as `(afu)`**, which is why this is an entry rather than a tidy-up. There, a
  rule stated in §1 as a **product invariant** was implemented in `truestill-cli`, which
  `truestill-app` is forbidden to import - so the surface the rule's own reasoning named could
  not have satisfied it. Here a rule stated as *"real code that imports the core"* was
  implemented as five directory names. **A rule scoped to a set of PLACES, with the file that
  matters outside them.**

  ## What it cost to fix: one word

  Measured before deciding, on the tree as it stood:

  | target | `uv run mypy` (Makefile / CI path) | pre-commit hook (isolated env) |
  |---|---|---|
  | `suite_scratch.py` | **0** | **0** |
  | `conftest.py` | **0** | **2** |

  Both clean under `strict = true` on the path the gate actually uses. The widened
  `make typecheck` reports **`Success: no issues found in 118 source files`**.

  🔑 **`conftest.py` was not the reason not to, and the fear had a number: zero.** Its 2 hook
  errors were **one cause** - `pytest` absent from `additional_dependencies`, so mypy in the
  isolated env could not resolve the import, and the then-unresolvable `@pytest.fixture`
  decorator read as untyped. Adding `pytest` cleared both.

  ## ⚠ AND THE COMMENT DESIGNED TO PREVENT THIS DRIFT WAS ITSELF FALSE

  `.pre-commit-config.yaml` carried, directly above the regex:

  > Keep in step with `make typecheck` and the CI mypy step, **which cover exactly this set**.

  They did not. The regex was
  `^(packages/(truestill-core|truestill-cli|truestill-app)/src/|scripts/)` - **no `packaging/`** -
  while `Makefile`'s `typecheck` and `ci.yml`'s Mypy step have both checked it since it was
  added. So `packaging/` was covered by `make check` and by CI and **not** by the hook.

  **This is the finding, not the missing directory.** The sentence asserting the three sets agree
  is precisely what stopped anyone comparing them: a reader who wants to know whether the hook
  matches the Makefile reads that line and stops. It is `ENGINEERING_STANDARD.md` §4's
  fifty-eighth member - *writing the reason down is what makes it checkable* - failing in the
  direction where the written reason is **wrong**, and the neighbouring thirty-second member,
  where a claim about a **machine state** expires in silence while a claim of **intent** does
  not. *"These three lists are identical"* is a machine state.

  ⚠ **The residual is stated rather than closed: it is still prose.** Nothing executes the
  comparison, so the next divergence is found the way this one was - by somebody asking. Making
  it a check means teaching a test to parse a `Makefile`, a workflow file and a regex, and
  agreeing what "the same set" means across three notations. Not attempted; recorded so the
  next person knows it was considered.

  ## ⚠ THE TEST CORPUS STAYS OUT, AND NOW FOR A MEASURED REASON

  §6 keeps tests out of the fence. That was a preference; it is now evidence. `mypy` over all
  four test directories does not report type errors - **it cannot run at all**:

  ```
  packages/truestill-app/tests/conftest.py: note:     b) adding `__init__.py` somewhere,
  Found 1 error in 1 file (errors prevented further checking)
  ```

  Four `conftest.py` files, no `__init__.py` anywhere, duplicate module names. mypy stops before
  type-checking begins. **§6 is vindicated rather than merely agreed with**, and the reason is
  structural rather than about test quality - which matters, because "tests are messy" would
  invite someone to clean them and try again, and that would not help.

  **It does not apply to the two files widened here**: they are uniquely-named modules passed as
  explicit paths, so there is nothing to collide with. The boundary that holds is *code that is
  not a test*, not *code outside `tests/`*.

  ⚠ **Near-ready, noted and NOT proposed.** `packages/truestill-core/tests/conftest.py`,
  `packages/truestill-app/tests/conftest.py`, `app_support.py` and `e2e_support.py` are all at
  **0** errors already, and `tests/e2e/conftest.py` has exactly **one** real finding
  (`:126`, missing return annotation). So the test infrastructure is close - and the duplicate
  module names, not the type errors, are what stops it. Anyone revisiting this should attack
  that, not the annotations.

  ## What shipped

  - `Makefile`: `ROOT_CODE := conftest.py suite_scratch.py`, appended to `typecheck`.
  - `ci.yml`: the Mypy step gains the same two paths.
  - `.pre-commit-config.yaml`: `packaging/` and root `.py` files added to `files:`, `pytest`
    added to `additional_dependencies`, and the false comment replaced with what is true.
