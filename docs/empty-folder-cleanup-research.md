# Cleaning up the folders a migration emptied - recon + design

Status: **Decided and shipped (2026-07-28).** `truestill clean-empty`.

A layout migration moves every file out of the old tree and leaves the tree behind, because
truestill never deletes a folder. After migrating two real drives that is a `Camera/` skeleton
on each: correct, and unpleasant to look at. This records what other tools do about it, what
they get wrong, and the rules this one is built to.

---

## 1. What the surveyed tools do

**`emptydir`-class utilities** enforce a **junk-only rule**: a directory counts as empty if it
contains nothing, *or* only files from a small named list of operating-system detritus. The rule
is deliberately narrow - the list is enumerated, not inferred - because the moment "looks
unimportant" becomes a heuristic, the tool starts deleting things it cannot name.

**`4dots`-class cleaners** add two behaviours worth copying: deletions go to the **recycle
bin** rather than being unlinked, and **zero-byte files** are treated as removable alongside the
named junk. Both are recoverability features: the first makes a mistake reversible, the second
avoids leaving a directory alive for a file with no content in it.

**The paid market is the evidence of need.** Several of these ship as commercial products with
active user bases, which is a strange thing for `rmdir` to be sold as - it means people
routinely face folder skeletons they do not trust themselves to delete by hand, and will pay
for something that decides safely. truestill *creates* that skeleton, so it owns the cleanup.

## 2. What they get wrong, and the rule that follows

The failure mode across the category is **scope**: a general "find empty folders on this drive"
sweep. It finds directories the tool never created, never touched, and knows nothing about - an
empty folder a user made deliberately as a placeholder looks identical to a migration leftover.

**So the scope here is the journal, not the filesystem.** Only folders the migration record
shows truestill *emptied* are candidates. A drive-wide sweep is never offered, in either mode.
That single decision removes the entire class of "it deleted a folder I wanted".

## 3. The three tiers

Per candidate folder, bottom-up:

| Tier | Contents | Action |
|---|---|---|
| **truly empty** | nothing | removable |
| **junk-empty** | only entries from `JUNK_NAMES`, or zero-byte files | removable, junk and all |
| **occupied** | anything else, however small or hidden | **left alone, listed with its contents** |

**Unknown is never junk.** A folder holding one unrecognised dotfile is reported with that file
named, not removed. `JUNK_NAMES` is a named constant with a doc comment; extending it is a
deliberate edit someone has to justify, not a pattern that quietly grows.

**Bottom-up matters.** A migration empties `Camera/2013/09/`, which leaves `Camera/2013/` and
then `Camera/` empty in turn. Processing leaves first lets each newly-empty parent collapse in
the same pass; top-down would inspect a parent that is not empty *yet* and stop.

## 4. Trash, and being honest when it is unavailable

Deletions go to the OS trash where the platform supports it. `send2trash` is **not** a
dependency: adding one to `truestill-core` for a cleanup command fails the §7 test, and the
repo already has a graceful-degradation precedent in `pillow-heif`. So the trash backend is
resolved at runtime - `send2trash` if the user has it, else the `gio trash` command on Linux
desktops - and when neither is available the preview **says so in the confirm prompt**, so the
typed word is given in full knowledge that removal is permanent. Never a silent permanent
delete.

## 5. Rejected alternatives

- **Sweep the drive for empty folders.** The category's standard behaviour and its standard
  bug. Rejected for the scope reason above.
- **Delete the skeleton automatically at the end of a migration.** The migration already asked
  for one typed confirmation; silently widening what that word authorised is exactly the kind of
  scope creep the copy-only invariant exists to prevent. Cleanup is *offered*, and confirmed
  separately.
- **Infer junk by size or extension.** "Small files are probably junk" deletes someone's
  `notes.txt`. The list is named or the feature does not ship.
- **Recursive `rmdir` and swallow the error.** Works, reports nothing, and cannot distinguish
  "left alone because occupied" from "failed" - the user learns nothing about their own drive.

## 6. Complexity

One bottom-up walk over the affected subtrees: **O(folders)** with a directory listing each, and
the junk check is a set membership test per entry. No hashing, no recursion into folders the
journal does not name, and nothing proportional to library size beyond the leftovers themselves.
