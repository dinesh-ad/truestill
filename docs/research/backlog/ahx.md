# (ahx) `not_applied` REACHES NO CONSUMER, SO A RESTORE NEVER SAYS THE ALBUMS WERE DROPPED.

*Body of backlog entry `(ahx)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahx) `not_applied` REACHES NO CONSUMER, SO A RESTORE NEVER SAYS THE ALBUMS WERE DROPPED.**
  Filed 2026-08-26 (P103). The
  computed-and-read-by-nobody class, on the restore path.

  ## THE FIELD, AND THE DOCSTRING IT CONTRADICTS

  `apply_decisions` returns `not_applied=("albums",)` whenever a document carries albums
  (`decisions.py:590`); the field is declared at `decisions.py:373`.

  `_print_restore_plan` (`cli.py:1440`) prints `unmatched_events`, `awaiting_content`,
  `already_newer_locally`, `superseded` and `undated` - **and not this one**. Its own docstring, at
  `cli.py:1441-1444`, promises *"What would come back, and - the half that is easy to leave out -
  what would not."*

  ⚠ **So a user restoring is never told the albums section was discarded**, on either surface:
  grep for `not_applied` across `packages/` returns four hits total - the declaration
  (`decisions.py:373`), the write (`decisions.py:590`), one documentation line, and a test whose
  name collides and is about date corrections. **No test asserts it, so deleting `decisions.py:590`
  breaks nothing.**

  ## WHY THE ALBUMS ARE DROPPED IS RECORDED - THIS IS NOT THAT

  The write-only behaviour is **intended**, ruled at [`acg.md`](acg.md) lines 9-11, which names
  `not_applied` exactly. This entry is not a request to restore albums; it is that the product
  computes a fact about a user's data and shows it to nobody.

  ⚠ **And `(acg)`'s justifying premise is false** - corrected in that entry the same day. It reads
  *"the albums tables are empty today"*; `takeout.py:244` -> `cli.py:2484` builds
  `IngestContext.albums` **unconditionally** on every ingest -> `organizer.py:2121` ->
  `catalog.py:3113`. `--map-albums` does not gate it. Every Takeout user with album folders has
  album names written to their drive on every save and silently discarded on every restore, which
  is what makes the missing sentence matter rather than being tidy-up.

  ## THE ASYMMETRY NOTHING RULES ON

  `decisions.py:863` puts `albums` in `_LOSS_KEYS`, so an album name is **protected from being
  overwritten on the drive** while still never being readable back into a catalog. Written,
  guarded against loss, and unreadable. No document rules on that combination.

  ## THE FIX

  One line in `_print_restore_plan`, and the app's restore payload alongside it - the same shape
  `(abm)` used for `unreadable_dirs`. **Loop the report's own fields rather than naming five**, or
  the sixth omission repeats this one.

  ## RELATED

  `(acg)` (the ruling and its corrected premise), `(abm)`, `(ahl)`, `(ahn)`,
  [`decisions-on-drive-research.md`](../../decisions-on-drive-research.md).
