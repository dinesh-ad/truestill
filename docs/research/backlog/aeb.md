# (aeb) `truestill catalog` CLAIMS THE OLD LOCATION WHENEVER A SYMLINK IS IN THE PATH.

*Body of backlog entry `(aeb)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aeb) `truestill catalog` CLAIMS THE OLD LOCATION WHENEVER A SYMLINK IS IN THE PATH.**
  Recorded 2026-08-19. ⚠ **Introduced by `(adv)` and `(adw)` together, four days and one day old
  respectively** - neither was wrong alone, and the combination is.
  - **The mechanism, and it is one missing `.resolve()`.**
    - `default_catalog_path()` returns `(override_dir / CATALOG_FILENAME).resolve()` - `(adv)`
      added the `resolve()` so the path a user is told matches the file that is opened.
    - `standard_catalog_path()` returns `_data_dir() / CATALOG_FILENAME` - **unresolved**.
    - `_cmd_catalog` compares them (`cli.py`) and prints *"This catalog is in the old location. To
      copy it to the standard place: truestill catalog --move"* when they differ.
  - 🔬 **MEASURED ON THIS MACHINE.** `/home/dinesh/TruestillLibrary` is a symlink to
    `/data/TruestillLibrary`. With the data directory under it:

    ```
    default  (resolved): /data/TruestillLibrary/.../data/catalog.sqlite
    standard (raw)     : /home/dinesh/TruestillLibrary/.../data/catalog.sqlite
    differ: True      same file: True
    ```

    and `truestill catalog` duly printed the old-location hint for a catalog sitting exactly where
    it belongs.
  - ⚠ **`(adw)` is what made this reachable, by removing the legitimate difference.** The two
    functions used to differ for a real reason - one preferred a legacy file, the other said where
    the catalog belonged - and `standard_catalog_path`'s own docstring still says so: *"unlike
    `default_catalog_path`, which says where it currently is and **prefers a legacy file that
    exists**"* and *"the pair differ only while someone is still on the old layout"*. **Both
    sentences are now false.** With the legacy lookup gone the two reduce to the same expression,
    so the *only* difference they can have left is string-level - and a symlink is the ordinary way
    to get one.
  - **What a user sees:** a correct catalog reported as being in the old location, and an
    instruction to run `--move`, which will then say there is nothing to move (or, with a legacy
    file present, refuse - `(aea)`). **Advice that is wrong and cannot be acted on.**
  - **Not fixed here, and the choice is not obvious:** resolve both (and accept that the printed
    path stops matching what the user typed), resolve neither (and give back what `(adv)` fixed),
    or compare on identity rather than string - `os.path.samefile`, which answers the question
    actually being asked and raises on a missing file, so it needs a guard. There is also a
    standing question of whether the two functions should still be separate at all now that they
    compute the same thing.
  - **Related.** `(adv)` - added the `resolve()`, for a good reason. `(adw)` - removed the
    difference that made the comparison meaningful. `(aea)` - what `--move` does when the user
    follows the wrong advice and a second catalog is there.
