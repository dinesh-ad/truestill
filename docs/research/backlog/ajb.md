# (ajb) `rescan` HOLDS THE RECORDED SIZE AND STATS THE REAL ONE, AND COMPARES NEITHER.

*Body of entry `(ajb)`, **shipped 2026-08-31** - the closure is in [`SHIPPED.md`](../../SHIPPED.md);
the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

Filed 2026-08-31 (P166, soak eleven), measured. The run is
[`soak-eleven-record.md`](../../soak-eleven-record.md).

## MEASURED

After a physical mid-write pull left **836 files at zero bytes** against a catalog recording
3.5 MB each:

```
  in place           : 2538, where the catalog says they are     <- all 836 are in here
  NOT ACCOUNTED FOR: 2
  LEFT BEHIND BY TRUESTILL: 1
  time taken         : 0.28 s
```

**`rescan` called 836 destroyed photographs "in place".** It is not wrong about where they are.

## THE PREMISE, CHECKED RATHER THAN ASSUMED

| fact | check |
|---|---|
| the catalog records a size for every copy | **2,540 of 2,540** `file_copies` rows have a non-null `size` |
| the walk already stats | it enumerates the drive; 0.28 s for 2,540 files |
| **the size never reaches the classifier** | `reconcile()` takes `on_disk: Collection[str]` - **paths only** - and its docstring says *"Pure: no I/O"* |

**A size comparison would have caught 836 of 839 damaged files in that same 0.28 s, reading not
one byte.**

## ⚠ SCOPE, MEASURED ACROSS THREE FILESYSTEMS - THIS IS NOT UNIVERSAL

**The gap exists only where the filesystem KEEPS the directory entry.** Measured under the same
physical mid-write pull on the same stick:

| | exFAT | NTFS (`ntfs3`) |
|---|---|---|
| what the interruption left | **zero-byte files that still exist** | entries that **refuse every read** |
| `rescan` caught, today's code | **2 of 838** | **304 of 304** |
| would a size comparison add anything? | **yes - 836 more** | **no** |

**On NTFS the journal rolls the incomplete entries out of existence**, so `NOT ACCOUNTED FOR`
already catches every one and this entry proposes nothing. **A missing file is honest; a zero-byte
file is a lie**, and only the lie needs a second instrument.

🔑 **So the claim is: `rescan` is blind to an interrupted write ON A FILESYSTEM THAT KEEPS THE
DIRECTORY ENTRY** - exFAT and FAT32, which is what removable media is overwhelmingly formatted as.
Filed narrower than first written, because the first version would have read as universal and been
wrong on the one filesystem with a journal.

## 🔑 THE ARGUMENT THAT MAKES THIS MORE THAN A CONVENIENCE

**The filesystem's own checker structurally cannot find this.** `fsck.exfat` on the same volume:

```
/dev/sda1: corrupted. directories 56, files 1906
/dev/sda1: files corrupted 1, files fixed 0
```

It found the **one** genuinely incoherent entry and was blind to the **836**. It had to be:
**those files agree with themselves** - directory entry says 0 bytes, allocation says 0 clusters,
and `st_blocks = 0` confirms it. There is nothing inconsistent to detect. **Only the catalog,
which lives outside the filesystem, knows they should be 3.5 MB.**

So this is not *"`rescan` could be more helpful"*. **It is the only instrument that can hold both
numbers at once**, and it is discarding one of them.

## ⚠ AND THE DISCLAIMER TALKS THE USER OUT OF IT

`rescan` prints, every run:

> *"Silent damage to a file changes neither its name nor its size, so only `truestill verify` can
> find it - that reads every byte and this reads none."*

**True of bit-rot. False for what an interrupted write actually produces**, which is the accident
this product exists on removable media to survive: 3,554,132 bytes became **0**. It is the sentence
a user reads when deciding whether the fast check was enough, and it sends them away.

## THE COST OBJECTION IS ALREADY ANSWERED BY OUR OWN MEASUREMENT

Metadata on a cloud mount is **~free** while content reads at **3.9 MB/s** - which is why the
`PLACED` rule reads nothing. **A size check stays inside that rule**: it is one `stat`, on a walk
that already stats.

## THE COUNTER-EXAMPLE, BECAUSE THE PRODUCT ALREADY DOES THIS WELL ELSEWHERE

The same report's `.partial` line:

> *"a run was interrupted while writing these - a disk that filled, **a drive pulled out**, the
> process killed. They are not your photos: delete them."*

**That names this exact accident and gives the remedy.** The gap is not the product's voice; it is
one comparison it declines to make.

## WHAT IS NOT ESTABLISHED

- **Which bucket a size mismatch belongs in.** It is not `moved`, not `unaccounted`, not `stray`.
  A fifth bucket is a report-shape decision and `reconcile()`'s buckets are *"derived by
  subtraction rather than by a second rule, so they cannot overlap or leave a gap"* - **that
  discipline must not be broken to add this**, and how to add it without breaking it is unruled.
- **Whether `reconcile` should stop being pure.** It need not: the caller can pass sizes alongside
  paths, keeping *"no I/O"* intact. **Not obviously the right shape, and not decided here.**
- **A zero-length file is not always damage.** A user's own 0-byte file is legitimate; the claim is
  only that it **differs from the recorded size**, which is what makes the comparison safe.

## RELATED

`(aja)` (the re-run that repaired nothing this would have found), `(aiz)`, `(abn)` (repair),
[`soak-eleven-record.md`](../../soak-eleven-record.md) §5 and §6.
