# (ajh) TRUESTILL CANNOT TELL A REMOVABLE DRIVE FROM A FIXED ONE, AND ALREADY READS THE LINE THAT SAYS SO

*Body of backlog entry `(ajh)`, under **Internal / tooling**. The index is
[`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-09-01, split out of `(ajf)` when its wording half shipped. **Not a defect** - nothing
is wrong today, because `(ajf)` put the condition in the sentence rather than in a gate. This is
the capability that would let a surface stop asking the user to decide.

## MEASURED: FIVE CHECKS, ALL NEGATIVE

| check | result |
|---|---|
| `grep -rn removable packages/*/src` | every hit is `cleanup.py`'s removable **folders**. Zero device hits |
| `/sys/block/*/removable` | **zero occurrences** in the tree |
| udisks2 / `GetDriveTypeW` | **zero occurrences** |
| `filesystem.parse_proc_mounts` | reads `/proc/mounts`, keeps **field 2 only** |
| the `drives` table | `uuid, label, first_seen, last_seen, last_verified, notes` - no device, no mount point, no filesystem |

🔑 **THE ANSWER IS ALREADY IN A LINE THIS CODE READS AND DISCARDS.** `parse_proc_mounts` walks
`/proc/mounts` and takes `fields[2]`, the filesystem type. **`fields[3]` is the mount options** -
where a removable volume's udisks-set flags live - and it is dropped on the floor. Whoever builds
this should not rediscover that; the walk is already paid for.

## WHAT IT WOULD COST, PER PLATFORM

| platform | mechanism | cost |
|---|---|---|
| **Linux** | `/sys/block/<dev>/removable` (a one-byte read), or the udisks2 `Drive.Removable`/`Drive.Ejectable` properties | cheap, but needs the mount -> device mapping `parse_proc_mounts` currently throws away (`fields[0]`) |
| **Windows** | `GetDriveTypeW` == `DRIVE_REMOVABLE`. One call, no subprocess - the same shape `_windows_filesystem` already uses for `GetVolumeInformationW` | cheap; the guard belongs **inside** the function for the `mypy`/`WinDLL` reason that function already documents |
| **macOS** | `statfs` `MNT_REMOVABLE`, or DiskArbitration | ⚠ **`filesystem.py` returns unknown on macOS by design** and states why: *"neither is worth a per-run cost"*. Any detection here inherits that, so **unknown must be a real answer**, exactly as it is for filesystem type |

## ⚠ WHAT IT MUST NOT DO, WHICH IS THE WHOLE RISK

**A filesystem-type proxy was already refused with a measurement** (`(ajf)`): it fires on an
internal Windows NTFS disk and stays **silent on an ext4 USB stick**. The silent-on-a-stick
direction is the dangerous one, and it is the case a user is most likely to be surprised by,
because they believe ext4 is the safe format. **Whatever this builds must fail toward saying the
line, never toward suppressing it** - `filesystem.stores_access_control`'s *"unknown means yes"*
is the precedent, and it states the rule in its own docstring.

## WHAT THIS UNBLOCKS, AND WHAT IT DOES NOT

- **Unblocks**: `(ajf)`'s sentence could drop its *"If this drive unplugs"* clause where the answer
  is known, and keep it where it is not.
- **Does NOT unblock**: nothing about durability. Knowing a drive is removable does not flush it.
- ⚠ **It is not obviously worth doing.** The sentence works today without it, on every platform.
  This entry exists so the option is priced, not because the wording is inadequate.

## RELATED

`(ajf)` (the wording, shipped), `(aiy)` (two registrations on one physical stick - the other
question the `drives` table cannot answer for want of a device),
[`soak-ten-record.md`](../../soak-ten-record.md), [`soak-eleven-record.md`](../../soak-eleven-record.md).
