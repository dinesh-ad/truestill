# (aiy) TWO REGISTRATIONS ON ONE PHYSICAL DEVICE ARE REPORTED AS "NICELY REDUNDANT".

*Body of backlog entry `(aiy)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-31 (P165, soak ten), **measured on real removable media** rather than reasoned about.
The run is [`soak-ten-record.md`](../../soak-ten-record.md).

## MEASURED, VERBATIM

Two drives were registered in two folders of **one** USB stick - `soak10/drive` and
`soak10/backup` on DAMON_16GB - and 356 files were backed up from the first to the second. The
stick was then **physically removed**. With no copy of anything reachable:

```
$ truestill status --db …
All catalogued content has at least two drive copies. Nicely redundant.
Last checked: 2026-08-31 (the oldest of the drives holding copies).
```

**Both copies were on one device, and that device was in a drawer.**

## THE PREMISE, CHECKED RATHER THAN ASSUMED

`st_dev` occurs **16 times** across `packages/*/src/`. Every one is in
`service/organize.py`'s same-filesystem guard for `--in-place` (via `service/path_probe.py`'s
`nearest_device`) or in `run_health.py`'s `DeviceReading`. **`drive.py` never asks.** So the
product already knows how to ask which device a path is on, and asks it for a **rename guard** but
not for the **redundancy claim**.

⚠ **The negative is the falsifiable half and it is one command**:
`grep -rn "st_dev" packages/*/src/` - a hit inside `drive.py` or the status path refutes this
entry.

## WHY IT RANKS SECOND IN SOAK TEN, BEHIND `(aiz)`

Both are the product being wrong about safety. **`(aiz)` misleads about safety being achieved
right now** - the copy you are watching is not yet on the medium. **This one misleads about safety
you already have**, which is quieter and lasts longer: a user who reads *"nicely redundant"*
stops looking for a second device, and nothing will correct them until the first one fails.

## WHY IT MATTERS, AND WHY REMOVABLE MEDIA IS WHERE IT BITES

3-2-1 is *"three copies, on two media, one off site"*. `status` is the product's whole answer to
the first two, and it counts **registrations**. A registration is a folder with a
`.truestill-drive.json` in it, and nothing stops two of them sharing a volume, a partition table
or a physical enclosure.

**A user backing up "to my other drive" and pointing at another folder on the same stick is the
ordinary case, not a contrived one** - it is what `soak10` did without meaning to, and the product
congratulated it. When that stick fails, both copies fail together and the last thing the user was
told is that they were *"nicely redundant"*.

## WHAT IS NOT ESTABLISHED

**How far the check should reach.** `st_dev` distinguishes two mounts; it does **not**
distinguish two partitions of one disk, two disks in one enclosure, or two folders reached through
different mount points of the same device. Each is a strictly stronger claim than the last and a
strictly more expensive one, and this entry rules none of them.

⚠ **And whether it should refuse or merely say so.** Refusing to register a second drive on a
device that already carries one would stop a legitimate case - staging a library before it moves
to a real second drive. **Saying it plainly in `status` costs nothing and loses nothing**, and is
the cheaper half; it is not obviously the whole answer.

## WHAT WORKED IN THE SAME MEASUREMENT, SO THE ENTRY IS NOT READ AS A VERDICT ON THE COMMAND

With the stick gone, `drives` reported both as **offline** correctly, and `verify` on the vanished
path refused with a named remedy, exit **2**, and a warning against the mistake that would compound
it - *"Do NOT register the folder again while the drive is disconnected - that creates a second
drive id for a library you already have."* The reporting around this is good. The redundancy claim
is the one sentence that is not.

## RELATED

`(abd)` (one catalog or many - the same question about a different noun),
[`soak-ten-record.md`](../../soak-ten-record.md) §6.
