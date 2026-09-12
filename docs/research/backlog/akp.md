# (akp) THE AT-RISK REMEDY ON BACKUPS CANNOT FIX THE FILE IT IS SHOWN ABOUT.

*Body of entry `(akp)`, now in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared
with [`BACKLOG.md`](../../BACKLOG.md).*

> ✅ **CLOSED 2026-09-12 by `4e1305a`.** `reach` is on `AtRiskRow` and `WhereCopy`,
> `app.js:atRiskBanner` splits the three cases, and the button is withheld when there is nothing
> to copy from. **Everything below is what was observed BEFORE that commit and is left as it was
> written** - a record edited to stay correct stops being one. `SHIPPED.md`'s entry is what says
> what shipped.

- **(akp)** Filed 2026-09-12, observed on a real external drive that had been ejected.
  **No work attached.**

  ## WHAT WAS ON SCREEN

  One photograph, `zsd.jpg`, recorded on drive `AD_2TB` and **nowhere else**. `AD_2TB` was
  unplugged, so the file was in zero reachable places. The Backups screen said:

      1 file exist in only one place
      A second copy is what makes them safe. Copy your library to another drive above.
      [ Copy to another drive ]

  ⚠ **Following that advice does not protect that file.** `zsd.jpg` is not in the library - it is
  on `AD_2TB` alone. "Copy your library to another drive" backs up the OTHER 161 files and leaves
  the one named above in exactly the state it was in. Measured rather than reasoned: `reclaim`
  against the library lists **161** candidates and mentions `zsd` **zero** times, because
  `reclaim_candidates(drive_uuid)` is per-drive.

  **Being told what to do, doing it, and remaining unprotected is worse than being told nothing**,
  because the user now believes they acted.

  ## THE SECOND DEFECT IN THE SAME BLOCK

  *"1 file exist in only one place"* - the verb does not agree. Counted wording, so it needs the
  same `plural()` treatment every other count on that screen already gets.

  ## WHAT THE RIGHT REMEDY WOULD BE

  The remedy has to name **the drive the file is actually on**, and the action differs by whether
  that drive is reachable:

  * **at-risk file on a CONNECTED drive** - the current advice is right if and only if that drive
    is the library. Otherwise the honest action is *copy `<that drive>` to another drive*, not
    *copy your library*.
  * **at-risk file on an ABSENT drive** - there is no action available at all. The honest sentence
    is that the only copy is on a drive that is not connected, and the step is to connect it. An
    offer to copy anything is inert until it is plugged in.
  * **at-risk file on the library itself** - the present wording is correct, and is presumably the
    only case anyone had when it was written.

  The screen already knows which case it is in: `service/drives.py:DriveRow` carries `reach` on the
  drive payload, which is why the card above this block correctly reads *"AD_2TB - not plugged
  in"*. The at-risk list does not carry it - `AtRiskRow` (`service/drives.py:AtRiskRow`) is `name` and
  `drive`, nothing more - so the remedy is composed without the one fact that decides it.

  ⚠ **This entry does not propose the wording.** The state is now reproducible, and the sentence
  should be written against it rather than guessed at.

  ## RELATED

  `(aiy)` (a count that was right about the number and wrong about the meaning), `(adx)` gap 2
  (naming a remedy the reader cannot reach).
