# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to adhere to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **If you lose your catalog, your names come back from your drives.** `truestill restore <path>`
  reads the decisions file Truestill keeps on each drive and puts your trip and event names,
  dismissed groups and corrected dates back. It works on a brand-new machine with an empty
  catalog and nothing registered, which is the whole point of it. It **shows you what it would do
  first** and only acts when you type `restore`, and it tells you what it could *not* place -
  a name whose photos have changed, or a correction for a photo this computer has not scanned
  yet - rather than reporting only the good half.
- **Your drives now tell you what they are carrying.** Both `truestill drives` and the Backups
  screen say when each drive's copy was saved, when it is behind what is on this computer, when
  it holds names this computer does not have, and when a save to it failed - which is the first
  time a failed save has been visible anywhere.
- **Your names now live on your drives, so losing the catalog no longer loses them.** Truestill
  keeps a small file - `.truestill-decisions.json`, beside the drive marker at the top of each
  registered drive - holding **only what a person decided**: trip and event names, the drive's
  label, dismissed groups, and dates you corrected by hand. Everything else it knows is
  recomputable by reading your photos again; those names are not, because nobody but you ever
  knew them.
  It is written after any work that changed the catalog, to every drive that is plugged in, and
  it is **plain readable text** - you can open it in any text editor, on any machine, with
  Truestill nowhere in sight. That is the point of it. About a kilobyte.
  **The first time you run this version it saves a copy straight away**, so a library you
  finished naming months ago is covered without you having to rename anything, and it says so
  once. After that it is silent unless something goes wrong: a drive that is full, write-
  protected, or that already holds names this catalog does not have is reported rather than
  written over.
- **Naming a trip or event now suggests a name taken from your own folders.** If the photos in a
  group came from a folder you named - `Rock Climbing`, `Riverside Mall 2015` - Truestill offers that
  name under the box, with a **Use** button. It is only ever an offer: **the box stays empty until
  you click Use or type something**, so leaving a card alone still skips it exactly as before.
  Typing your own name puts the offer away.
  The suggestion is tidied but never invented. Apostrophes are dropped because they break shell
  scripts, `~` and `_` read as spaces, and a year that only repeats the year in the folder above
  is removed - `Wayanad '14` becomes **Wayanad**. Hyphens inside a name are left alone, so
  `TCS-M05-Batch` arrives as it is. **Nothing is spell-checked**: your places and people are not
  in any dictionary, and a confidently wrong correction would be worse than no suggestion at all.
  A group you have already named shows its name instead, and is never offered a suggestion.

### Fixed
- **Photos from an iPhone or a modern camera saved as HEIC are no longer shown on their side.**
  Some HEIC files record "turn this a quarter turn" in a way Truestill was reading but not
  applying, so the thumbnail came out landscape for a photo taken in portrait. Photos that were
  already the right way up are untouched - the fix can tell the two apart.
- **Setting up a new drive on a full disk now tells you so, instead of crashing.** Pointing
  `organize` at a folder that is not a drive yet, on a disk with no room, used to end in a Python
  stack trace - a few steps from a copy that would have named every file it could not write.
  Truestill now checks that the drive can hold the run *before* it sets the drive up, and says
  "Not enough room: this needs about 4.2 GB and the drive has 190 MB free". Nothing is written:
  no marker on the drive, no half-registered drive in your library.
- **A drive that will not take a marker is now a sentence rather than a crash**, whether it is
  full, out of allowance, read-only, or unplugged part-way through - and it no longer leaves an
  empty marker file behind on the drive.
- **A completely full drive is no longer reported as having exactly enough room.** A disk with
  zero bytes free and a disk Truestill could not measure at all were being treated as the same
  thing, so the space check passed on a drive that could not take a single file.
- **`truestill catalog` no longer claims your catalog is in the wrong place when it is not.** If
  any part of the path to your Truestill folder was a shortcut - common on Linux and macOS where
  a home folder or a data drive is linked elsewhere - Truestill compared two spellings of the same
  file, decided they were different, and told you to move a catalog that was already exactly where
  it belongs. It now asks whether two paths are the same *file* rather than the same *text*, and
  the self-check no longer labels a current catalog as an older one.
- **Truestill no longer opens a different library depending on which folder you ran it from.**
  Very early versions kept the catalog in a `reports/` folder next to wherever you happened to be,
  and Truestill still looked there first - so the same installation could show you one library
  from one folder and another from somewhere else, with nothing said about it. It now always uses
  its proper location, or the one you set with `TRUESTILL_DATA_DIR`. If you have an old
  `reports/catalog.sqlite`, `truestill catalog --move` copies it across, and it is left untouched
  until you delete it yourself.
- **An upgrade that is interrupted now leaves your library exactly as it was.** When Truestill
  updates the shape of its catalog, it does that in steps. If the power went out, or you closed
  the laptop, part of a step could already be written while Truestill still believed the older
  shape was in place - so the next launch could meet an error it could not explain. Each step is
  now all or nothing: it either finishes completely or leaves nothing behind, and the next launch
  simply carries on. **The same change fixed a rarer problem** where opening Truestill twice
  while an upgrade was pending could report a broken catalog.
- **Checking a copied drive now tells you it is a copy.** If you clone a drive - or restore one
  from an image - both copies carry the same drive identity, which is correct: they are the same
  library until they drift apart. But Truestill counted them as **one** place, so it told you your
  photos were in fewer places than they really were, which is the wrong direction to be wrong in.
  Now, when a drive answers in two places at once, `truestill verify` and the Check screen say so:
  both folders, when the other was last seen, and the command to give one its own identity if they
  are genuinely two drives. **It never decides for you** - nothing is renamed, split or refused.
  A drive you simply *moved* says nothing, because a move and a copy whose original is unplugged
  look identical and warning about every move would be noise.
- **If you tell Truestill where to keep its files, it now listens.** Setting `TRUESTILL_DATA_DIR`
  used to be quietly ignored whenever there was a `reports/catalog.sqlite` in the folder you
  happened to run from - so you could be organizing photos into a different catalog than the one
  you named, with nothing on screen saying which. The setting now wins, an empty setting counts as
  not set, and Truestill says which catalog it chose and why. **An existing library is still never
  left behind**: if the location you named has no catalog yet, the one you already have is used,
  and Truestill tells you that is what happened.
- **Screens that open several things at once no longer queue behind each other.** Every time
  Truestill opened your library it briefly took the same exclusive lock it needs to *build* a
  library, even when it was only going to read. One screen fires several requests at once, so
  they took turns for no reason: the slowest of twelve simultaneous opens went from **232 ms to
  4 ms**. Nothing about your data changed, and a brand-new library is still built exactly once.
- **An empty file where your catalog should be now stops Truestill instead of becoming your
  library.** If a copy of your catalog ran out of disk part-way, or a run was interrupted before
  it wrote anything, what is left behind is a file of **zero bytes** wearing your catalog's name.
  Truestill used to open it, build a fresh empty library into it, and call it *"an empty
  catalog"* - which looks exactly like starting over, and made the on-screen advice to *"delete
  the old one when you are happy"* point at the file that still had your photos in it. It now
  refuses to open it, says the file is empty and that your real library is untouched, and tells
  you to rename or delete it or to pass `--db` to the catalog you meant. **A genuine first run is
  unaffected** - there is no file at all in that case, which is a different thing.
- **Reloading the page during a run no longer leaves you watching a spinner that never ends.**
  If you reloaded, or the connection dropped and came back, Truestill reconnected to the running
  job and then waited for news that had already been delivered to the page you left - so the
  screen sat there with no outcome, however the run actually ended. It now tells you how the job
  finished. The same fault kept Truestill from shutting down cleanly while a run was on screen.
- **Screens now announce that they are still loading.** Each screen marks itself busy while the
  content it opens with is on its way, and clear when it has arrived, so a screen reader says so
  instead of reading a half-filled page as finished. A failure in one of those background
  requests is now reported deliberately rather than through the catch-all that exists for
  unforeseen bugs. **A screen that fails still shows its placeholder** - replacing that with a
  failure card is a separate change, not yet made.

- **A run that loses contact with Truestill now tells you, instead of freezing.** If the live
  connection to a running job died - which could happen when you pressed Cancel just as the work
  finished - the screen simply stopped. It kept whatever it was showing before the run, the button
  stayed greyed out, and there was **no message, no error, and no way to find out what had
  happened**. It now says plainly that contact was lost, that the job may have finished or been
  stopped, and to check the folder before running it again. This affects every kind of run -
  organizing, backing up, checking, rearranging, importing - because they all share the same
  machinery.
- **Organizing by copy no longer asks you to type "move".** The confirm box wanted the same word
  whichever mode you chose, so copying - which leaves your originals exactly where they are -
  asked you to type *move* to go ahead. It now asks for the word that matches what will happen:
  **copy** when copying, **move** when moving or reorganizing in place. That is also the word the
  command line already uses, so the two do not disagree.
  The same box used to warn *"This run is not reversible with undo-organize"* while copying. True,
  but it read as a hazard warning on the one mode that changes nothing. It now says what actually
  matters - *your originals are not changed, so there is nothing for undo-organize to put back*.
- **A folder with nothing left to organize says so, instead of asking you to type a word first.**
  Organizing the same folder twice showed the full confirmation ceremony and ended in a button
  reading **"Organize 0 files"**. It was counting the files it FOUND to decide whether to ask, and
  counting the files it would ORGANIZE on the button. It now checks the second one and simply
  tells you everything there is already organized.
- **A trip or an event you have already named no longer asks you to name it again.** Opening Trips & events
  re-offers every trip it can see, including ones you named earlier. Those came back with an empty
  name box, exactly like a trip that had never been named - and anything you typed into it was
  discarded without a word. Anything you have already named now shows its name instead of a box,
  and says that renaming is not available on that screen rather than pretending to accept one.
  **A group of photos that has since grown or shrunk still asks**, and that is deliberate: adding
  one photo to an evening makes it a different group from the one you named, so Truestill treats
  it as new rather than quietly filing it under the old name.
- **Two events on the same day with the same name now get separate folders, as the preview always
  said they would.** Truestill has always noticed that a second event named *Goa Trip* on the same
  date would spell the same folder as the first, and the preview offered to file it as
  *Goa Trip (2)*. It worked out that name and then did not use it: both events were placed in one
  folder, and the note described something that never happened. The preview and the result now
  agree. Nothing was lost - the photos were all there, under one folder instead of two - but where
  they landed was not what you were told.
  If you already have events that merged this way, a **Rearrange your library** run will now offer
  to separate them.

### Changed
- **The Truestill name in the sidebar is back to the monospace lettering, with the indigo dot.**
  It was briefly set in a serif; that took the name out of the one thing it was chosen to lead,
  since every path, count and date in Truestill is set in the same monospace. The **TS** mark on
  the collapsed sidebar and the app icons are unchanged.
- **The sidebar no longer warns you about the step you are in the middle of.** If nothing has
  been copied to a backup drive yet, that is progress rather than a problem, and it now reads
  quietly - *"not on a backup drive yet"* - instead of in the warning colour. This is also the
  normal, permanent state for anyone organizing to a cloud remote with `--rclone`, who was being
  told their photos were at risk for a choice they had made deliberately.
  The warning colour is now kept for the one case you can act on: *"N files in only one place"*.
  It carries a **⚠ marker** as well as the colour, so the difference does not depend on seeing
  colour at all.
  **Files Truestill has no copy of anywhere have moved to the Stats screen**, where there is
  room to say what they are and what to do. They are counted as *"not on a registered drive"*
  with both ordinary explanations - a cloud remote, or files organized from the command line
  before it registered its destination - and Truestill does not guess which applies to you.

### Fixed
- **Photos organized from the command line are now actually in Truestill's care.** Organizing
  into an ordinary folder recorded the photos but never registered the folder, so they existed
  in a strange half-state: Truestill knew about them well enough to skip them as duplicates on a
  later run, but `truestill verify` could not check them, `truestill status` did not count them
  toward keeping copies in two places, and `truestill where` could not find them. **The app has
  never had this problem** - it registers the destination before it writes anything - so which
  of the two you used silently decided whether your photos were being looked after.
  The command line now registers the destination too, which writes one small
  `.truestill-drive.json` file into it, exactly as the app does. **A preview still writes
  nothing at all**, so trying Truestill out against a scratch folder leaves it untouched unless
  you ask for the real run with `--apply`. A folder that is already a registered drive keeps the
  identity and the name it has.
  **Photos organized this way before today are not repaired by this** - the fix stops it
  happening again, it does not go back. If `truestill status` reports fewer files than you
  expect, that is why.
- **The sidebar strip was telling you your photos were safe when they were not.** It read
  *"safe in 2 places"*, and the 2 was the number of backup drives holding *anything at all* -
  not the number of places your photos are. Organize into one drive, then organize different
  photos into a second, and every single photo sat in exactly one place while the strip said
  two. On the maintainer's own library it said "safe in 2 places" while **31 files had no
  recorded copy on any drive**.
  It now counts your **files**, not your drives, and it leads with the risk: *"31 files not on a
  drive yet"*, or *"4 files in only one place"*. The reassuring version - *"every file in 2
  places"* - appears only when it is true of **every** file, and the three squares fill from the
  least-protected file, so they can never promise more than your worst-off photo has.
  **The word "safe" is gone**, deliberately. Truestill knows where copies were recorded; that is
  not the same as having checked they are still there. Use **Check now** on the Backups screen
  for that.
  The photo and video totals have gone from the strip - they never changed and asked nothing.
  And the catalog path no longer collapses to a fragment like `…e` when the sidebar animates.

### Changed
- **The sidebar is now a dark rail in both light and dark mode.** Collapsing it swaps the name
  for a **TS** mark, which is drawn artwork rather than text in a font, so it looks the same on
  every computer - a font would have rendered differently on Linux, where the one the brand sheet
  names is not installed. (The full name itself is set in Truestill's own monospace; see the
  entry at the top of this release.)
  The seven screens are unchanged and still flat; they are only grouped now under **Main** and
  **Settings**. **The browser tab shows a Truestill icon** instead of a blank page.
  Collapsing is now a small round chevron sitting on the edge between the sidebar and the page,
  rather than a row that looked like another place you could go to. It moves with the edge when
  the sidebar opens and closes, still works from the keyboard, and still announces itself as
  Collapse or Expand. On a narrow window, where the sidebar becomes a bar across the top and
  there is no edge to sit on, it is not shown.

### Fixed
- **The sidebar stays where it is when you scroll a long screen.** On a tall screen - Settings,
  or a big result - scrolling moved the whole window, so the navigation slid up off the top and
  you had to scroll back to reach it. The navigation now stays put and only the content moves.
  **And switching screens takes you to the top of the new one.** It used to keep whatever
  scroll position you were at, so moving from a scrolled screen to another one dropped you into
  the middle of it, often into blank space below the content.
  **On a narrow window nothing changes, on purpose.** There the navigation is a bar across the
  top rather than a column, and holding it in place would spend most of a short window on
  navigation instead of on your photos.

### Changed
- **After cleaning up empty folders, the app now tells you where they went.** It used to say
  "Removed 3 folders", which is the same sentence whether they are sitting in your trash and can
  be put back or are gone for good. Truestill knew which; the screen added the two numbers
  together and showed the total. It now says **"3 folders moved to the trash"**, and names a
  permanent removal as permanent when that is what happened. A run that removed nothing says so
  plainly rather than reporting a removal with a zero in it.
- **And when there is no trash to use, the app now tells you what to do about it.** The previous
  release stopped Truestill from deleting those folders outright, which is right - but the
  message said only that they could not be removed, which left you correct and stuck. It now
  shows the exact command that will remove them from a terminal, and says in the same breath
  that it cannot be undone and asks for a different word because of that.
- **If Truestill cannot reach a trash, it now leaves the folders alone instead of deleting
  them.** This is the second half of the change below, and it is the one that matters. Truestill
  removes leftover empty folders by putting them in the trash, and it always refused to do
  anything else when a *drive* turned the trash down - a network or cloud drive often does. But
  when the whole *machine* had no trash it did the opposite: it removed the folders outright.
  Those are two situations you cannot tell apart from the outside, and they had opposite
  outcomes, with the permanent one happening on its own.
  Now they behave the same way. Every folder is left exactly where it is, and each one is named
  on screen with the reason, so nothing is quietly skipped either. **The only way Truestill will
  ever delete a folder outright is `truestill clean-empty --permanent`**, which asks you to type
  `delete forever` rather than `clean` - a different question for a different answer. That was
  always the intent; it is now the only route.
  If you have been using Truestill on Linux, nothing changes for you: you had a trash and still
  do. Nothing about your photos was ever at risk here - only the empty folders left behind after
  a move, which by then contain nothing but system files like `.DS_Store`.
- **Removing leftover empty folders now uses your system's trash on every platform, not only on
  a Linux desktop.** Truestill has always tried to put a removed folder in the trash so you can
  get it back. What it could not do was guarantee it had a trash to use: it looked for an
  optional helper, then for a Linux tool called `gio`, and where it found neither it removed the
  folder outright instead. Because `gio` is a Linux component, "neither" was the ordinary
  situation on **Windows and macOS** - so the recoverable behaviour was the one Linux users got
  by accident, and the permanent one was the default everywhere else. Truestill said which of
  the two was about to happen before asking you to confirm, so nothing was ever hidden, but the
  answer depended on the machine rather than on anything you chose.
  The helper is now a required part of Truestill rather than an optional one, so the trash is
  always available. On Windows that means the Recycle Bin; on macOS and Linux, the desktop
  trash. It adds no download of any size worth mentioning and brings nothing else with it.
  **A test now checks this on Windows, macOS and Linux on every build**, because the old
  behaviour was decided by a value nobody had ever measured on the platforms it affected.
- **What Truestill costs on a cloud drive is now written down, and it still will not guess how
  long a run will take.** Measured on one encrypted cloud mount: a 32,628-file census took
  **21 seconds**, while reading those files for duplicates and dates moved 29.4 GB at about
  **9 MB/s** - roughly 53 minutes, with the processor 3% busy the whole time. The wait is your
  connection, not your computer. Encryption adds its own cost on top, because the files are
  decrypted on your machine as well as pulled over the wire. `README.md` carries the short
  version and `docs/PERFORMANCE.md` §5.2 the detail, including that this is **one mount on one
  connection** and not a claim about Truestill's speed.
  **No finishing time is shown, on purpose.** The obvious way to guess one is to time the fast
  census and scale it up - but that reads folder listings while the slow part reads the files
  themselves, and a cloud client that keeps listings on your machine makes the census fast no
  matter how slow the link is. The guess would be confident and wrong. Truestill tells you how
  much it needs to read before it starts, and says plainly that how long that takes depends on
  your disk or connection.
- **If your Linux desktop indexes your files, exclude your cloud drive from it.** GNOME's file
  indexer opens every file it finds to read metadata - and on a cloud drive, *opening* a file
  **downloads** it. Organize into a cloud folder inside your home directory and the indexer can
  quietly pull your entire library back down behind you, filling your disk and saturating your
  connection, looking for all the world like Truestill being slow. `docs/moving-machines.md`
  has the settings that stop it, including the measured detail that **adding an exclusion did
  not work** and narrowing the indexed folders did.
- **Truestill now tells you when it has passed over a hidden file or a hidden folder.** It
  still skips them, and that is deliberate: the hidden folders on a typical computer are
  `.Trash`, `.thumbnails` and the caches your operating system keeps, and sweeping those into
  your library would be worse than leaving them alone. What was wrong is that it said nothing.
  **If you keep photos in a hidden folder, you saw no sign of them at all** - not a count, not a
  name, nothing. Now the folder is named, so you can rename it without the leading dot and run
  again to bring those photos in.
  Hidden *files* are listed by name, so you can see that the thing skipped was your own
  `.picasa.ini` rather than something anonymous. And **Truestill's own `.truestill-drive.json`
  is listed separately** rather than counted among yours - it is hidden too, and one of the
  hidden files being ours is exactly the sort of thing that makes a count confusing.
  **Nothing about which photos get organized has changed.**
- **`truestill analyze` now shows you what it is doing while it does it, and its report survives
  being saved to a file.** On a 192 GB library the census appeared in 21 seconds and then
  **nothing happened on screen for 53 minutes** - the work was running the whole time, but there
  was no way to tell that from the outside. Now each stage reports as it finishes, and a counter
  shows the slow stages moving.
  **Saving the report works properly.** `truestill analyze <folder> > report.txt` puts the
  report in the file and the progress counter on your screen, so the file stays clean and
  readable - the same way `git` and `docker` behave. It used to write the progress counter into
  the file too: **127 KB of it** on that library, one line per file, which made the report
  almost unusable. Piping into `less`, `tee` or a log file all behave now.
  **And the report no longer waits for the end.** Redirected to a file, nothing at all appeared
  until the whole run finished; the early answers are now written out as soon as they are ready,
  which is the entire point of getting a cheap answer first.
  **What is not measured still says so.** A stage that has not run is named and left without a
  number, never shown as a `0` - a zero would mean "none found", and nothing has looked yet.
  Stopping with Ctrl-C still keeps everything printed so far and still refuses to give a partial
  duplicate count, because a half-finished count is a wrong answer rather than an incomplete one.
- **If your drive is unplugged part-way through organizing, Truestill now stops and tells you,
  instead of quietly filling up your computer.** A cloud drive that drops out under a long copy
  leaves an ordinary empty folder behind where it used to be - so writing carried on, into your
  computer's own disk, rebuilding the library there. Truestill already refused to *create*
  folders that way; now a long run also checks, every few seconds, that the drive it started on
  is still the drive it is writing to, and that this computer still has room. If either stops
  being true it stops, says which, and says what to do about it.
  **Everything already copied stays, and the run picks up where it left off** when you plug the
  drive back in and run again. Nothing is left half-written.
  **It is deliberately slow to complain.** A drive that hiccups for a moment is not a drive that
  has gone: it takes three bad readings over fifteen seconds before Truestill will stop a run.
  A check that interrupts healthy work gets switched off, and takes its real protection with it.
  **This now covers all three long jobs** - organizing, changing your folder layout, and backing
  up to a second drive. Changing the layout is the one worth knowing about: it rewrites every
  file, so on a cloud drive it pushes your whole library through that client's cache, and it
  previously had no free-space check of any kind. Backing up had one, but it was measuring the
  *drive*, which is exactly the disk that is not the problem.
- **When Truestill skips duplicates, it now tells you where their twins are.** A run used to
  report a number - *"2,057 duplicates, skipped"* - and stop there. That number meant two
  completely different things and gave you no way to tell which: either **Truestill already had
  those photos in your library**, in which case the copies in your source folder are redundant
  and you can clear them out, or **your source folder simply contained each photo twice**, which
  tells you nothing about your library at all. The count is now split - *"5 already in your
  library, 3 earlier in this batch"* - in the preview, in the run summary, in Analyze and on the
  screen in the app.
  **Nothing was deleted, then or now.** A skipped duplicate is a file that was not *copied* a
  second time; your originals are untouched, which is what the wording now says plainly. The
  screen also used to describe every duplicate as *"identical to a kept file"*, which was simply
  wrong when the twin was already in your library and there was no such file in the batch.
- **Photos and videos your phone named itself now join your timeline instead of landing in
  `Saved/`.** Android's camera writes files called `IMG_20140105_181210.jpg` and
  `VID_20140817_155317.mp4` - the date and time the shutter fired, in the name. On some phones,
  and after some copies between computers, that name is *all* that survives: the camera make and
  model come through blank. Truestill was already reading the date out of those files and filing
  them correctly by month - it just would not call them your photos, so they went to `Saved/`,
  the folder for files whose origin is unknown. On the library this was found in, **every single
  file in `Saved/` was one of these**. They now go where they always belonged.
  **A timestamp alone is still not enough**, and that is deliberate: a film you saved from the
  web has a date inside it too. It takes the camera's own naming - the `IMG_`/`VID_` prefix
  *and* a full date and time - before Truestill will call something your photo. `IMG_1234.JPG`,
  which iPhones and Canon cameras use, is just a counter and is left alone.
  **This applies to files you organize from here on.** Anything already sitting in `Saved/`
  stays there; re-importing from the originals is what moves it.
- **A photo that still carries its camera's details now joins your timeline, even if it reached
  you through a messenger.** Truestill used to decide where a file belonged from its *name*
  first, so a photo sent to you as a *document* - which keeps the full camera information - went
  to `WhatsApp/` rather than to the month it was taken in. It was already being **dated** from
  that same camera information, which is what made the old behaviour hard to explain: trusted
  enough to date, not trusted enough to file. So a photo someone forwards back to you, or one
  you sent as a document and later re-imported, now joins the timeline instead of sitting in a
  messenger folder. It is your photo, with your camera's evidence on it.
  **This applies to files you organize from here on.** Anything already filed under `WhatsApp/`
  stays there, and `migrate-layout` will not move it either - a re-layout deliberately trusts a
  messenger folder rather than re-reading the files in it. Re-importing from the originals is
  what places them the new way.
  **Nothing changes for the ordinary case.** A photo sent normally through a messenger has its
  camera information stripped by the app before it ever reaches you, so there is nothing to go
  on but the name - those files stay exactly where they were, and Truestill still refuses to
  treat the date in a messenger filename as the date the photo was taken. Screenshots are
  unaffected too.
- **Truestill now keeps the camera and the location a photo records, instead of reading them
  and throwing them away.** Nothing shows them yet - this is the storage, and the screens come
  later - but it is worth knowing now, because **only files organized from here on will have
  them.** Older entries keep the columns empty; re-importing from the original files is what
  fills them in. Camera make, camera model and lens are kept; the serial number and owner name
  are **not**, and are not even read - they identify one device and one person, which is not
  something a tool that transmits nothing about your library should be writing down. Locations
  are kept exactly as the photo records them: 0N 0E is a real place off the coast of Africa and
  is stored as such, not confused with "no location recorded". **Your catalog file is upgraded
  automatically on first open and can no longer be read by an older Truestill.**
- **Reviewing trips on a drive you already organized now finds the same trips as reviewing
  them during an import.** It did not before. Truestill ends one outing and starts another when
  consecutive photos jump a long distance, and that check only ran on a fresh import - the
  screen that reviews an already-organized drive had no locations to work with, so it grouped on
  time alone. The same photos could therefore be offered as one trip on one screen and two on
  the other. **Trip suggestions on that screen may differ from what you saw before, and the new
  answer is the one the import path was already giving.** Nothing you have named or applied
  changes; this affects suggestions only. Photos with no location are unaffected and still group
  by time, which is most libraries.
- **An organize *preview* now exits `1` instead of `0` when it could not read one of your
  files.** Read this if you script Truestill: `truestill organize <src> <dst> && next_step` used
  to chain in this case and now stops. That is the intended behaviour, not a side effect - a
  preview exists to predict the run, the run exits `1` on those same files, and a `0` here meant
  the chain continued past a library Truestill could not fully account for. Nothing else about
  the exit codes changed: `1` has always been this CLI's *"finished, but something is wrong"*
  (`verify` uses it for a missing or mismatched copy, `organize --apply` for a failed one,
  `reclaim` for a skipped one), so no new code was introduced. **A preview over a fully readable
  source still exits `0`**, and `--apply` runs are unchanged. If you want the old
  keep-going behaviour, test the code explicitly (`code=$?; [ $code -le 1 ] && next_step`)
  rather than discarding it.
- **`ingest --takeout` is now `ingest --source`.** The old name described the motivating case
  rather than the feature: archive ingestion reads any `.zip`, `.tar`, `.tgz` or `.tar.gz` from
  any source, and every major photo service hands a user a `.zip`. `--source` is format-neutral
  and matches `organize`'s existing `source`. **`--takeout` keeps working, permanently** - it is
  a hidden alias resolving to the same value, not a deprecation, so existing scripts are safe.

### Added
- **`truestill analyze <folder>` tells you what is in a folder, in about a second, without
  changing anything.** Point it at any folder - one you have never organized, one you are not
  sure you want to organize - and it reports how many files are there, how much space they take,
  the split between photos, videos and audio, and every file format it found, with counts. It
  needs nothing else: no destination, no library, no setup. **It reads file names and sizes
  only and never opens your files**, which is why it is fast on a folder that would take much
  longer to organize.
  **It also tells you what it has *not* worked out.** Dates, duplicates and look-alikes need
  Truestill to actually read your photos, which this does not do - so instead of showing you a
  zero, it says plainly that nothing has looked yet, and points you at the organize preview,
  which does. A folder it could not open is named too, rather than counted as empty.
  **Analyze never changes your photos and never adds anything to your library.**
  It also says **how long it took**, and on a run of more than a second how many files a second
  it managed. That is there to set expectations rather than to boast: this report only reads
  names and sizes, so if it is slow, the parts of Truestill that have to read your actual photos
  will be much slower - useful to know before you start one.
  Folders with a long tail of odd file types stay readable: the file types are listed
  most-common-first and the rest are summarised (*"and 190 more (190 seen once each)"*) instead
  of filling the screen. **The totals are always exact** - only the list of names is shortened.

### Changed
- **The organize preview now tells you what is in your library, not just what it would do with
  it.** Before you commit to anything, it reports the **span of dates** your photos cover and how
  many fall in each year, how much space **identical copies** are wasting, and which files are
  the largest. These numbers existed before but only appeared *after* an organize had finished,
  which is the wrong way round for a preview.
  **Identical copies and look-alikes are counted separately, and only identical copies are
  described as space you get back.** A look-alike - the same photo at a different size or quality
  - is *kept* by Truestill and flagged for you to review, so calling its bytes "saved" would
  promise space that never arrives. Undated photos are counted on their own line rather than
  quietly left out of the years, so the numbers still add up to the number of files.

### Changed
- **Truestill now refuses, out loud, to write outside the folder you pointed it at.** It never
  did - every destination path it builds is assembled from a single filename it read off your
  disk - but nothing was actually *checking*, so the guarantee rested on how the code happened
  to be arranged rather than on a rule. There is now a rule. A path that is absolute, names a
  drive, or contains `..` is refused before anything is written, and the message names the path.
  **Folders you have symlinked elsewhere keep working** - a year folder living on a second disk
  is an ordinary setup, and the check reads the path rather than following it, so it cannot
  mistake your arrangement for an escape.

### Fixed
- **If a drive disconnects while Truestill is writing to it, Truestill now stops instead of
  quietly refilling your computer's own disk.** This is the one that could cost you real space
  without any warning. When a network or cloud drive drops - which they do under a long copy -
  the folder it was mounted at turns back into an ordinary empty folder on your computer.
  Writing to it *works*, so Truestill would carry on, **rebuild your whole library structure on
  your computer's disk**, and fill it. Now it notices the drive is no longer the one it started
  on, stops before creating anything, and tells you: nothing was written, reconnect the drive
  and run again, and it continues from where it stopped.
  **Moving files is covered by the same stop** - a `--move` run cannot delete an original,
  because the copy it would check is never made.

- **A photo that claims to have been taken in the future is no longer filed by that date.** Found
  on a real 32,628-photo library that reported its range as *2002 to 2051*: two files carried a
  capture date 25 years ahead, and Truestill believed them - which would have put them in a
  `2051/` folder and stretched the library's timeline by three decades. A date after today is
  impossible, so it is now **refused**, and Truestill carries on looking: if the file has another
  usable date it is used, and only if nothing is left does the photo go to `Undated/`.
  **It tells you when this happens**, because it usually means a camera's clock was wrong or the
  details were edited - and the original date cannot be recovered by any tool once it has been
  overwritten. **Photos taken today are never affected**: a full day of leeway is allowed for
  cameras running slightly fast and for timezone differences.
  Very old dates are still accepted. A scanned negative may genuinely be from 1962, and refusing
  it would throw away a true date that someone took care to record.

- **Organizing the same photo twice no longer puts two dates in its name.** A photo whose date
  came from its filename gets a name like `20140815_IMG_0001.jpg`. If Truestill later organized
  that same photo again once it could read the camera's own date - after you installed
  `exiftool`, say - it added the fuller stamp in front of the one already there, giving
  `20140815_143022_20140815_IMG_0001.jpg`, and again on every pass after that. The date Truestill
  wrote is now **upgraded in place** instead: you get `20140815_143022_IMG_0001.jpg`, the same
  answer you would have got by organizing once with everything known. **Only a date at the very
  start of the name, and only for the same day, is treated as Truestill's own** - a photo called
  `VID-20250804-WA0020.mp4` or `IMG_20140815_143000.jpg` is left to be stamped exactly as before,
  and if your own filename says a different day from the photo's metadata, your name is kept and
  the metadata date is added in front rather than replacing it. **Files already organized are not
  renamed**; this applies to copies made from here on.
- **A camera or app name that had to be shortened can no longer end in a dot, which Windows
  would have silently dropped.** Folder names were already protected against this; the label
  Truestill records for a source was not, so a very long camera model cut at 60 characters could
  keep a trailing dot. On Windows `Photos.` and `Photos` are the same folder and on Linux they
  are two, which is how one library starts reading differently on two machines. Both now follow
  one shared rule.
- **Using Truestill in two places at once now says so plainly, instead of showing you a
  crash.** Running a command in a terminal while the app is open is an ordinary thing to do, and
  the two share one library catalog. Only one of them can write to it at a time - which is
  correct, and is what keeps your library consistent - but the one that had to wait used to give
  up after five seconds with a wall of technical output ending in `database is locked`. It looked
  like something had broken. Nothing had. Both surfaces now stop with a sentence that says
  another Truestill operation is using the catalog, that a file is recorded only after it has
  been copied safely, and to try again once the other one finishes. **On the command line this
  has its own exit code (`5`), so a script can tell "try again shortly" apart from "you typed
  something wrong".** Real problems - a failing disk, a damaged catalog - are untouched and still
  report themselves in full, because being told to wait for a fault that will never clear is
  worse than seeing the error.
- **Truestill will no longer register the same library twice as two different drives.** If a
  drive's marker file went missing - copied to a new machine without it, restored from a backup
  that skipped hidden files - registering that folder used to create a *second* drive identity
  for photos Truestill already knew about. On the command line the new drive then showed **0
  files**, as though the backups had never existed. In the app it was quieter and worse: the new
  drive picked up all the files, and Truestill went on to report *"at least two drive copies"*
  for photos that existed in exactly one place. Registering now **stops and names the drive the
  folder already is**, having checked the file contents rather than just the names. If the drive
  simply moved, `truestill drives --init <folder> --label x --adopt-existing` re-attaches it
  under its original identity; if you really do have two drives holding the same photos,
  `--force-new-identity` registers the second one.
- **An unplugged drive no longer tells you to register it.** Pointing `verify`, `reclaim` or
  `migrate-layout` at a path that is not there said *"isn't a Truestill drive yet - register it
  with `truestill drives --init`"* - the one piece of advice that causes the problem above. It
  now asks whether the drive is plugged in. A folder that *is* there and simply is not a drive
  still gets the register suggestion, unchanged.
- **A photo Truestill could not read is no longer also counted among the ones it says it will
  organize.** The preview said both *"organized (unique): 5"* and *"files that could not be
  read: 2"* about the same seven photos, with the two unreadable ones inside the 5 - a file with
  no hash matches nothing, so it read as new. Every scanned file is now reported in exactly one
  bucket, and the buckets add up to the number of files scanned. **The CLI summary has a new
  `could not be read` line**, printed even when it is zero so the figures can be checked by
  adding them up; the app's *"new - will be organized"* count and the number on the confirm
  button both drop accordingly. Nothing about what a run *does* changed - an unreadable file is
  still attempted and still reported as failed; only the preview stopped promising it.
- **A photo Truestill cannot read is now named, instead of vanishing from the preview.** A file
  that is locked, permission-denied, on a failing disk, or moved away mid-scan produced empty
  hashes - **the same empty hashes** a file gets when the size pre-filter deliberately decides
  not to hash it. Nothing downstream could tell those apart, so on a preview, which copies
  nothing and therefore never reaches the run's "failed" outcome, the file was reported
  **nowhere at all** and the library looked clean. Both the CLI and the app now count these and
  name them one by one, with the reason for each - *permission denied*, *input/output error*,
  *disappeared during the scan* - because those are three different things to do about it. A
  long list is capped and says how many it hid. Unreadable **folders**, which the app has known
  about since the feature shipped but never actually drew on screen, are now displayed too;
  they are still named without a file count, because the number inside a folder that cannot be
  opened is precisely what is unknown.
- **A FAT32 drive can no longer swallow most of a run and then fail the videos.** FAT32 cannot
  store a file of 4 GiB or more, and 4K phone video crosses that routinely. Organize had no
  preflight of any kind, so a library with a few big videos organized nine thousand files and
  *then* failed N of them, one `[Errno 27] File too large` at a time, against a drive reporting
  200 GB free. Organize now checks what the destination can physically hold **before writing
  anything** and refuses, **naming the files that would fail** rather than counting or skipping
  them - a run that quietly omitted exactly the footage the user cared most about, and reported
  success, would be the worse outcome. The errno message itself now names FAT32 as the reason
  instead of passing the raw errno through. Detected from `/proc/mounts` on Linux and
  `GetVolumeInformationW` on Windows; **macOS reports unknown, and unknown never refuses
  anything**. Both the CLI and the app inherit the refusal, and both previews say so up front.
- **An archive holding a file too large for the drive is refused before it is unpacked.** The
  organize preflight above cannot cover this: an archive ingest extracts a staging tree onto the
  destination *first*, so a 5 GB video inside a zip would fail part way through the unpack with
  most of the tree already written. The precheck now names such entries from the archive's own
  headers - free, because the walk that totals the claim already reads every declared size - and
  the extractor's own write, the one path that does not go through the destination backend,
  names EFBIG the same way for a header that under-declares.

### Added
- **`truestill repoint-sources` - moved the folder you imported from? Point Truestill at where
  it went, once.** Truestill records where each photo came from, as a full path. Move or rename
  that folder and every one of those records goes stale: `reclaim` reports files it cannot find
  instead of offering to free space, and searches cite folders that no longer exist. Name the
  old folder and the new one and every record beneath it is updated in a single step - the whole
  tree, not file by file. **Your organized library needs none of this** and never did: those
  copies are recorded relative to the drive they live on, so a drive that reappears somewhere
  else just works.
  It shows you exactly what it would change and asks you to type `repoint` before changing
  anything. **It also checks the contents of the new folder before believing you**, and refuses
  outright if the files there are not the files it recorded - a folder with the right shape and
  the wrong photos is exactly the mistake that would later let `reclaim` delete the wrong file.
- **Truestill now says whether each of your backup drives is actually plugged in.** A drive you
  have unplugged reads as *not plugged in* rather than looking like every other drive in the
  list - and, deliberately, never as *missing* or as an error, because disconnecting an external
  drive is a normal thing to do and reconnecting it fixes everything by itself. A drive Truestill
  has not yet seen on this computer says so in its own words (*location not known yet*) instead
  of being reported as gone: not knowing where a drive is and knowing it is absent are different
  facts, and only one of them is worth worrying about. The command line shows the same three
  states in a new `STATUS` column, and `truestill verify` now remembers where it found a drive so
  that column has something to say.
- **Trips**: group multi-day photos into one folder, review and apply on disk.
- **In-place organize (`organize --in-place`)** for libraries that live on the drive itself -
  a pendrive or external HDD with no staging space to copy into. Files are moved by **rename**:
  no bytes are rewritten, no other process ever sees an instant at which the content does not
  exist, and the content hash is unchanged because the inode is. (Surviving a *power cut*
  intact is a property of journalling filesystems; on FAT32/exFAT pendrives the undo journal is
  what makes such a run recoverable.) Plain `--move` now takes the same
  fast path automatically wherever the filesystem allows; `--in-place` additionally *requires*
  it, refusing a cross-device destination rather than quietly consuming space the user said
  they did not have. `--apply` needs a typed `move` confirmation, and the run reports its
  mechanism split ("3 moved by rename · 1 copied across devices").
- **`truestill undo-organize`** - reverse an in-place run, restoring every file to its exact
  prior path. Preview by default, `--apply` to move; `--list` shows recorded runs, and
  `--source-root`/`--dest-root` handle a drive that has remounted elsewhere. It ships *with*
  the feature rather than after it: a rename cannot lose bytes, so what is at risk is the
  *arrangement* of a library whose owner, by definition of this feature, has no second copy.
- Catalog **schema v10**: `inplace_runs` + `inplace_moves`, a **reversible** journal (where
  each file moved) rather than an audit one (what was destroyed).

### Added
- **`truestill migrate-layout`** - move an existing library to a layout you have chosen. Shows
  the full plan first (where every label's files are headed, how many, sample paths, and how
  close the longest path comes to Windows' 260-character limit) and moves nothing until you type
  `move`. Each file is copied, re-hashed at its new home, and only then removed from the old
  one, so there is never a moment when it exists nowhere. An interrupted run resumes.
- **`truestill migrate-layout --undo`** - put a completed migration back. Walks the moves in
  reverse with the same verification going the other way, and **refuses any file that changed
  since the migration**, reporting it rather than overwriting your edit. Available until a later
  migration of the same drive replaces the record.
- **`truestill clean-empty`** - remove the empty folders a migration leaves behind. Scoped to
  folders Truestill itself emptied - it never sweeps your drive - and it shows three lists before
  anything happens: what is empty, what holds only operating-system junk (`.DS_Store`,
  `Thumbs.db` and friends, removed with the folder), and what it is **leaving alone**, naming
  whatever is still inside. Anything it does not recognise keeps its folder. Removals go to the
  trash, and you type `clean` to confirm.
- **`truestill clean-empty --permanent`** - for cloud and network drives, where the trash cannot
  be used at all (there is nowhere on that mount to trash *to*). Trash is still tried first;
  only the folders it refuses are deleted outright, the preview says plainly that this is
  irreversible, and the confirmation is a different phrase - `delete forever` - so the word you
  typed for a recoverable cleanup can never be reused for a permanent one.
- **A browser end-to-end test layer** (`tests/e2e/`, `make e2e`). Playwright via
  `pytest-playwright` against an in-process app server, run in CI as its own chromium-on-ubuntu
  lane. Every UI defect the soak found is pinned as a named regression test, and the whole
  organize → back up → check journey runs as one test because the value is in the handoffs.
  Deliberately outside `make check`: a fresh clone stays green with no browser installed.
- **A hash cache** (`catalog.cache.sqlite`, beside the catalog - never inside it). An unchanged
  file is never read twice: a repeat preview of 2,275 unchanged photos went **15.8s → 4.7s**.
  It caches the perceptual hash as well as SHA-256, which is where nearly all of the win is.
  It can only ever remove work - any mismatch, corruption or unknown schema means hashing from
  scratch - so the answers are identical with it and without it.
- **`truestill --version`**, and the same version in the app footer, read from package metadata.
- **`docs/PERFORMANCE.md`** - the measured baseline per pipeline stage, the two known scaling
  limits with their thresholds, and a list of things a future optimizer should **not** "improve"
  (the size pre-filter above all). It carries one binding rule, referenced from the quality
  gates: every new pipeline stage declares its complexity in *n*, and anything worse than
  O(n log n) must justify itself.
- **A runtime alarm on the one known O(n²).** Perceptual dedup's linear scan is 0.7s at 2,275
  images and deliberately left alone; the first index to pass 10,000 now logs one line saying
  so, rather than leaving the trigger in a document nobody reads.

### Fixed
- **The Backups screen told four kinds of untruth, found in one real backup.** Checking a
  folder that was not a backup drive rendered `NaN verified · NaN missing · NaN changed`; the
  "this isn't a backup yet" state survived the copy that disproved it; the completion had no
  weight; and the drive cards said less than they knew. The NaN was a whole *class* of bug -
  handlers were reading raw job events, so every failure path could produce it - and it is
  fixed at the seam: `streamJob` now normalizes every terminal event before a handler sees it.
- **The golden path was broken at the organize → backup handoff.** Organizing never registered
  its own destination as a drive, so the app rejected the library it had just built. Organize
  destinations and backup targets are now registered on a real run (never on a preview, which
  must stay pure).
- **A path typed into one Backups field had to be typed again in the next.** Known values now
  prefill; Browse is for overriding, not for repeating yourself.
- **Organize reported "uploaded"** - backend vocabulary for an event that did not occur, and a
  quiet contradiction of the promise that files never leave the machine. Outcomes are now
  worded in exactly one place (`models.status_label`), so the CLI and the app cannot drift.
- **A cancelled run claimed there was nothing to organize.** For a 6,000-photo source, that is
  a false statement about the user's own library. Cancellation is now reported as cancellation
  on both the preview and the run paths.
- **Preview blocked the UI and could not be cancelled**; it now runs as a job on the same
  progress/SSE path as every other long operation.
- **`reclaim` can no longer delete the only copy of a file organized in place.** Such a file
  is both the source and the drive copy - one inode - so reclaim's re-verify gate was
  satisfied by the file checking against itself, and it would have deleted content with no
  backup anywhere. Those files are now excluded, and the count is reported rather than
  silently dropped.

### Removed
- **The category-first layout is decommissioned.** The compat machinery that carried existing
  libraries across to year-first - the legacy template constant, the legacy scheme, the
  load-time leniency that let a stored `{category}` template parse, and the "legacy layout"
  framing in Settings - is gone. Both real drives are year-first and verified; there are no
  external users; a bridge kept after the crossing is a path someone can still walk off.
  `{category}` is now valid **only** inside the fixed side-bin shape, which is not user-supplied.
- **The two migration undo records were retired** (The Memory Cabinet and Output, 2,269 journal
  rows each) with an explicit confirm, because after the decommission an undo would have
  succeeded into a state the product could no longer describe: a category-first tree with a
  year-first setting, and no supported way to set a matching layout. `migrate-layout --undo` on
  either drive now answers "no reversible migration exists for this drive". Reversibility itself
  is unchanged - every future migration arms its own record.

### Changed
- **The default folder layout is now year-first.** Photos land in `YYYY/YYYY-MM/`, with ordinary
  shots in a per-month `YYYY-MM - Everyday` bucket and named events in `YYYY-MM-DD - Name`
  beside it. Non-camera sources (Screenshots, WhatsApp, app names) are filed as labelled bins
  *beside* the years - `Screenshots/2024/2024-01/` - never above them. Undated files sit in
  `Undated/` at the root, or `<Label>/Undated/` for a bin.
  - **Months name themselves.** `2025-08`, not a bare `08`, so a folder still says what it is
    once it is copied, searched or attached somewhere away from its parent.
  - **Routing is on evidence, not on the label.** The one rule that identifies a camera photo
    puts it on the timeline; everything else goes to a bin. That keeps working under
    `--by-device`, where the label is the hardware name rather than `Camera`.
  - **An existing library is never reshaped.** A library organized before this change keeps its
    `<Label>/YYYY/MM/` structure, is described as a legacy layout in Settings, and is offered a
    migration it is never forced into.
  - **`{category}` is refused in a timeline template**, so source-above-timeline is structurally
    impossible rather than merely not offered. The side-bin shape is fixed and not editable.
- **Takeout metadata baking is ~27x faster.** Writing a rescued date or location into an
  organized copy spawned one `exiftool` process per file - **254.9 ms/file** measured, almost
  all of it process startup, which is about **7 hours** for a 100,000-file Takeout and 5
  minutes for a 1,200-file one. Writes are now batched (100 files per process, staged and
  baked a chunk at a time): **9.3 ms/file**, staging copy included, or ~15.6 min at 100k.
  The originals are still never touched - the batch bakes staged copies - and a process that
  dies mid-batch is **detected**, with every unconfirmed file reported failed rather than
  counted as organized.
- **The type fence now covers `scripts/`, and the pre-commit hook no longer lies.**
  `scripts/benchmark_hashing.py` imported `truestill.scan` - a module that has never existed
  under that name - and survived two renames that way, because nothing was pointed at it. It
  is repaired (correct import, no dead `sys.path` shim, the corpus read from
  `TRUESTILL_CORPUS` instead of a hard-coded home directory, and one `type: ignore` removed by
  typing the pool properly). Widening the fence also exposed that the pre-commit mypy hook
  inherited `--ignore-missing-imports`, which had been silently answering "fine" for that very
  import; it now runs with `args: []`, resolving workspace packages from source via
  `mypy_path`. That in turn revealed `uvicorn` missing from the hook's dependencies.
- **`[tool.mypy] python_version` and `[tool.ruff] target-version` raised 3.12 → 3.13**, to
  match what all three packages require and what CI actually runs.
- **The custody strip stopped doing 13x more work than it displays.** "Safe in N places" was
  building and sorting every at-risk row and then taking its length; it now counts. 224 ms →
  17.5 ms at 100,000 files, on a query that runs after every operation and on every load.
- **Renamed the project `vaeon` → `truestill`.** Distributions are now `truestill-core`,
  `truestill-cli` and `truestill-app`; the import packages are `truestill_core`,
  `truestill_cli` and `truestill_app`; the console commands are `truestill` and
  `truestill-app`; the app's auth header is `X-Truestill-Token`. The repository moved to
  `github.com/dinesh-ad/truestill`.
- Drive markers are now written as `.truestill-drive.json`. **Drives initialised before the
  rename keep working**: `.vaeon-drive.json` is still read, its `uuid`/`label`/`created` are
  preserved verbatim (the uuid is the catalog's foreign key, so re-minting would orphan every
  recorded copy), and the old file is never deleted. Reads never write; upgrading is explicit
  via `truestill drives --migrate-marker ROOT`. Precedence when both exist: the canonical
  file wins. See `IMPLEMENTATION_STANDARDS.md` §3.1.

### Added
- Drive identity, offline catalog & verify: a `.vaeon-drive.json` marker (truestill-minted `uuid4`,
  never the mount path) identifies each backup drive. Catalog schema v6 adds a `drives` table and
  a per-(content, drive) `file_copies` location table (with a per-copy `copy_sha256`, since a
  baked copy is not byte-identical to its source). `truestill drives` (list/`--init`),
  `truestill where <term>` (which drive is a file on, fully offline), `truestill verify <path>` (re-hash a
  connected drive's copies → verified/MISSING/MISMATCH, read-only, worker-pool), and
  `truestill status` (single-copy 3-2-1 nudge). Scoped to local destinations. See
  `docs/drive-identity-research.md`.
- Google Takeout Rescue Mode (`truestill ingest --takeout <dir>`): matches each media file to its
  JSON sidecar (all naming variants -- classic, `supplemental-metadata`, truncated, `-edited`,
  relocated `(n)`), recovers `photoTakenTime`/GPS/description into the existing dating and dedup
  pipeline, bakes rescued metadata into the organized copy losslessly via exiftool (source
  untouched; catalog stores both source and post-write copy hashes), collapses album duplicate
  copies while recording album membership, and prints an honest end-of-run rescue report.
  Timezone-aware (`--tz ±HH:MM`, single UTC->local conversion), `--prefer-takeout-dates` for
  libraries fixed inside Google Photos, `--map-albums` to name Camera events after their album.
  See `docs/takeout-format.md`. Catalog schema v5.
- CLI restructured into subcommands (`truestill organize`, `truestill ingest`).
- Event layer (`--events`, opt-in, Camera-only): adaptive log-scale temporal-gap clustering
  with GPS-jump reinforcement proposes events for the user to name or skip (never
  auto-named). Named events become `Camera/YYYY/MM/YYYYMMDD_<slug>/`, consolidated under the
  start month across month boundaries. Cluster identity is the hash of member SHA-256s, so
  names and skips are remembered (schema v4) and re-proposed only when membership changes.
  Sensitivity default (4.0) tuned so multi-day trips stay whole; see `scripts/tune_events.py`.
- Filename convention: organized copies are named `YYYYMMDD_HHMMSS_<original>` (date-only
  when the time is unknown) from the same date evidence used for placement. The prefix is
  suppressed only when that exact stamp already appears in the name, so date-embedded names
  (screenshots) are not double-dated and re-runs never stack a prefix; any mismatch keeps
  the authoritative metadata prefix. Originals are never renamed; the catalog records the
  original name alongside the new one. Disable with `--no-rename`.
- uv workspace layout: `truestill-core` (library) and `truestill-cli` (the `truestill` command),
  ready for future packages (desktop/UI) without restructuring the core.
- Concurrent hashing scan with a byte-size pre-filter (`truestill_core.scan`); thread/process
  pool selectable via `--pool`, worker count via `--workers`.
- SQLite catalog schema versioning via `PRAGMA user_version` with ordered, idempotent
  migrations; refuses catalogs written by a newer version.
- `Saved/` category for metadata-stripped social/web images (renamed from `Unsorted/`),
  plus a low-resolution + no-camera-EXIF heuristic that flags likely social saves.
- Two-tier de-duplication: exact (SHA-256) skipped, perceptual (dHash) near-duplicates
  kept-and-flagged so an original is never silently dropped for a look-alike.
- Pluggable `Destination` interface with local and rclone backends.
- Project hygiene: cross-platform CI (Linux/macOS/Windows, Python 3.13), pre-commit
  hooks (ruff + mypy), `py.typed`, package metadata, this changelog.

### Notes
- SHA-256 is the sole content hash (hardware-accelerated via OpenSSL); BLAKE3 is
  deliberately not used - one catalog column, no algorithm toggle, and a faster hash would
  optimize ~1% of cold-preview wall (`DECISIONS.md` D8; profiled 2026-07-29).
- Dates come from embedded metadata first, filename convention second, `Undated/`
  never from filesystem mtime.

[Unreleased]: https://github.com/dinesh-ad/truestill
