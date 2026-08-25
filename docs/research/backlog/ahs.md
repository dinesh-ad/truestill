# (ahs) NO READ-ONLY PATH REBUILDS THE INVENTORY AFTER A LOST CATALOG.

*Body of backlog entry `(ahs)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahs) NO READ-ONLY PATH REBUILDS THE INVENTORY AFTER A LOST CATALOG.** Filed 2026-08-25
  (P98, soak six). **A product ruling, filed rather than ruled here.**

  ## THE DRILL, AND WHAT EACH PATH RETURNED

  Soak five's organized library - 10,710 files, 28 GB, ext4 - catalog moved aside, rebuilt from
  the files alone:

  | path | result |
  |---|---|
  | `truestill restore <drive>` | **drive identity only**: 1 drive, 1 setting, **0 files, 0 copies** |
  | `truestill rescan <drive>` | 30.1 s. Reports all **10,710 as "ON THE DRIVE, NOT IN THE CATALOG"** |
  | `attach_drive` (the app's walker) | 31.5 s. **`linked=0`, `unmatched=10710`** |
  | re-organize | rebuilds the rows - and is a full read of every file |

  **`attach_drive` links a file on the drive to a `files` row by content.** With the `files` table
  empty there is nothing to link to, so the walk that exists to rebuild custody rebuilds nothing.
  That is not a defect in it; it is what it is for.

  ⚠ **`rescan`'s own closing sentence is honest, and is also the whole gap**: *"No command repairs
  any of the above yet. This one only tells you."* The product says exactly what it does not do.

  ## WHY THIS IS WORTH A LETTER

  Every 2026 comparison of Immich, PhotoPrism and Nextcloud Memories records the same failure -
  paths, albums and metadata live in a database that re-scanning does not rebuild, so restoring
  files without the matching dump yields orphaned photos and an empty timeline. Their remedy is
  *"dump the database first."* **Truestill's pitch is the opposite**, and the drive document exists
  to make it true.

  Measured, the claim holds **in substance and not in reach**: the facts are all in the files, and
  only the longest operation in the product recovers them. A user who loses a catalog is told, by a
  read-only command, that every one of their photos is unknown - and the next step is to re-organize
  a library that is already organized.

  ## WHAT THIS ENTRY DOES NOT DECIDE

  Whether that is acceptable. It may be: a re-organize is safe, idempotent in placement, and a
  catalog loss is rare. **⚠ It is NOT idempotent in categorisation** - that is `(ahr)`, and it
  makes "just re-organize" a lossier answer than it looks.

  The options are a ruling, not a fix: teach `rescan` a `--rebuild`, have `attach_drive` create
  `files` rows from content when none exist, widen the drive document, or **write down that
  re-organize is the recovery path** and say so in the product where `rescan` currently says
  nothing repairs it.

  ## RELATED

  `(ahr)` (why re-organize is not a clean recovery), `(abm)` (the attach counts nobody saw),
  [`soak-six-record.md`](../../soak-six-record.md), `decisions-on-drive-research.md`.
