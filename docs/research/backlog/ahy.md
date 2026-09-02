# (ahy) AN IN-PLACE ORGANIZE AGAINST AN EMPTY CATALOG REBUILDS NOTHING, AND REPORTS SUCCESS.

*Body of backlog entry `(ahy)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahy) AN IN-PLACE ORGANIZE AGAINST AN EMPTY CATALOG REBUILDS NOTHING, AND REPORTS SUCCESS.**
  Filed 2026-08-26 (P103). **`(aei)`'s shape on the in-place path**, found while measuring `(ahv)`.

  ## MEASURED

  An organized drive of 353 files, its catalog moved aside, rebuilt with
  `truestill organize <drive> <drive> --apply --in-place` against a fresh catalog:

  ```
        353  already in place
    353 already in place
  ```

  | | after the run |
  |---|---|
  | `files` | **0** |
  | `file_copies` | **0** |
  | `drives` | 1 - registered, uuid read from the marker |
  | `path_hint.drive.<uuid>` | **absent** |

  **Exit 0, a success sentence, and a catalog that knows nothing.** The same command in **copy**
  mode (`<drive> -> <new dest>`) rebuilt all 353 rows, which is the path
  [`soak-six-record.md`](../../soak-six-record.md) used and the one `(ahs)` records.

  ## WHY IT MATTERS

  `(ahs)` says re-organize is the only path that rebuilds a lost inventory. **For the user whose
  library is already where they want it, the natural command is the in-place one** - and it is the
  one that rebuilds nothing. The recovery path the product implicitly recommends is the arm that
  does not work.

  A user who runs it sees `353 already in place` and has every reason to believe the catalog was
  rebuilt.

  ## WHAT IS NOT YET ESTABLISHED

  **Whether "already in place" is meant to record.** Not ruled here: the organizer may reasonably
  treat a file needing no move as no work. The defect either way is that **an empty catalog is not
  the same situation as a complete one**, and nothing distinguishes them - and that the run
  registers a drive while recording none of its contents, which is `(aei)` verbatim.

  ⚠ **The missing `path_hint` is a second, independent effect**: without it the drive has no
  recorded location, so the decisions document can never be written to it either - `(ahu)`'s
  outcome reached by a different route. `cli.py:_register_destination` writes the hint on the registration path;
  this one does not.

  ## RELATED

  `(aei)` (a 0-file drive reported as success), `(ahs)` (re-organize as the recovery path),
  `(ahu)` (the missing path hint), `(afu)`.
