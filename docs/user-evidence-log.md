# User evidence log - what people actually lose, and what they expect

**A RECORD. Started 2026-08-23, kept as observed, never rewritten** - corrections go beside it,
dated, the way the soak records are treated.

**This is evidence, never rules.** It makes no claim about Truestill's code and it has no numbered
section. Where a line touches the product it is phrased as a question, and where the repo has since
answered one the answer is recorded beside it rather than folded in. `IMPLEMENTATION_STANDARDS.md`
remains the only binding document.

**Method.** Forum evidence is worth more than blog guidance because it records what actually failed
for someone, in their own words, with the tool's own response quoted back. Search for the failure,
not the feature. The most useful threads are the ones where a user is panicking and an expert
answers *"you should never have done that"* - because that sentence usually marks a product's
unsolved problem, and sometimes a whole product's reason to exist.

**Engineering prior art already cited inside `(afw)`, `(agi)` and `(agj)` is deliberately not
repeated here**, to avoid a second authority.

---

## 1. The closest real-world match to `(agk)`

**Lightroom Classic, Adobe community, Sept 2018.** A user moved photos between folders. The move
stalled partway. They clicked the X to cancel, expecting to restart. The files were then
unreachable: thumbnails still visible in the catalog, nothing in the folder on disk, every edit
option greyed out, and the tool reporting that all selected files were missing.

**Why it matters.** This is `(agk)`'s shape in a shipping product with millions of users: an
interrupted move, after which the catalog and the disk disagree about where the photographs are.
Our own reproduction scored 2 orphans in 8 kills. **This is what those 2 look like to the person
they happen to.**

**And the user did nothing wrong.** They pressed cancel. A cancel that leaves files unreachable is
a defect, not user error, and any warning copy must not imply otherwise.

## 2. The custody claim has to be literally true

**Photoshop Elements, Adobe community, Sept 2024.** A user imported from an SD card for four years
believing files were being moved to their hard drive, because their preferences said so. At some
point the import silently began leaving them referenced on the card. They wiped the card and lost
photographs of a newborn grandchild. Thumbnails displayed correctly throughout.

**Why it matters.** A thumbnail is not custody. A catalog row is not custody. The product's own
statement about where a file is must be checkable against the disk, and when it cannot be checked
it must say so rather than display confidently.

> **Attached to `(abf)`** - *"a fix does not retroactively clean what it prevented"*, whose
> reassured-state-has-no-staleness argument reads as theoretical until this case sits next to it.

## 3. "Reconnect" is the operation everyone needs and nobody has

**Photoshop Elements, multiple threads 2017-2023.** Files moved or renamed outside the tool produce
mass "missing file" states. The standard advice is a reconnect dialog; repeatedly, users report
reconnect selecting the file and the location never updating. One user's fix was to delete every
catalog and start over, losing all their tagging work. Another expert's advice is blunter: moving
files outside the organizer should never be done.

**Why it matters.** *"Never move your files"* is not an acceptable constraint on a person's own
disks, and it is the opposite of Truestill's premise that files stay readable without the tool.

> ⚠ **CORRECTION, 2026-08-23, made when this document was committed.** The working draft said this
> *"maps to `(yy)` in the backlog"* and that its priority was understated. **`(yy)` is not a
> backlog letter - it SHIPPED on 2026-08-02** as `truestill repoint-sources OLD NEW`
> (`SHIPPED.md`). The evidence still lands, harder and somewhere else:
> `docs/cli-app-parity.md` records `repoint-sources` as having **no app route**, so the operation
> the incumbent's users complain about most is CLI-only here. That is the gap this evidence
> argues about, not the letter.

## 4. The market gap, stated by the incumbent's own experts

**Lightroom Classic, Adobe community, 2017 and 2023.** Asked how to reorganize an existing library
into dated folders, the community answer is repeatedly **don't** - leave the files where they are
and use keywords and filter bars. One expert advises against it explicitly if it involves large
amounts of moving; another says it can only be done manually.

**Why it matters.** The operation Truestill exists to perform is one the mature tools consider too
dangerous to offer, so their advice is to stop wanting it. **That is the gap, and it is also the
standard being set**: if reorganizing is offered at all, the reversal has to actually work, or the
incumbents' advice was correct.

## 5. Safety is a marketed feature, not a background quality

- **Photo Renamer** (Windows, discontinued) led its description with the promise that it will not
  touch your original photos, and copies them instead.
- **photo_reorganize** (GitHub) builds a parallel tree of hardlinks so the organized structure
  costs no extra disk and the originals are never modified.
- **imgfiler** (GitHub) documents that the destination may be the same directory as the source,
  treating in-place as a first-class option.

**Why it matters.** All three answers to *"I have no spare disk"* exist in the wild: copy, hardlink
shadow tree, in-place. We chose in-place. That is defensible, and it is the riskiest of the three,
which sets the bar for the journal.

## 6. The in-place cohort is the one with no options

Not one thread, but the consistent shape behind the disk-space questions.

Someone choosing in-place is choosing it because they have no room for a second copy. So they also
cannot take a backup before running it, they have the least room for any safety net, and they are
the most likely to hit a full destination - which is `(agi)`'s condition. **The mode that most
needs a working undo is the mode whose users are least able to recover without one.**

> **Attached to `(agk)`** - this is why it was treated as a release blocker rather than a backlog
> item.

## 7. Reporting failure only through an exit code hides it

**BackInTime issue #1587.** Before 1.4.0, rsync errors surfaced only as exit codes and were
invisible in the interface, leaving users believing snapshots had succeeded when they had not.

Cited in `(afw)` as engineering prior art; kept here because it is **user** evidence, and because
it generalises: a failure the user is not shown did not happen, as far as they are concerned.

## 8. Users file "it kept going after the disk filled" as a defect

**rclone issues #6355 and #5308.** Users report that rclone does not terminate when the destination
is out of space, and ask for it to stop and return an error code. #5308 describes filling one drive
of a union and the transfer continuing to fail rather than stopping.

Cited in `(agi)`; kept here as the user-side confirmation that watcher-only behaviour is
experienced as a bug rather than a preference.

---

## Product ideas this evidence suggests - proposals, not decisions

Each needs checking against the repo before it becomes a letter. One already failed that check
(see §3), which is the reason for the rule.

1. **A find-orphans command.** After an interrupted run a user can have organized files with no
   catalog row and no journal row, and no way to find them among 33,000. A command that walks a
   destination and reports files that look organized but that nothing recorded would turn an
   unrecoverable situation into a list - and it is what would have helped the user in §1.
2. **Undo must report what it skipped.** Answered by `(afw)`'s undo stage; the forum evidence
   raises its weight, because *"Restored 27 file(s)"* while a file stays put is exactly the
   reassuring-but-false message that produced §2.
3. **Warning copy for in-place should say what is and is not at risk.** A rename never destroys
   data. What an interrupted in-place run costs is the knowledge of **where a file came from**, not
   the file. That distinction is honest, reassuring, and more useful than a generic
   *"this cannot be undone"*.
