# (ajc) `ntfs3` ACCEPTS EVERY NAME WINDOWS REFUSES, SO A DRIVE IS WRITTEN ON LINUX AND BREAKS WHEN IT MOVES.

*Body of backlog entry `(ajc)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-31 (P166, soak eleven, pass 2), **measured on a real NTFS volume**. The run is
[`soak-eleven-record.md`](../../soak-eleven-record.md).

## ⚠ IT IS NOT `(aid)`, AND THE DIFFERENCE IS THE WHOLE ENTRY

`(aid)` is *"a name that **refuses at write time**"* - the copy fails, the user is told, nothing is
lost. **This is a name that writes fine and breaks later**, on another machine, with no error
anywhere in between. **Different mechanism, different moment, different remedy**, and its home is
[`moving-machines.md`](../../moving-machines.md) rather than `layout.py`'s refusal set.

## MEASURED

`/dev/sda1` freshly formatted NTFS, mounted by udisks2 as **`ntfs3`, the KERNEL driver** - not
`ntfs-3g` FUSE, and no `ntfs-3g` process exists - with
`rw,nosuid,nodev,relatime,uid=1000,gid=1000,**acl**,iocharset=utf8,prealloc`.

| name | ext4 | exFAT | **NTFS (`ntfs3`)** | Windows Win32 |
|---|---|---|---|---|
| `Trip: day 1.jpg` | OK | **REFUSED `EINVAL`** | ⚠ **created verbatim** | refuses |
| `photo?.jpg`, `a*b.jpg`, `pipe\|name.jpg` | OK | **REFUSED** | ⚠ **created verbatim** | refuses |
| `report<v2>.jpg`, `say"hi.jpg`, `back\slash.jpg` | OK | **REFUSED** | ⚠ **created verbatim** | refuses |
| trailing dot `photo..jpg.` | OK | silently stripped | ⚠ **kept verbatim** | stripped/refused |
| case sensitivity | sensitive | **INSENSITIVE** | ⚠ **SENSITIVE** | insensitive |

🔑 **`(aid)`'S CENTRAL CLAIM IS MEASURED FALSE.** It says these names *"are legal on ext4 and
**refuse on NTFS**"*. On a real NTFS volume they do not refuse. **exFAT is the strict filesystem
and NTFS-under-Linux is the permissive one** - the reverse of the assumption both entries were
built on. `(aid)`'s reproduction on 2026-08-30 came from **exFAT** behaviour, not from anything
NTFS-like, and its Windows `xfail` has been aimed at the wrong premise since 2026-08-29. Corrected
in place there.

## THE HAZARD, WHICH IS ONE-WAY AND ONLY APPEARS WHEN THE DRIVE MOVES

A Linux user organizes onto an NTFS external drive. `ntfs3` writes `Trip: day 1.jpg` without
complaint, `verify` passes, the catalog is correct, everything is consistent. **They carry the
drive to Windows** - which is the entire point of choosing NTFS - and the Win32 layer will not open
the name.

**Case is the same shape and quieter**: two photographs whose organized names differ only in case
are two files here and **one name on arrival**.

⚠ **Nothing in the product is wrong at the moment it writes.** That is what makes this hard: there
is no error to report, no failed copy, no bad row. The damage is created by a **future event on a
different operating system**, and `moving-machines.md` is the document that exists for exactly that
event.

## 🔑 WHAT THE FIX IS **NOT**, BECAUSE THE OBVIOUS ONE IS WRONG

**Refusing the eight characters everywhere would be wrong.** They are **legal on ext4**, which is
where this product runs and where most of a Linux user's library lives. Sanitising every name to
the strictest common set would rename files that were never going to travel, and
`(aid)`'s own "WHAT IS NOT ESTABLISHED" already refuses to sanitise the original name for a
narrower reason.

**The real question, named and deliberately not answered here:** *should a **destination that may
travel** be held to the strictest name set, and how would the product know which destinations
those are?* Candidate signals - the filesystem type, the drive being removable, an explicit
"this drive travels" flag on the drive record - are all plausible and none is measured. ⚠ **A soak
does not get to make that ruling**, and this entry does not.

## WHAT IS NOT ESTABLISHED

- **The Windows half is still unproven from here.** No lane on this machine can ask Win32 to open
  `Trip: day 1.jpg`. This measurement **narrows what the Windows `xfail` must prove** - the
  refusal is at OPEN time on Windows, not at write time on Linux - and does not replace it.
- **`ntfs-3g` was not tested.** udisks2 chose `ntfs3`; the FUSE driver is installed and may differ,
  and Q1050 exists because the two behave differently.
- **Whether Windows refuses or mangles.** Refusal, truncation and a `?` substitution are three
  different outcomes for the user and this entry measured none of them.
- **`prealloc` and `acl`** were in the mount options and their effects were not isolated.

## RELATED

`(aid)` (the refuse-at-write-time entry whose premise this corrects),
[`moving-machines.md`](../../moving-machines.md) (this entry's home),
[`filename-safety-research.md`](../../filename-safety-research.md) (correct about token values,
silent about this), [`soak-eleven-record.md`](../../soak-eleven-record.md) pass 2.
