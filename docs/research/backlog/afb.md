# (afb) CLEANUP'S "PURE: READS, NEVER WRITES" PLAN CRASHED ON A FOLDER IT COULD NOT LOOK AT.

*Body of backlog entry `(afb)`, **CLOSED 2026-08-21**. The closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(afb) THE THIRD BARE PREDICATE IN A DELETE PATH, FOUND BY SWEEPING RATHER THAN BY A FAILURE.**

  ## HOW IT WAS FOUND, WHICH IS THE POINT

  `(aez)` was two bare `is_file()` probes in `reclaim.py` with the guarded helper **three
  functions above them**. The maintainer's question on reading that: *two bare probes in one
  module, with the correct helper adjacent, suggests nobody has swept it rather than that those
  were the only two.* The sweep was run. There was a third.

  ## MEASURED

  `cleanup.plan_cleanup` gated on a bare `folder.is_dir()`. With the folder's **parent** refused:

  | | 3.13.13 | 3.14.4 |
  |---|---|---|
  | `plan_cleanup(root, ["Camera/2013"])` | **`PermissionError` - the plan dies** | `[]` - silently skipped |

  ⚠ **`plan_cleanup`'s own docstring is *"Pure: reads, never writes"***, which is the guarantee
  that makes a cleanup preview safe to run at all. A traceback at the end of an otherwise
  successful organize is the loudest possible way to break it.

  ⚠ **And 3.14 masked it, exactly as it masked `(aez)`.** That is the second time the version
  being treated as the threat turned out to be the one hiding a live defect on the version we
  ship. Worth stating twice because it inverts the intuition the upgrade work started from.

  ## WHY `OCCUPIED` AND NOT `continue`

  On 3.14 the folder simply vanished from the plan - and `continue` in that loop means *"a
  previous cleanup, or the user, may already have dealt with it"*. A folder that will not answer
  was **not** dealt with, so conflating them hides it. It is now reported `Tier.OCCUPIED`, which
  is the verdict `_classify_with` already returns when `iterdir` refuses: the module's two
  unreadable cases finally agree with each other.

  ## THE SWEEP ITSELF - what was checked, including what was clean

  Every destructive call in `packages/*/src` was read, and every predicate that gates one:

  - `reclaim.py` - `(aez)`, fixed. Now every filesystem touch is inside `_readable_file` or has
    its own `except OSError`.
  - `cleanup.py` - **this entry**. `_classify_with`'s `iterdir` was already guarded; its per-entry
    `is_dir()`/`is_file()` calls are **not** exposed, measured rather than assumed: `stat` needs
    permission on the *parent*, so a `chmod 000` **child** answers `True` on both versions. The
    only reachable refusal is the folder itself, which `iterdir` catches.
  - `organizer._move_source` - **clean**. It verifies by **checksum**, not by a predicate, and
    catches `(DestinationError, OSError)` around the verify and `OSError` around the `unlink`.
    Every failure keeps the source. This is what the pattern should look like.
  - `undo.py`, `safe_copy.py`, `decisions.py`, `archive_extract.py`, `thumbnails.py`,
    `selfcheck.py`, `session_link.py`, `exif.py`, `destinations/local.py` - the remaining
    `unlink`/`replace`/`rename` calls operate on **Truestill's own** temp files, journals and
    markers, not on a user's originals, and each is inside its own `try`.

  **Two of three delete-adjacent modules had the defect; the third shows the correct shape.** That
  ratio is the argument for the `IMPLEMENTATION_STANDARDS` row rather than three more comments.
