# (aes) `status` SAYS "NEVER CHECKED" ABOUT A DRIVE IT JUST CHECKED AND FOUND WANTING.

*Body of backlog entry `(aes)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aes) THE SURFACE `(aej)` DID NOT REACH.** Found 2026-08-21 by soak two, S4.

  ## MEASURED

  Seven files deleted from drive B by hand; `verify B` reported `MISSING: 7` and named each. Then,
  in the same minute:

  - `drives` -> `B  2269  7  ...  LAST VERIFIED: checked, gaps` ✅ correct, and this is `(aej)`'s fix.
  - `status` -> **"Never checked: 'B'. Truestill has not looked since the copy was written."** ❌
    and the **next line** says *"Last checked: 2026-08-21"*.

  The catalog holds the evidence: **2,262 copies with a `last_verified`, 7 with a `missing_at`.**
  Truestill looked 2,269 times.

  ## ROOT CAUSE - TWO CORRECT FIXES THAT COLLIDE

  `drive.custody_freshness` decides `never_checked` from the **drive-level stamp** alone:
  `never = sorted(... for d in holding if not d["last_verified"])`.

  That stamp is deliberately **NULL when a verify finds gaps** - which is `(abg)`'s own fix, §4's
  thirty-sixth member: *derive the date from the evidence rather than stamp it beside the
  evidence*, so a run that found `missing: 2269` cannot date the claim today.

  So a NULL stamp now carries **two** meanings - *never looked* and *looked and found gaps* - and
  `custody_freshness` reads it as the first. `drives` derives from per-copy evidence and gets it
  right; `status` does not.

  ⚠ **`(aej)` was titled "THREE SURFACES STATED SOMETHING TRUE OF ONE POPULATION AS IF IT WERE
  TRUE OF ANOTHER".** This is a fourth.

  ## SCOPE, MEASURED

  It resolves once the drive is clean: restoring the 7 files and re-verifying cleared `missing_at`
  to 0, advanced the stamp, and `status` stopped saying it. **So the false sentence appears exactly
  while a drive has known gaps** - which is when a custody tool is being asked the question.

  ## NOT DECIDED

  - Whether `custody_freshness` should take the per-copy evidence (it currently takes drive rows
    only), or whether a third state belongs on the drive row. The first keeps one source of truth;
    the second is cheaper.
