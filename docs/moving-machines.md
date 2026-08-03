# Moving Truestill to another computer

Plain steps for taking your libraries and catalog to a new machine (or a new home
folder / mount point) without losing custody of your photos.

---

## What you do not have to relink

Adobe Lightroom Classic stores **absolute** paths to every photo (including Windows
drive letters). After you move a library to a new computer or drive letter, the usual
result is question marks on every folder and every photo. The published advice is
literally "do not panic," then walk Find Missing Folder / reconnect paths until the
catalog matches the new location.

Truestill does not work that way for the copies it organizes onto a drive. Those
locations are stored as **paths relative to the drive**, keyed by the drive's marker
uuid (the small `.truestill-drive.json` file at the drive root). When the same marked
tree lands somewhere else, custody is still intact: no question-mark grid, no
relinking pass, no reconnect step for the organized copies. Point Truestill at the
new folder, verify, and move on.

That is the important thing **not** to worry about on the new machine. The rest of
this page is about the catalog file, the marker, and a few absolute paths that are
*not* part of that custody model (old source folders for reclaim, undo roots, UI
prefills). Those need care; your organized library copies do not.

---

## What to copy

1. **Every library drive root**, including the small marker file at the top of that
   folder: `.truestill-drive.json` (older drives may still have `.vaeon-drive.json`
   instead - copy that too). Copy the whole tree, marker included.

   **Do not copy a photo library without its marker.** Without that file, Truestill
   treats the folder as unregistered. Someone may then run "init drive" and create a
   *new* identity. Your catalog still points at the *old* identity, so every recorded
   copy of every photo looks orphaned - as if the backups never existed. That is the
   worst failure mode of a move. The marker is what ties the folder to your catalog;
   the photos alone are not enough.

2. **Your catalog file** - the SQLite database Truestill keeps of which drive holds
   which copy (often named `catalog.sqlite`). Copy the file you actually use, not a
   random empty one from a fresh checkout.

You do **not** need the speed cache that sometimes sits beside the catalog
(`catalog.cache.sqlite`). Skipping it is fine; see "First preview is cold" below.

---

## Order that works

Do these in this order. It matches how Truestill expects things to look.

1. **Copy the drives** (with markers) onto the new machine or mount.
2. **Copy the catalog** to a stable place on the new machine.
3. **Install Truestill** on the new machine.
4. **Open the new drive folders** (browse to them; see below).
5. **Verify** each drive so Truestill re-checks the copies under the new location.
6. **Only then** run migrate, backup, or trips & events work.

Skipping verify and jumping straight into migrate or backup makes it harder to tell
copy damage apart from a wrong folder.

---

## Always say which catalog

Pass `--db` with the **absolute** path of the catalog you copied, for both the CLI
and the app. Example:

```sh
truestill status --db /home/you/Truestill/catalog.sqlite
truestill-app --db /home/you/Truestill/catalog.sqlite
```

If you omit `--db`, Truestill may open a different file relative to wherever you
happened to launch it - often an empty catalog that looks like your whole library
vanished.

On startup, Truestill prints which catalog path it opened. Read that line. If it is
not the file you copied, stop and pass the right `--db`.

---

## Do not trust old paths in the UI

After a move, fields that still show your *old* home path, old mount, or locked
folder are wrong. **Browse** to the new location for each drive and backup target.
Do not click through on a prefilled path that still mentions the previous machine.

---

## Undo after a move

If you need to undo an in-place organize that ran on the old machine, tell undo where
the folders live **now**:

```sh
truestill undo-organize --db /absolute/path/to/catalog.sqlite \
  --source-root /new/path/to/library \
  --dest-root /new/path/to/library
```

(Use two different paths if source and destination were different.) Without those
flags, undo looks for the old absolute paths stored in the catalog and will refuse or
find nothing.

---

## First preview is cold

Truestill keeps a local speed cache of hashes and metadata next to the catalog. That
cache is keyed to paths on *this* machine. It does **not** travel usefully with a
move, and the ~170× warm speedup you may have seen on a second preview at home does
**not** apply on the new machine.

The **first** big "check for duplicates" / organize preview after a move is a full
cold run: every file is read again. On a network or cloud mount with a couple of
thousand photos, plan on **several minutes** (often around three to four). That is
work, not a hang - leave it running. Later previews on the *same* machine get fast
again once the cache rebuilds.

---

## If your desktop indexes files, exclude the cloud mount

**Linux desktops with `localsearch-3` (GNOME's tracker/indexer) will re-download a library you
just organized onto a cloud mount**, and nothing points at the cause. The indexer opens every
file under its roots to extract metadata, and *opening* a file on a cloud FUSE mount **downloads
it**. Organize into a mount inside `$HOME` and the indexer will quietly pull the whole library
back down behind you - filling the local disk, saturating the link, and looking exactly like
Truestill being slow.

**Excluding the directory did not stop it.** Measured on the affected machine:

| setting | result |
|---|---|
| `ignored-directories` including the mount | **+862 files in 5 minutes** - still indexing |
| `index-recursive-directories` narrowed to the XDG folders | **0 growth over 6 minutes** |

So set the roots, do not add exclusions:

```bash
gsettings set org.freedesktop.Tracker3.Miner.Files index-recursive-directories \
    "['&xdg-documents&', '&xdg-music&', '&xdg-pictures&', '&xdg-videos&']"
```

Check what is happening with `localsearch3 status` (or `tracker3 status` on older builds); the
file count climbing while nothing is running is the symptom.

**This is documentation, not a Truestill setting.** Truestill cannot see another program reading
the mount, and changing a user's desktop configuration on their behalf is not something a photo
organizer should do. The run health check added in `56bb6f3` will stop a run when this fills the
local disk, and will say the disk is full - which is true, and still will not name the indexer.
That is exactly why this page has to.

## What survives without repair

Once the markered drives and the right catalog are in place, these keep working
without rewriting anything:

- **Custody** - which drive uuid holds which copy (relative paths on that drive)
- **Dedup** - exact and look-alike matching against the catalog
- **Trips and events** already named and stored
- **Settings** such as layout templates and trip size preferences
- **Layout migration resume** - unfinished folder moves, as long as you point at the
  new drive root

What still needs your attention after a move is paths that lived on the old machine
(reclaim of old source folders, undo without `--source-root` / `--dest-root`, and
prefilled UI paths). Those fail loudly or ask you to browse - they should not silently
look "done" when nothing happened.
