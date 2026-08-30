# (aiv) THE FAILURE CAP COUNTS 2,519 REASONS FOR ONE FACT, WHICH IS THE DEFECT `(afd)` CLOSED.

*Body of backlog entry `(aiv)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-30 (P148, soak nine), **measured at scale**.

## WHAT THE USER SAW

`(aie)`'s injected run - `EPERM` at `copystat` for every one of 2,519 files, one condition
belonging to the mount - ended with:

```
  ... and 2,499 more METADATA NOT SET (2519 distinct reasons in total).
```

**There is exactly one reason.** The drive would not set timestamps, for the whole run.

## THE MECHANISM

`cli._reason_key` strips **quoted** fragments so per-file details collapse to their shared cause.
Both messages that reach the cap lead with the **source filename, unquoted**:

| producer | shape |
|---|---|
| `destinations/local._upload_failure` | `could not copy a.jpg to '…': there is no space left on the drive` |
| `drive_unwritable.metadata_not_preserved_note` | `a.jpg was copied to '…' and is safe, but this drive does not let Truestill set timestamps or permissions` |

Verified directly: `_reason_key` collapses **neither**. The path is stripped; the leading name
survives, and it differs per file.

## ⚠ THIS REOPENS `(afd)`'S OWN MEASUREMENT

`(afd)` records *"2,096 failures from one refused destination carry 2,096 distinct details,
because each names its own source and target - so counting them verbatim would report 2,096
reasons for one fact. **Stripping quoted fragments collapses them correctly.**"*

**Today it does not**, on either path. Whether the wording changed under the guard - `(aep)`
rewrote `_upload_failure` to remove two §9 violations, and `(aie)` added the second producer in
P142 - or the claim was never true of this shape, the entry's stated behaviour and the code
disagree now. That reconciliation belongs in whatever closes this.

## THE FIX SHAPE, NOT RULED

The honest options differ in where the cost lands:

1. **Quote the leading name** in both producers, so the existing key strips it. One character each,
   and it makes the sentence read like the rest of the product's quoting convention.
2. **Key on something structural** rather than on prose - the `errno`, or `Unwritable`. This is
   what `(aep)` parks as *"whether `detail` should be structured rather than free text"*, and it
   is the answer that stops the next wording change from breaking the count again.

⚠ **(2) is the root cause and (1) is a two-character patch of a text heuristic.** `_reason_key`'s
own docstring already calls itself *"an approximation over a string, and it is one because
`detail` is a string"*. This entry is evidence for `(aep)`, not a reason to keep sharpening the
approximation.

## WHY IT RANKS WHERE IT DOES

Nothing is lost and nothing is mis-copied - the files are safe and recorded, which is `(aie)`'s
whole point. **The harm is a user reading "2519 distinct reasons" and concluding their drive has
2,519 different problems** when it has one, with one remedy.

## RELATED

`(afd)` (the cap, and the measurement this contradicts), `(aep)` (structured `detail`), `(aie)`
and `(ain)` (the second producer), [`soak-nine-record.md`](../../soak-nine-record.md) §6.
