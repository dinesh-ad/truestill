# Truestill

Categorize and date-organize a photo and video library into a stable, browsable tree.
Audio files (voice memos, `.m4a`/`.mp3`/`.amr` and friends) are recognized, organized and
counted alongside them, but photos and videos are what Truestill is built and tuned for:

```
<destination>/
├── 2025/
│   ├── 2025-08/
│   │   ├── 2025-08 - Everyday/      <- ordinary photos from that month
│   │   └── 2025-08-14 - Goa Trip/   <- a named event, if you name one
│   └── 2025-09/
├── Screenshots/2026/2026-07/        <- non-camera sources sit beside the years
├── WhatsApp/2025/2025-08/
├── Snapseed/2023/2023-05/           <- created on the fly, no code change
└── Undated/                         <- no trustworthy date; never guessed
```

**Your years are the top level.** A photo library is a timeline first and a set of sources
second, so the year is the parent and months name themselves - `2025-08`, not a bare `08`, so a
folder still says what it is once it is copied, searched or attached somewhere on its own.
Screenshots, WhatsApp images and other non-camera sources are filed *beside* the years rather
than above them, so they never break the timeline apart.

Built for organizing a Google Photos export before it is pushed to long-term storage,
but nothing in it is Google-specific.

## The folder set is not hard-coded

Labels are **derived from each file's own evidence**, not chosen from a fixed list. A
library containing Signal, Snapseed, a flatbed scanner or a camera brand the tool has
never seen grows those folders by itself. Files whose origin cannot be proven land in
`Saved` - named that, and not `Unsorted`, because to a normal user "unsorted" reads as a
failure when these are genuinely just images saved from apps or the web, whose origin is
unknowable by design (platforms strip EXIF on upload).

## How a file is classified

Rules run in priority order and the **first** match wins:

| # | Rule | Evidence | Confidence |
|---|------|----------|-----------|
| 1 | `screenshot_metadata` | Vendor tag, e.g. `SamsungCaptureInfo=Screenshot` | high |
| 2 | `screenshot_name` | `Screenshot_*`, `Screen Shot *`, `Screenshot from *` | medium |
| 3 | `filename_convention` | Extensible table: WhatsApp `-WA<n>`, Telegram (2 conventions), Signal, Instagram, Facebook, Snapchat, Viber, WeChat, Discord, Line, … | medium |
| 4 | `software` | `Software` tag naming an application → folder named after it | low |
| 5 | `device` | `Make` + `Model` (or video `SamsungModel`) → `Camera`, or the device itself with `--by-device` | medium |
| 6 | `fallback` | nothing matched → `Saved` | low |

Order is load-bearing. Screenshots are checked **before** device metadata because a
screenshot often also carries `Make`/`Model` and would otherwise be filed as a camera
photo. Messenger filenames are checked before device metadata for the same reason:
WhatsApp strips most metadata, so the filename stamp is the more reliable signal of
where a file actually came from.

Adding a new source means adding one row to `NAME_PATTERNS` in `categorize.py`.

## How the date is chosen

1. **Embedded metadata** - `DateTimeOriginal`, then `CreateDate`, `MediaCreateDate`,
   `TrackCreateDate` (covers both photos and video containers).
2. **Filename convention** - `YYYYMMDD`, `YYYY-MM-DD`, or Telegram Desktop's
   `DD-MM-YYYY`. These are **flagged for manual review** in the report; a date parsed
   from a filename is a convention, not a guarantee.
3. **Nothing** - the file goes to `<Label>/Undated/`. Dates are never guessed.

**Filesystem mtime is never consulted.** Google Photos downloads and Takeout zips carry
the *download* time in the filesystem timestamp, so trusting mtime would file an entire
library under the day it was exported.

## Timestamps

After placing a file, its mtime/atime are set from the resolved capture date -
equivalent in intent to:

```bash
exiftool "-FileModifyDate<DateTimeOriginal" -r <folder>
```

but driven by the *same* date used for folder placement, so a file's mtime and its
year/month folder can never disagree. Disable with `--no-timestamps`.

## More than organizing

Organizing is the entry point, not the whole tool. Truestill also owns the **custody - a verified
record of where every file is safe** for the library it builds:

- **De-duplication**, two tiers - exact (SHA-256) skipped, perceptual look-alikes kept and
  *flagged*, so an original is never silently dropped for a resembling file.
- **Archive and folder rescue** (`truestill ingest --source`) - reads a folder of photos or the
  archives a service gave you (`.zip`, `.tar`, `.tgz`), and recovers the capture dates that
  survive only in the export's JSON sidecars, and bakes them losslessly into the organized
  copy. The source is never modified.
- **Drive identity and an offline catalog** - which drive holds which copy, answerable with
  the drive unplugged (`truestill where`).
- **Verification and 3-2-1 backup** - re-hash a connected drive against the catalog
  (`truestill verify`), copy the library to a second drive, and see what still exists in only
  one place (`truestill status`).
- **Configurable layout** with crash-safe migration of an existing library.
- **Trips & events** - opt-in clustering that proposes named events for you to confirm; never
  auto-named.
- **Space-safe relocation**, all opt-in and verify-gated: `--move`, `--in-place` (moves by
  rename rather than copying, with `truestill undo-organize` to reverse it), and
  `truestill reclaim`.

There is also **`truestill-app`**, a local web UI on `127.0.0.1` - token-authenticated,
server-rendered, no bundler and no npm. It is co-equal with the CLI, not a replacement: both
front-ends call the same core library.

## Requirements

- Python ≥ 3.13, [uv](https://docs.astral.sh/uv/)
- `exiftool` - the only tool that reads photo EXIF, video container tags and vendor
  MakerNotes through one interface:

```bash
sudo apt install -y libimage-exiftool-perl
```

Runtime Python dependencies are deliberately minimal and each is justified in writing
(`docs/IMPLEMENTATION_STANDARDS.md` §7): `imagehash`, `pillow` and `pillow-heif` in the core
(perceptual hashing needs image decoding, which the stdlib cannot do), and `starlette` +
`uvicorn` in the app. The CLI adds none. Hashing, SQLite, concurrency and all path/date work
are stdlib.

## Install

```bash
make install       # uv sync --all-packages --group dev
```

## Usage

The CLI is subcommand-based. **Dry run is the default** - nothing is written without
`--apply`:

```bash
uv run truestill organize <source> <destination>
uv run truestill organize <source> <destination> --report reports/plan.json
uv run truestill organize <source> <destination> --apply

uv run truestill-app                 # the local web UI
```

`truestill --help` lists every subcommand: `organize`, `ingest`, `drives`, `undo-organize`,
`where`, `verify`, `status`, `config`, `reclaim`, `migrate-layout`.

Frequently used `organize` flags:

| Flag | Effect |
|------|--------|
| `--apply` | Actually write files. Without it, nothing is touched. |
| `--move` | Move instead of copy. Default is copy, leaving the source intact. |
| `--in-place` | Reorganize in this same folder by rename, so no second copy is needed and nothing is rewritten. Use this when you do not have space for a full copy. Reversible with `truestill undo-organize` - which is also what covers a power cut on a FAT32 or exFAT drive, since those cannot make a rename crash-safe. |
| `--by-device` | Name capture folders after the device (`samsung SM-A546B`) instead of `Camera`. |
| `--events` | Propose named events for camera clusters (you name or skip them). |
| `--skip-undated` | Skip undateable files instead of copying them to `Undated/`. |
| `--all-files` | Include non-media extensions. |
| `--no-rename` | Do not add the `YYYYMMDD_HHMMSS_` prefix to copies. |
| `--no-timestamps` | Do not set mtime from the capture date. |
| `--report PATH` | Write the full per-file decision report as JSON. |

## Safety

- **Dry run by default** - `--apply` is the only thing that writes. A read never writes.
- **Copy, not move, by default** - the source tree survives a bad run. The three exceptions
  (`--move`, `--in-place`, `reclaim`) are each opt-in, individually confirmed, and never
  remove a source without proof that the content survives.
- **Never overwrites.** On a name collision the file is hashed: identical content is
  reported as a duplicate and skipped; different content is written alongside with a
  `_1` suffix.
- **Dates are never invented.** No date evidence means `Undated/`.
- **Nothing is silently dropped.** Skipped, refused and unverifiable outcomes are counted and
  named in the report - never folded into a success total.
- **Your photos never leave your machine.** No telemetry, and nothing about your library is
  ever transmitted (`docs/DECISIONS.md` D5).

## Development

```bash
make check         # lint + format-check + typecheck + test
make lint
make format
make typecheck
make test

make e2e-install   # once: fetch the chromium build
make e2e           # browser end-to-end suite (opt-in; not part of `make check`)
```

`make check` is green on a fresh clone with no browser installed - the E2E layer is
deliberately opt-in.

## Documentation

Start with [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md): where the project stands, what
ships next, and the standing rules. [`CLAUDE.md`](CLAUDE.md) carries the full document map.

## Licence

Truestill is licensed under the [Apache License 2.0](LICENSE). The published source is
open-core: the repository is Apache-2.0; paid Pro capabilities (when they ship) attach through
the capability seam rather than a separate closed tree (`docs/DECISIONS.md` D7, D6).

> **Status:** pre-1.0 and not yet published. This README is deliberately factual rather than
> promotional; the newcomer-facing rewrite with screenshots is a tracked pre-launch task.
