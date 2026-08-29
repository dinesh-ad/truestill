# (aij) THE COMMAND `backup` TELLS YOU TO RUN CANNOT WORK AS PRINTED.

*Body of entry `(aij)`, **shipped 2026-08-29** - the closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

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

  ## ⚠ SHIPPED 2026-08-29 (P136), AND THE SECOND INSTANCE IS WHY THE GUARD CAME WITH IT

  **Two sites, not one.** Beside `cli.py`'s backup refusal, `drive.second_location_for` suggested
  `truestill drives --init <other> --force-new-identity` - also without `--label`, and
  `cli._cmd_drives` has **no exemption** for `--force-new-identity`. Both now carry
  `--label <name>`. This entry recorded that *"one instance is not yet the evidence `(ago)`
  requires, so this is recorded so a second is recognised as the second"* - it was recognised, and
  the guard came with it: `test_a_suggested_command_can_be_run.py`.

  ⚠ **The WIDE guard was refused on a measurement, and the number is the argument.** Extracting
  every `truestill …` string in the tree and asserting the parser accepts it was prototyped: it
  reported **33 failures out of 36 on a clean tree**, nearly all prose - comments reading
  *"`truestill verify` takes"*, docstrings naming a command mid-sentence, f-strings whose
  placeholders cannot be filled. **Separating "a command to run" from "a sentence mentioning a
  command" is not a regex or a parser job**, and a guard crying wolf 33 times is one somebody
  switches off. The shipped guard is scoped to `drives --init`, the one shape whose failure is
  proven, and says so in its own docstring.

  ⚠ **And it must not use the parser**, which was the first design and would have been vacuous:
  `--init requires --label` is a **runtime** check in `cli._cmd_drives`; `parse_args` accepts
  `drives --init X` happily. A parser-based guard would have passed while the defect stood.

  **One more thing the guard caught - its own bug.** `ast.walk` visits a JoinedStr *and* each
  fragment inside it, so a message split across adjacent literals offered a fragment holding the
  subcommand without the flag, and the guard failed on the very fix that repaired it. Fragments of
  an f-string are now excluded by identity.

  ## RELATED

  `(agp)` (the CLI-remedy census), [`soak-eight-record.md`](../../soak-eight-record.md) §7.
