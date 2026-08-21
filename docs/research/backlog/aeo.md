# (aeo) A FULL HOME DISK STOPS THE APP LAUNCHING, WITH A TRACEBACK.

*Body of backlog entry `(aeo)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aeo) `session_link.write` IS UNGUARDED ON THE LAUNCH PATH.** Split out of `(aek)` on
  2026-08-21 as the same class in a different feature.

  ## WHAT HAPPENS

  `session_link.write` does `mkdir` (`session_link.py:131`), `touch(mode=0o600)` (`:143`) and
  `write_text` (`:148`), none of them guarded, and `__main__.py:345` calls it during launch. A
  full or read-only home directory therefore takes the app down with an interpreter stack trace
  before it serves anything.

  ## WHY IT IS ITS OWN ENTRY RATHER THAN PART OF `(aek)`

  `(aek)` is about a **drive** the user chose - the remedy is a sentence naming that drive, and
  the wording already exists for it. This is about the machine's own home directory on the launch
  path, where there is no drive to name, no run to refuse, and the failure is *the app does not
  start*. Same shape, different answer, and folding them would have produced one fix with two
  audiences.

  ## ⚠ THE PART THAT NEEDS CARE

  The write is deliberate and sharp-edged: `unlink` → `touch(mode=…)` → `write_text`, and each
  step is load-bearing (`ENGINEERING_STANDARD.md` §4 records the measurements - `write_text` alone
  yields the umask default, 0664, i.e. a session credential readable by the whole group, and
  `os.open` with `O_CREAT` follows a symlink at the target). **A repair must not simplify that
  sequence to make error handling tidier**; `test_session_link.py` pins the pre-existing-mode and
  symlink cases specifically.

  ## NOT DECIDED

  - **Whether a failed session-link write should stop the launch or degrade.** The file exists so
    a user with no console can find the URL; failing to write it is not obviously fatal, and
    launching without it is not obviously safe either.
  - **Not measured**: what a real full home disk does to the rest of startup - the catalog opens
    from there too, which is `(aen)`.
