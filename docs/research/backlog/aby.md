# (aby) Organize screen: copy that repeats itself or explains its own button.

*Body of backlog entry `(aby)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aby) Organize screen: copy that repeats itself or explains its own button.** Recorded
  2026-08-08. **Editorial, no behaviour, deliberately kept out of the behavioural fix** - bundling
  it would drag a defect repair through a prose review.
  - *"Originals stay where they are."* is emitted from TWO sites onto one screen:
    `index.html:148` as the radio subtitle, and `app.js:loadSidebar` (`modeLine("copy")`) into
    `#org-mode-hint`.
  - The **Look inside** button is explained by a sentence next to it that says the same word:
    `index.html:177` and `app.js:cleanupDisposition`, *"Look inside first to see what is in the folder."*
  - The confirm banner prints the typed-word instruction twice, four lines apart -
    `app.js:fitCatalogPath` in the banner and again in the input label.
