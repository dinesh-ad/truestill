# (adf) A CLI-ORGANIZED LIBRARY LEAVES `path_hint.library` UNSET, so the app has no observed destination to prefill.

*Body of backlog entry `(adf)`, under **Rulings - decided, no work attached**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adf) A CLI-ORGANIZED LIBRARY LEAVES `path_hint.library` UNSET, so the app has no observed
  destination to prefill.** Found 2026-08-12 while verifying `(abx)` on real material, and
  recorded rather than fixed because the right answer is a ruling.
  - `service/organize.py` writes `LIBRARY_PATH_HINT` after a successful run. **The CLI's organize
    does not.** Measured: 161 real files organized with `truestill organize` leave
    `library_path` at `None` while `files` reads 161.
  - **Nothing is broken today.** `(abx)`'s first-run gate is `no declaration AND no files`, so
    such a library is correctly never re-asked; and `(abx)`'s declared `library.root` is now the
    thing that prefills a destination, which does not depend on the hint at all.
  - **What is worth deciding:** whether the CLI should write the hint too. For it - a user who
    organizes on the command line and then opens the app gets an empty Organized-folder field
    where the app-only user gets a filled one, which is one product behaving as two. Against -
    the hint is an app-side convenience and the CLI has always taken its destination as an
    argument, so writing it makes the CLI carry state for a surface it does not use.
  - Small either way; it is one `set_setting` call or one sentence saying why not.
