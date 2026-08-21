# (aey) ON PYTHON 3.14 AN UNREADABLE FOLDER WOULD BE REPORTED AS MISSING AND CREATABLE.

*Body of backlog entry `(aey)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aey) `pathlib` STOPS RAISING ON `EACCES` IN 3.14, AND `path_probe` IS BUILT ON IT RAISING.**
  Found 2026-08-21 while researching the 3.14 upgrade. **Not live** - this project runs 3.13 - and
  it is the concrete reason the move was deferred rather than a reason to hurry it.

  ## MEASURED, on the 3.14.4 interpreter present on this machine

  ```
  chmod 000 on the parent, then:
                     3.13.13              3.14.4
  Path.is_dir()      PermissionError      False
  Path.exists()      PermissionError      False
  os.stat()          PermissionError      PermissionError
  ```

  Upstream: [cpython#144525](https://github.com/python/cpython/issues/144525),
  *"`pathlib.Path.is_file` no longer throws an exception on Python 3.14"*.

  ## WHY IT IS A DEFECT AND NOT A CURIOSITY

  `service/path_probe.py` exists **specifically** to preserve this distinction. Its own docstring:
  *"`Path.exists` and `Path.is_dir` look total and are not… they re-raise everything else,
  `EACCES` included… **absent and refused are different answers.**"* Three app surfaces once
  returned 500 on a permission-denied folder (audit F21) and this module was the fix.

  On 3.14, `probe_dir` (`path_probe.py:55-66`) reads:

  1. `path.is_dir()` → **`False`** instead of raising, so the `except OSError` never fires;
  2. `path.exists()` → **`False`**, so it returns **`PathReach.MISSING`**.

  A folder the user cannot read is reported as **absent and creatable**. Offering to create it
  sends them round a loop the module was written to prevent - and it is the same family as
  `(aac)`/`(aer)`: a place Truestill could not look into, described as one with nothing in it.
  `nearest_device` (`path_probe.py:79`) has the identical shape.

  ## ⚠ THE GUARD THAT SHOULD HAVE CAUGHT IT SKIPS INSTEAD OF FAILING

  `test_unreadable_paths.py:85` says in its own docstring: *"If `Path.is_dir` ever starts
  swallowing `EACCES`, this fails - which is exactly when someone should be made to re-read this
  module's rationale."*

  It does not fail. `_really_locked` (`:62-78`) decides whether the condition reproduced by
  calling **the same swallowing method**, so on 3.14 it concludes *"chmod 000 did not deny this
  process"* and the test **skips**. Measured: 3 runs each, deterministic - 1 skip on 3.14, 0 on
  3.13. §4's fifty-second member from the inside: the precondition check and the subject share a
  mechanism, so the subject cannot be observed failing.

  **The consequence for the new 3.14 CI leg**: it reports **2,664 passed, 2 skipped - green** - while this defect is live. The leg is evidence, not a gate, and this is why it cannot be
  promoted to one until the probe is rewritten.

  ## NOT DECIDED

  - **What the probe should call instead.** `os.stat()` still raises `PermissionError` on both
    versions and is the obvious candidate, but `path_probe`'s stated complexity is **O(1), one
    stat**, and that budget must survive the change.
  - **Whether `_really_locked` should probe with a different call from the one under test**, or
    whether the skip should become a hard failure on any interpreter where the mechanism is gone.
  - **How wide the blast radius is.** `is_dir`/`exists`/`is_file` are used well beyond
    `path_probe`; this entry names the one place with a written contract about `EACCES`, and a
    sweep is part of the work.
