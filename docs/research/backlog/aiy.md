# (aiy) A SECOND COPY ON THE SAME DEVICE COUNTS AS REDUNDANCY, AND IT GATES A DELETE

> ⚠ **REWRITTEN 2026-09-01 (P177) AFTER A CENSUS.** The title above replaces
> *"TWO REGISTRATIONS ON ONE PHYSICAL DEVICE ARE REPORTED AS 'NICELY REDUNDANT'"*, and the body
> below is new. **The original framed this as one sentence in `status`, and a reader who met that
> first would rank it as reporting.** It is not: the same count gates `truestill reclaim --apply`,
> which deletes the user's originals. The `status` sentence is the **symptom that revealed it**.
> The original reading is kept in §8 rather than deleted, because the correction is only legible
> next to it.

*Body of backlog entry `(aiy)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md);
the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-31 (P165, soak ten), **measured on real removable media**. Rewritten 2026-09-01
(P177) from the P176 census.

## 0. PROGRESS - TWO SURFACES DONE, FOUR TO GO

| surface | state |
|---|---|
| `reclaim`'s delete gate | ✅ **`e6ef82c`** - `ReclaimPlan.not_independent`, warned before the `delete originals` prompt |
| `status` | ✅ **P179** - `drive.library_independence`, wording from `drive.LIBRARY_REDUNDANCY` |
| `custody_floor` (the app's strip) | ⬜ reaches a screen |
| `stats_summary` (the Stats screen) | ⬜ reaches a screen |
| `list_drives` (drive cards, `drives.length`) | ⬜ reaches a screen |
| `app.js`'s unconditional literal | ⬜ reaches a screen |

⚠ **THE FOUR THAT REMAIN ALL REACH A SCREEN**, so they need the browser lane and should be **one
commit rather than four** - the same payload and the same wording home, and four separate screen
commits would run the 26-minute lane four times to answer one question.

⚠ **AND THE PREDICATE ITSELF WAS CORRECTED IN P179.** `e6ef82c` shipped
`copy_independence` testing *any duplicate device* rather than *fewer than two distinct devices*,
so `[7, 7, 9]` returned `NOT_INDEPENDENT` while the surface said *"every copy on ONE DEVICE"* -
false of that content. It over-warned and never under-warned, so nothing was unsafe; the fix is in
`drive.copy_independence` with the original rule quoted beside it.

## 1. 🔑 THE HARM: A DELETE GATED ON A COUNT THAT CANNOT SEE A DEVICE

`truestill reclaim --apply` - argparse's own help: *"actually delete sources (default: preview
only)"* - is guarded by one warning, `cli.py:4992`:

```python
    if plan.single_copy:
        print(
            f"  WARNING: {len(plan.single_copy)} file(s) would then exist in only ONE place "
            f"(raise --min-copies to exclude them)"
        )
```

`ReclaimPlan.single_copy` is `reclaim.py:62-64`:

```python
    @property
    def single_copy(self) -> list[ReclaimCandidate]:
        """Candidates whose content would exist in only one place after the source is freed."""
        return [c for c in self.candidates if c.copies <= 1]
```

and `copies` comes from `catalog.py:1661`:

```sql
                       (SELECT COUNT(*) FROM file_copies WHERE sha256 = f.sha256) AS copy_count
```

`file_copies` is keyed `(sha256, drive_uuid)`. **Two folders on one stick are two rows.
`copy_count = 2`, `copies <= 1` is False, `plan.single_copy` is empty, the warning does not print,
and `--apply` deletes the originals** - on the strength of a second copy that fails at the same
moment as the first.

**The warning exists for exactly this user and is silenced by exactly this defect.**

## 2. WHAT SOAK TEN MEASURED, WHICH IS THE SYMPTOM

Two drives registered in two folders of **one** USB stick - `soak10/drive` and `soak10/backup` on
DAMON_16GB - 356 files backed up from the first to the second, then the stick **physically
removed**. With nothing reachable:

```
$ truestill status --db …
All catalogued content has at least two drive copies. Nicely redundant.
Last checked: 2026-08-31 (the oldest of the drives holding copies).
```

⚠ **AND THE SENTENCE IS IDENTICAL IN ALL FOUR CASES**, which is a sharper statement of the defect
than *"it counts registrations"*. `single_copy_shas` reads `file_copies` rows with
`missing_at IS NULL`, and `missing_at` is set only by `verify` - `catalog.py:3212`: *"Remember that
we looked for this copy on a drive **that was there**, and it was not."* **Unplugging sets
nothing.**

| case | today |
|---|---|
| both online, separate devices | *"Nicely redundant."* |
| both online, **same device** | *"Nicely redundant."* |
| one offline | *"Nicely redundant."* |
| **both offline** (soak ten) | *"Nicely redundant."* |

**It does not vary with anything a user would care about.**

## 3. THE CENSUS - 17 SURFACES, SIX DENOMINATORS, ONE WITH NO QUERY AT ALL

**47 surfaces assert redundancy, a copy count, safety or custody. 35 are counting claims.
17 would be wrong for two folders on one stick**, including the `reclaim` gate above, the `drives`
table, the app's custody pips and tone, the Backups at-risk banner, and both drive cards.

**Six independent implementations of the same wrong denominator**, none able to see a device:
`single_copy_shas`, `single_copy_count`, `custody_floor`, `stats_summary`,
`reclaim_candidates.copy_count`, `list_drives` - plus `drives.length` in the browser
(`app.js:3058`).

⚠ **`app.js:1380` asserts redundancy with NO query at all:**

```js
    sub: "Your library now lives in more than one place."
```

An unconditional string literal on every backup completion. It is wrong here and structurally
wrong everywhere.

⚠ **AND `cli.py:2003`'s COMMENT IS FALSE ABOUT THE LEG IT NAMES:**

```python
        # The same rule the app's custody strip uses, from core, so the two surfaces cannot drift.
```

True of `custody_freshness`. **False of the redundancy verdict one line above it** - the strip
reads `custody_floor`, `status` reads `single_copy_shas`. Core says so itself, `catalog.py:2678`:

> The strip now uses :meth:`custody_floor`, which this method cannot replace: reading
> ``FROM file_copies`` makes a file with no copy row invisible here.

## 4. 🔑 THE DESIGN: `st_dev` CAN FALSIFY AND CAN NEVER CONFIRM

The capability exists - `destinations/base.py:33` `device_of(path) -> int | None`, one `stat`.
**But the codebase already records what it cannot do**, `local.py:213`:

```
        Device identity is never predicted -- ``st_dev`` can agree across btrfs subvolumes and
        bind mounts where a rename still fails. The kernel is asked, and its answer is final.
```

| direction | sound? |
|---|---|
| two roots share an `st_dev` -> **not independent** | ✅ soak ten's case exactly |
| two roots differ -> **independent** | ❌ two partitions of one disk, two disks in one enclosure, two mounts of one device |

**So the check can falsify redundancy and never confirm it. That asymmetry is the whole design**,
and it is why the answer is three states rather than a better boolean.

## 5. THE PRECEDENT IS IN THIS FILE'S OWN NEIGHBOUR, VERBATIM

`drive.py:136`:

> **Three states, not a boolean.** A boolean would have to fold ``UNKNOWN`` into one of the other
> two, and both folds lie. Read as connected it invents a drive that may not be plugged in; read
> as offline it tells someone their backup drive is missing when the truth is only that truestill
> has never recorded where it lives. **The alarming reading is the worse one for a custody tool,
> and the honest answer - *we do not know* - is available, so it is reported.**

`DriveReach` went from a boolean to three states for this reason. **The redundancy claim is still
a boolean.** `drive_reach` (`drive.py:708`) is called by `service/drives.py:598`, `bake.py:235`
and `cli.py:1118`; ⚠ **`_cmd_status` never calls it.**

⚠ **Silence is refused** on the same grounds: for a custody tool a user who reads nothing concludes
what one who reads *"redundant"* concludes.

## 6. WHAT IS **NOT** THIS ENTRY

- **Recording an identity that survives unplugging.** That needs a **filesystem UUID or volume
  serial**; it is **`(ajh)`-class platform work**, and ⚠ **`st_dev` cannot do it** - it is a
  mount-time kernel number, not a durable identity. **Comparing two connected roots is one stat,
  portable, and already written.**
- **Partitions, enclosures and bind mounts.** `st_dev` cannot see them; this entry claims only
  what it can prove.
- **Refusing to register a second drive on a device that already carries one.** It would block
  staging a library before it moves to a real second drive. A separate ruling.
- **The three divergent `missing_at` filters.** `single_copy_shas` and `custody_floor` exclude
  copies known absent; `stats_summary` (`catalog.py:2178`) does **not**, so three core helpers
  answer one question three ways. **Wrong today independent of any device question** - its own
  entry, not folded in here.

## 7. ⚠ A HARNESS CONSTRAINT, RECORDED WHERE A MEASUREMENT WILL MEET IT

The P176 probe resolved every drive's path hint and called `device_of` on each. One of them -
`Morrowkeep` - has a recorded hint under `/home/dinesh/pCloudDrive/`, so the probe **issued a
`stat` against a fenced path** before filtering. Nothing was read; the rule is *never read, walked
or stat'd, at any depth*.

🔑 **Any script probing drive hints must filter the fenced roots BEFORE resolving them**, and the
fence is **machine-local configuration the product does not know about**. `drive_reach` stats those
same hint paths in ordinary operation, so **the constraint binds harnesses, not code.**

⚠ **And the before/after diff on the real catalog is a NULL**: it holds **395 files on exactly one
drive**, so it never reaches the reassuring branch at all. **The regression cannot be measured on
real data because real data never triggers the sentence** - the acceptance criteria must be a
constructed case (two drives under one `tmp_path`, and two on genuinely different filesystems).

## 8. THE ORIGINAL READING, KEPT

As filed, this entry said the defect was that `status` counts registrations, ranked it **second in
soak ten behind `(aiz)`**, and reasoned:

> **`(aiz)` misleads about safety being achieved right now** - the copy you are watching is not yet
> on the medium. **This one misleads about safety you already have**, which is quieter and lasts
> longer: a user who reads *"nicely redundant"* stops looking for a second device, and nothing will
> correct them until the first one fails.

**That is still true and is no longer the worst of it.** The census found the same count standing
between a user and `reclaim --apply`.

It also recorded, correctly, what worked in the same measurement: with the stick gone `drives`
reported both as **offline**, and `verify` refused with a named remedy and exit **2**. **The
reporting around this is good; the count underneath it is not.**

## RELATED

`(abd)` (one catalog or many - the same question about a different noun), `(ajh)` (removability -
the platform work this entry is **not**), `(aap)` (the double-registration guard, which compares
content and not devices), [`soak-ten-record.md`](../../soak-ten-record.md) §6.
