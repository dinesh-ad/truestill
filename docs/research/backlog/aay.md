# (aay) JPEG XL (`.jxl`) is classified as unrecognized. RECORD ONLY - do not build.

*Body of backlog entry `(aay)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aay) JPEG XL (`.jxl`) is classified as unrecognized. RECORD ONLY - do not build.**
  Found 2026-08-03 by running `truestill analyze` over a deliberately format-diverse corpus,
  which put 7 `.jxl` files in the skipped census.
  - **It is genuinely media.** JPEG XL is an ISO/IEC 18181 still-image format, not an oddity,
    and it is a plausible future capture format rather than only an archival one.
  - **Recognising it is not enough, which is why this is recorded and not fixed.** Pillow still
    has **no native JXL support** (checked 2026-08-03); it needs the third-party
    `pillow-jxl-plugin` (Rust bindings, actively maintained). Adding `.jxl` to
    `IMAGE_EXTENSIONS` without that plugin would produce files truestill dates and categorises
    but **cannot perceptually hash** - near-duplicate detection silently absent for a format we
    just told the user we support. Exact dedup would still work.
  - **So it is a dependency decision, not a one-line extension.** §7's stdlib-first policy
    applies, and the honest options are: add the plugin and support JXL fully; or leave `.jxl`
    unrecognized, which is at least never-silent because the skipped census names it.
  - **Not urgent.** Zero `.jxl` in either real corpus measured so far - the 7 came from a test
    suite. Revisit when a real library contains them.
