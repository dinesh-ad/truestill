# (aek) THE COPY PATH SURVIVES A FULL DISK; THE SETUP PATH CRASHES WITH A TRACEBACK.

*Body of backlog entry `(aek)`, **CLOSED 2026-08-21**. The closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ⚠ CORRECTIONS, 2026-08-21 - added beside the original rather than into it
>
> The findings below are what the soak measured and are left exactly as written. Three claims in
> them did not survive being checked against the code, and a fourth thing was missed entirely.
>
> **1. "The decisions-file write beside it ... were NOT tested" is wrong.** The decisions write is
> already hardened and already pinned. `decisions.write_decisions` is documented *"never raise"*,
> stages through a temp sibling, `fsync`s, `os.replace`s, removes its temp on failure, and words
> the errno in English via `decisions._explain`. `test_decisions_write.py:145-158`
> (`test_a_full_drive_is_reported_rather_than_raised`) asserts the wording **and** that no partial
> and no temp survive a full disk. Sending the next reader to write a test that exists is worse
> than saying nothing, so: it exists, and it became the model the fix copied.
>
> **2. "A few lines from a copy path" is wrong, and the error matters more than the fact.**
> `write_marker` is `drive.py`; the copy path is `destinations/local.py` and `safe_copy.py` -
> different module, different layer, different package-internal seam. *"A few lines"* implies a
> local oversight that a careful reader would have caught. What it actually is, is
> `ENGINEERING_STANDARD.md` §4's **fifty-sixth member**: a rule applied to some surfaces and
> silently not to another, which is the same class as `(aei)` and reads as settled precisely
> because the surfaces that have it agree with each other. Two of the three drive writes in a
> single `organize --apply` handled this; one did not.
>
> **3. "What a full disk should DO at registration" - RULED: refuse cleanly**, and the ordering
> is the fix rather than error handling. The product already words a full disk correctly and
> already exits 4 on it; the run simply died before reaching the sentence.
>
> **4. NOT IN THE ORIGINAL, AND IT IS WHY THE ORDERING FIX ALONE WOULD HAVE BEEN INERT.**
> `preflight_destination` used `free = 0` as its *"could not measure"* value and then returned
> `free_bytes=free or need`, so a genuinely full disk - which reports **0 free** - resolved as
> *exactly enough* and passed its own space check. Two states, one value, and the silent one won:
> the same conflation as `FileHashes(None, None)` standing for *"could not read"* and *"correctly
> did not hash"* alike (§9). The comment's intent was right; zero was the wrong way to say it.
> Fixed with `None`, pinned in both directions - a measured zero refuses, an unreadable
> `disk_usage` still proceeds.
>
> **5. THE `(adr)` ASYMMETRY, RECORDED AND DELIBERATELY NOT FIXED.** This product writes exactly
> two files a user can lose: the catalog and the drive marker. A zero-byte **catalog** has a named
> state and a refusal - `CatalogPresence.ZERO_BYTES` (`catalog_startup.py:72`) and
> `refuse_unusable_catalog` (`:159-160`), which stops the launcher before it binds a socket. A
> zero-byte **marker** has neither: `read_marker` swallows the `JSONDecodeError` (`drive.py:685`)
> and returns `None`, so the drive reads as *unregistered* with nothing said. Measured directly on
> a fabricated zero-byte marker: `existing_marker_path` finds it, `read_marker` is `None`,
> `needs_marker_upgrade` is `False`, `locate_drive` finds no root.
>
> That is recoverable rather than corrupting - a retry mints a fresh marker over it - which is why
> it is recorded rather than repaired. It is also now much harder to reach, because the staged
> write means a failure leaves no marker at all. **What is unrepaired is the asymmetry**: two
> files, one of which explains itself and one of which goes quiet.

- **(aek) THE COPY PATH SURVIVES A FULL DISK; THE SETUP PATH CRASHES WITH A TRACEBACK.** Found
  2026-08-20 by the first soak, S7. **The contrast is the finding** - the same feature handles the
  same errno impeccably a few lines later.

  ## ✅ WHAT THE COPY PATH DOES, AND IT SHOULD NOT BE DISTURBED

  Organizing 289 MB into a destination with the user's quota exhausted (real `EDQUOT`, errno 122,
  same class as `ENOSPC`):

  ```
     82  failed
     79  organized
      5  duplicate, skipped
  ```
  **exit 1. No traceback.** Each failure named the file, the destination relative path and the
  errno. And what was **left behind** was clean: **79 complete files, 79 catalog rows - exact
  agreement - 0 `.partial` files, 0 zero-byte files.** Every failed in-flight write was removed.

  This is the same `.partial` -> rename -> record discipline that survived a `kill -9` in S4, and
  it holds under space exhaustion too. **A failed copy leaves no corrupt file and no phantom row.**

  ## ⚠ WHAT THE SETUP PATH DOES

  The same command, against a destination **not yet registered**, on the same full disk:

  ```
  OSError: [Errno 122] Disk quota exceeded
    ... create_marker -> write_marker -> marker_path(root).write_text(...)
    (full Python traceback ending in pathlib/_abc.py)
  ```

  `write_marker` calls `Path.write_text` with no handling, so **the first thing organize does to a
  new destination** - write `.truestill-drive.json` - raises an unhandled `OSError`.

  ⚠ **Worse in context: this is the first run against a new drive**, when a user is least sure they
  did the right thing, and the product answers with an interpreter stack trace rather than *"there
  is not enough space on that drive"* - **which it plainly knows how to say, because the copy path
  says it 82 times in the same run.**

  ## AND A VOCABULARY LEAK IN THE MESSAGE THAT DID WORK

  Every failure line reads `FAILED: IMG_2707.JPG: cannot upload to '2013/...'`. The destination is
  a local folder; nothing is uploaded. ⚠ `IMPLEMENTATION_STANDARDS.md` §9: **no backend vocabulary
  reaches a user.** `upload` is the internal destination-adapter verb (the `record_uploaded` /
  rclone lineage) surfacing in the one message a user reads when something has gone wrong.

  ## WHAT IS NOT DECIDED

  *(Answered 2026-08-21 - see the corrections at the top. Left as written.)*

  - **Which setup writes need hardening.** `write_marker` is the one measured; the decisions-file
    write beside it and the catalog's own first write are the obvious neighbours and were **not**
    tested. ⚠ Do not assume they behave the same way - the whole finding here is that two writes in
    one feature behaved differently.
  - **What a full disk should DO at registration** - refuse cleanly, or register and let the copy
    path report per-file. The second is closer to what already works.
  - ⚠ **Not measured: a disk that fills between registration and copying**, which is the ordinary
    real case and sits between the two paths above.

  ## WHAT THE ANSWERS TURNED OUT TO BE

  - **Three writes, not two, and they behaved three different ways** in one `organize --apply`:
    `decisions.write_decisions` never raised and named the errno; `LocalDestination.upload` raised
    a typed `DestinationError` caught per file; `drive.write_marker` raised `OSError` at the
    interpreter. The instruction *"do not assume they behave the same way"* was right and
    under-stated - they already did not.
  - **The catalog's first write is the same class and is filed as `(aen)`**, not fixed here:
    `Catalog.__init__` does an unguarded `mkdir` and `sqlite3.connect` (`catalog.py:888,902`), and
    `SQLITE_FULL` needs a different answer from `catalog_busy`, whose docstring is right to refuse
    a wider net. Reproduced: `sqlite3.OperationalError: unable to open database file`, traceback,
    same shape, earlier in the run.
  - **"A disk that fills between registration and copying" is exactly why the ordering fix is not
    sufficient**, and the search says so too: quota-aware `statfs` is a per-filesystem feature
    added piecemeal (kernel patches for cifs and f2fs project quota; Red Hat bug 2011104,
    *"statfs reports wrong free space for small quotas"*). So `shutil.disk_usage` cannot be relied
    on to see this finding's own `EDQUOT`. The industry pattern is the pair rather than either
    half: a preflight is advisory and never replaces per-write `ENOSPC` handling, because
    check-then-write is a TOCTOU window. That is why both halves shipped.
