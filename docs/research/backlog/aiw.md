# (aiw) `undo-organize` EMPTIES FOLDERS AND REPORTS NONE - `(afi)`'S THIRD PATH.

*Body of backlog entry `(aiw)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-30 (P148, soak nine), measured on the reversal arc soak eight never reached.

## MEASURED

An `--in-place --apply` run moved **666 files by rename**, then `undo-organize --apply` restored
all 666 and left the tree **path-identical** to the original - 1,900 files before and after. The
reversal is correct.

It also left **90 empty directories**, and said nothing about them:

```
Restored 666 file(s) to their original locations.      <- the whole of what it says
$ find Lib -type d -empty | wc -l
90
```

The **same run's** organize had printed both halves of the promise:

```
Empty folders left behind are reported, never deleted.
1 folder(s) are now empty. Review and remove them with:
  truestill clean-empty …
```

So one command states the policy and honours it; its inverse honours neither, on a tree where the
number is **ninety times larger**.

## ⚠ THIS IS `(afi)` EXACTLY, ONE PATH FURTHER ON

`(afi)` found `_offer_cleanup` wired into `migrate-layout` alone, while organize's own banner
promised the report - *"the comment below claimed an offer 'follows' that did not exist on this
path"*. That was fixed for organize. **`undo-organize` is the third path that empties folders**,
and it was not covered then because the reversal arc had never been run at a scale where it shows.

**A moving operation empties the folder it moved out of. Every one of them.** That is the class,
and it is now two instances against one guard.

## THE FIX SHAPE, NOT RULED

`cli._run_pipeline` already computes `emptied_folders` and prints the offer under `--apply`. The
undo handler needs the same two things: count what it emptied, and name `clean-empty`. ⚠ **Not by
copying the block** - two copies of the offer is how the wording drifts. The count and the
sentence want one home, which is the shape `(aim)` and `(aie)` both landed on.

⚠ **And a completeness question the fix should answer rather than dodge**: whether a *third*
caller can appear without inheriting it. `_offer_cleanup` reaching two of three paths for months
is the evidence that it can.

## WHY IT RANKS LOW

Nothing is lost - empty directories are inert, the reversal itself was exact, and `clean-empty`
exists and works. **The harm is a promise printed in one breath and broken in the next**, on the
command a user reaches for when they are already unhappy.

## RELATED

`(afi)` (the same offer, the first two paths), `clean-empty`,
[`soak-nine-record.md`](../../soak-nine-record.md) §3 and §6.
