# (aby) Organize screen: copy that repeats itself or explains its own button.

*Body of backlog entry `(aby)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aby) Organize screen: copy that repeats itself or explains its own button.** Recorded
  2026-08-08. **Editorial, no behaviour, deliberately kept out of the behavioural fix** - bundling
  it would drag a defect repair through a prose review.
  - *"Originals stay where they are."* is emitted from TWO sites onto one screen:
    the mode radio in `index.html` as the radio subtitle, and `app.js:modeLine` (`modeLine("copy")`) into
    `#org-mode-hint`.
  - The **Look inside** button is explained by a sentence next to it that says the same word:
    `#org-why` in `index.html` and `app.js:startOrganizeRun`, *"Look inside first to see what is in the folder."*
  - The confirm banner prints the typed-word instruction twice, four lines apart -
    `app.js:renderOrganizeRunConfirm` in the banner and again in the input label.
