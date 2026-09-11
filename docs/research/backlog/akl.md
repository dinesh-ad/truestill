# (akl) THE IMPORT PREVIEW NAMES NO DRIVE, AND `app.js` ALREADY ASKS IT TO.

*Body of entry `(akl)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

- **(akl)** Filed 2026-09-11 while building D17's apply route.

  ## WHAT IS KNOWN

  `app.js`'s `rcRenderSummary` ends with two calls that can never render anything:

      ${orgMarkup().matchList(r.duplicate_matches, "Show what each duplicate matched")}
      ${orgMarkup().matchList(r.near_dup_matches, "Show what each look-alike resembles")}

  `IngestPreviewSummary` has never declared `duplicate_matches` or `near_dup_matches`. Organize's
  payload does - `service/organize.py:_duplicate_report` builds both - and Import's does not.

  ⚠ **NOTHING IS BROKEN TODAY.** `frontend/src/preview.tsx:MatchList` types its report
  `DuplicateReport | null | undefined` and returns `null` on a falsy one, so the absence is
  tolerated by design rather than by luck. This is a gap, not a defect.

  ## WHY IT MATTERS

  `IMPLEMENTATION_STANDARDS.md` §9: a preview that finds files already in the library **says so and
  names WHICH library**. Organize satisfies that; Import reports only counts. Since D17 the Import
  payload carries `already_in_library` - the library's answer, kept separate from the
  destination's promise - so the count exists and only the naming is missing.

  ## WHY IT WAS NOT FIXED IN THE COMMIT THAT FOUND IT

  `_duplicate_report` lives in `service/organize.py`, and `service/takeout.py` **cannot import
  it**: `organize.py` already imports `InferredLocalShiftPayload` from `takeout.py`, so importing
  back is a circular import that neither ruff nor mypy reports. That cycle already forced two
  relocations in the same commit (`destination_scope.py`, and `ingest_run` landing beside
  `organize_run`). A third relocation to fill a gap that renders nothing today is the wrong trade
  inside a commit about applying an import.

  ## WHAT THIS ENTRY DOES NOT DECIDE

  Whether the fix is to move `_duplicate_report` to a neutral module, to move
  `InferredLocalShiftPayload` out of `takeout.py` and break the cycle the other way, or to render
  Import's naming from `already_in_library` alone without the per-file samples.
