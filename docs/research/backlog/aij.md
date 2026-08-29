# (aij) THE COMMAND `backup` TELLS YOU TO RUN CANNOT WORK AS PRINTED.

*Body of backlog entry `(aij)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aij) THE COMMAND `backup` TELLS YOU TO RUN CANNOT WORK AS PRINTED.** Filed 2026-08-29 (P131,
  soak eight), measured in passing while staging a backup target.

  ## MEASURED

  `truestill backup <source> <folder>` onto an unregistered folder refuses - **correctly** - and
  offers a remedy:

  ```
  error: /data/tmp/.../backup is not a Truestill drive.
         If this folder is new, register it:  truestill drives --init /data/tmp/.../backup
  ```

  Running exactly that:

  ```
  error: --init requires --label
  ```

  **The refusal is right and its remedy is wrong.** A user who copies the line the product printed
  gets a second error, from the command the product chose for them.

  ## WHY IT IS SMALL AND STILL WORTH A LETTER

  This is `(agp)`'s CLI-remedy census in one instance: a **remedy string that was never executed**.
  The fix is a one-word edit (`--label NAME`), and the interesting part is the class - a suggested
  command is a promise the product makes, and nothing anywhere checks that a suggested command
  parses. `cli.py` builds several such strings.

  ⚠ **Whether a guard is worth building is NOT decided here.** A test that extracts every
  suggested `truestill ...` string from `cli.py` and asserts the parser accepts it is buildable -
  the parser is already constructed in-process by the CLI tests - but it is a new artifact and
  `(ago)` rules that one has to earn itself. One instance is not yet that evidence; a second would
  be. **Recorded so the second is recognised as the second.**

  ## RELATED

  `(agp)` (the CLI-remedy census), [`soak-eight-record.md`](../../soak-eight-record.md) §7.
