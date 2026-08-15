# (aap) Registering a folder must not mint a second identity for a library already known.

*Body of backlog entry `(aap)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aap) Registering a folder must not mint a second identity for a library already known.**
  **BUILT 2026-08-02**, split out of `(yy)` after the design pass observed it. Shipped first
  because it prevents a loss where `(yy)` only repairs an inconvenience.
  - **Observed, not reasoned.** With a drive unmounted, `verify` printed *"isn't a truestill
    drive yet - register it with `truestill drives --init`"*, and following that advice on a
    library whose marker was lost minted a fresh uuid with no warning. `moving-machines.md`
    already named this the worst failure mode of a move; the CLI was steering people into it.
  - **The two surfaces failed in opposite directions, and the app's was worse.** The CLI showed
    the new drive with **0 files** - visibly wrong. The app registers as a side effect of
    backup, and `attach_drive` matches by content, so the phantom drive got *all* the files and
    `truestill status` then said *"All catalogued content has at least two drive copies. Nicely
    redundant."* about photos existing in exactly one place. A custody tool overstating
    redundancy is the worse failure, so the guard sits at the point of minting rather than on
    the screen that reads the count.
  - **Detection is two-stage and bounded**: stride-sampled `stat` of up to 40 recorded
    `file_copies.relative` paths per known drive, then - only if half are present - 3 full
    SHA-256 reads that must **all** agree. Measured 0.12 ms median on a small library; the cost
    is per known drive and never walks the tree, which is what keeps it usable on a slow mount.
  - **It never adopts.** The evidence for *"this drive moved"* and *"this is a clone"* is the
    same evidence, and a product that counts how many places a photo is safe in must not
    resolve that by guessing. The CLI refuses and names both ways forward
    (`--adopt-existing` / `--force-new-identity`); the app refuses and points at the CLI.
  - **Still open, deliberately:** the app has no register screen - registration happens inside
    backup - so its half is a refusal, not an offer. Giving the app its own adopt flow needs a
    surface that does not exist yet, and is not blocking `(yy)`.
