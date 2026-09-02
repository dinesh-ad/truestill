# (aat) `(aar)` is forward-only, and `migrate-layout` will not carry it backwards.

*Body of backlog entry `(aat)`, under **Rulings - decided, no work attached**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aat) `(aar)` is forward-only, and `migrate-layout` will not carry it backwards.** Recorded
  2026-08-02, found while writing `(aar)`'s CHANGELOG entry and checked against the code rather
  than reasoned about. **A known limit with an accepted workaround.**
  - **The mechanism.** `WhatsApp` is a deterministic side-bin label
    (`categorize.deterministic_side_bin_labels`), so `label_routes` returns route `side bin` with
    `needs_decision=False` - *"only a screenshot, messenger or fallback rule can produce this
    label"* - and `rederive_rules` re-reads **ambiguous labels only**. Files already filed under
    `WhatsApp/` are never re-examined, whatever their EXIF says.
  - **`migrate.py` is not wrong.** Its premise survives `(aar)` intact: the filename rule is still
    the only producer of those labels. Re-reading every side-binned file would buy an exiftool
    pass over the largest bin in most libraries to change a handful of them.
  - **The consequence is real, though.** A library organized before 2026-08-02 diverges from what
    a fresh run decides on the same files, and only a re-import from the originals closes it.
  - **Why this is a stance and not work.** Deleting the output and re-running from source is
    acceptable here - the sources are never touched, so it always is. Should rescuing
    already-organized side-bin files ever be wanted, `(ii)`'s rescue flow is the surface that owns
    that question.

- **The catalog stays SQLite.** Parquet and Feather were considered and rejected on three
  grounds, each sufficient alone: they are **immutable** (no row update without rewriting the
  whole file, and the catalog updates a row per organized file), they offer **no transactional
  safety** mid-migration (the journal that makes `migrate-layout` resumable and reversible
  depends on it), and they would add a **heavy `pyarrow` dependency** against §7's stdlib-first
  policy. Columnar formats are right for analytics over immutable batches; this is a mutable
  transactional record. JSON remains in exactly one place - the small, human-readable drive
  marker - where being readable by a person with a text editor is the point. This is also what
  `(z)` means by catalog-first; **no change is pending.**

- **No charting library for Analyze's screens: rejected, hand-rolled SVG instead.** Ruled
  2026-08-03 while designing Analyze, and recorded before the screens are built so commit 4 does
  not re-open it. ⚠ **The premise has moved and the ruling has not.** This read *"the app is
  offline-first with no build step and one deliberately un-bundled `app.js`, so a chart library
  cannot be a dependency line"*. There IS a build step now (`make frontend`, Vite) and a React
  island, so *"cannot be a dependency line"* is no longer the argument. **The ruling still
  stands on its other half** - offline-first, and a charting library is weight for screens that
  are not built - but anyone re-opening it should argue the weight, not the impossibility.
  Original text follows. The app is **offline-first with no build step** and one deliberately
  un-bundled `app.js`, so a chart library cannot be a dependency line - it has to be **vendored
  into `static/`**, which is a permanent maintenance surface, installer weight, and a file
  nobody in this repo wrote. Against that: two bar charts. **The 2026 landscape was checked
  rather than assumed** - Chart.js, ECharts and ApexCharts are the live vanilla-JS options;
  Recharts is React-only and this app is vanilla; Google Charts has been unmaintained since
  2014. The conclusion is not ignorance of the options, it is that none of them is worth
  vendoring for this. Same shape as the `psutil` ruling below: a dependency declined to keep a
  small amount of code we own. Revisit only if a screen genuinely needs interactive charting,
  which two bar charts do not.

- **Treemaps for Analyze: rejected.** Ruled 2026-08-03. Every well-known disk analyzer leads
  with one, so this will be proposed again, and the reason it is wrong here is specific rather
  than aesthetic. **A treemap answers "which subtree is eating my disk?", which presumes a
  hierarchy the user built and understands.** Analyze's whole premise is the opposite: it is
  pointed at an unsorted pile whose folder structure carries no signal, so a treemap of
  `Camera Uploads/` is one large rectangle and tells nobody anything. The proportions worth
  showing are **by media kind and by year**, which are bars or a sparkline, not a treemap. Note
  also what the terminal report already ruled for the same data: **counts, not bars**, because a
  real library spans three orders of magnitude between its quietest and busiest year, so a
  linear bar saturates and a log bar makes a proportion claim that is not true.

- **`psutil` for filesystem detection: rejected.** It would delete `parse_proc_mounts` and the
  `ctypes`/`GetVolumeInformationW` branch in `filesystem.py` - roughly 60 lines including a
  hand-written parser - and `disk_partitions()` reports `fstype` on macOS via `getfsstat`, which
  is the one thing truestill currently cannot answer. Rejected anyway, on four counts: it is a
  **compiled C extension in the runtime graph** of a stdlib-first product; it is a large,
  general-purpose library carried for one function; `disk_partitions()` returns *mounted*
  partitions, so the **longest-prefix match still has to be written on top of it**; and what it
  buys is macOS, which today returns **unknown** and therefore refuses nothing - an honest
  answer, not a broken one.

  **The gap, named so the trade can be reopened on evidence:** on macOS `facts_for` returns
  `FilesystemFacts(filesystem=None, max_file_bytes=None)`. Nothing is refused there, so a macOS
  user copying a >4 GB video to a FAT32 card gets the improved EFBIG *message* after the failure
  instead of the preflight *before* it. If macOS detection ever becomes load-bearing - a report
  of that exact failure, or a feature that needs the filesystem name rather than its limit -
  this is the decision to revisit, and psutil is the candidate to weigh again.

- **`imagehash`: watch, do not move.** Last PyPI release **2025-02-01**, last repository commit
  **2025-04-17**. That is quiet, and quiet is **not** abandoned - the distinction is worth
  keeping, because it decides whether to act. The repository is **not archived**, its 26 open
  issues are open rather than closed en masse, there is no maintainer statement winding it down,
  and **no fork is positioned as a successor**. That is the opposite of the httpx picture, where
  the issue tracker and discussions were closed and Pydantic's `httpx2` was named by the
  maintainers as the path forward - which is why httpx was a move and this is a watch.

  **What would turn it into a move:** an archive notice, a maintainer statement, a security
  finding left unfixed, or a successor with real adoption. Absent one of those, the cost of
  switching a perceptual hash is the point: the catalog stores its exact bit output, so any
  replacement re-hashes every library or silently changes what counts as a near-duplicate.

- **Distributed task queues (Taskiq, Celery, Dramatiq) stay out of the desktop app.** They are
  *distributed* queues: their purpose is dispatching work across a network to separate worker
  processes, and each requires a broker - Redis, RabbitMQ, NATS or Kafka. Taskiq's own
  introduction says it exists because nothing could send async functions over distributed queues
  like RabbitMQ. That is a real problem, and it is not this one.

  truestill is a single-user desktop app: one process, no network, no worker fleet. Adopting one
  would mean asking a photographer to install and run Redis before organising their photos -
  precisely the install friction recorded against Immich's Docker requirement in
  `docs/org-structure-research.md`, and the thing this product is positioned against.

  **What is already there instead:** `JobManager`, roughly one module. Background threads
  in-process, SSE progress, cancel, and a per-drive lock. It covers every long operation -
  organize, verify, backup, migrate, trip apply, archive ingest, undo - with no service for the
  user to run and nothing to keep alive between sessions.

  **Where one WOULD be a reasonable choice, so this rejection is not over-read:** the
  self-hosted licensing and update server (`docs/DECISIONS.md` **D5**) is a genuinely networked
  service, and a queue is a fair question there. That is post-launch, unbuilt, and its own
  decision. Nothing here rules on it.
