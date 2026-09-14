# (akk) RESTORE'S CANCEL COPY ASSUMES A PARTIAL APPLY THE ENGINE CANNOT DO.

*Body of entry `(akk)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

- **(akk)** Filed 2026-09-14 from the restore-panel audit. **Record only - do not build.** Left in
  place for recover-panel parity; this records why the sentence is wrong, not an order to rewrite
  it mid-pass.

  ## WHERE IT SITS

  `app.js:startRestore`, the `onCancelled` arm. The invented line, pasted:

      Stopped. Names already applied stay; run again to finish.

  ⚠ **A line number would rot** (`(ago)`); the arm is the durable cite. Measured at filing as
  `static/app.js` around the `startRestore` / `runJob` call that posts `/api/restore/run`.

  ## WHY IT OVERSTATES

  Restore's job target is one `apply_documents` call (`service/restore.py:restore_run`). There is
  no per-name loop to cancel between, so a cancel cannot leave "some names already applied"
  mid-run the way organize or recover can leave files. The sentence assumes a mid-run partial
  apply the engine does not perform.

  ## WHY IT IS ALSO THE WRONG OWNER

  The product rule is that core owns reader wording (`RESTORE_WORDING`, `messages_for_restore`).
  This string is invented in the browser. Conflict and withholding lines on the same panel already
  come from the payload; the cancel line does not.

  ## WHY IT WAS LEFT

  Recover's preview cancel invents the same class of browser string (`app.js`, recover preview's
  `onCancelled`: *"Stopped. Nothing was copied."*). Rewriting restore alone would make the two
  panels disagree about who owns cancel copy. Filing, not fixing, until a pass owns cancel wording
  for both.
