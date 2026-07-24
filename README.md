# vaeon

Categorize and date-organize a photo/video library into a stable, browsable tree:

```
<destination>/
├── Camera/2025/08/
├── WhatsApp/2025/08/
├── Screenshots/2026/07/
├── Telegram/2024/01/
├── Snapseed/2023/05/           <- created on the fly, no code change
└── Unsorted/Undated/
```

The month folder is the bare two-digit month (`07`); the year is already the parent
folder, so `2026-07` would just repeat it.

Built for organizing a Google Photos export before it is pushed to long-term storage,
but nothing in it is Google-specific.

## The folder set is not hard-coded

Labels are **derived from each file's own evidence**, not chosen from a fixed list. A
library containing Signal, Snapseed, a flatbed scanner or a camera brand the tool has
never seen grows those folders by itself. Only files with no identifying evidence at all
land in `Unsorted`, which is deliberately a dead end rather than a dumping ground — a
growing `Unsorted` is a signal that a rule is worth adding.

## How a file is classified

Rules run in priority order and the **first** match wins:

| # | Rule | Evidence | Confidence |
|---|------|----------|-----------|
| 1 | `screenshot_metadata` | Vendor tag, e.g. `SamsungCaptureInfo=Screenshot` | high |
| 2 | `screenshot_name` | `Screenshot_*`, `Screen Shot *`, `Screenshot from *` | medium |
| 3 | `filename_convention` | Extensible table: WhatsApp `-WA<n>`, Telegram (2 conventions), Signal, Instagram, Facebook, Snapchat, Viber, WeChat, Discord, Line, … | medium |
| 4 | `software` | `Software` tag naming an application → folder named after it | low |
| 5 | `device` | `Make` + `Model` (or video `SamsungModel`) → `Camera`, or the device itself with `--by-device` | medium |
| 6 | `fallback` | nothing matched → `Unsorted` | low |

Order is load-bearing. Screenshots are checked **before** device metadata because a
screenshot often also carries `Make`/`Model` and would otherwise be filed as a camera
photo. Messenger filenames are checked before device metadata for the same reason:
WhatsApp strips most metadata, so the filename stamp is the more reliable signal of
where a file actually came from.

Adding a new source means adding one row to `NAME_PATTERNS` in `categorize.py`.

## How the date is chosen

1. **Embedded metadata** — `DateTimeOriginal`, then `CreateDate`, `MediaCreateDate`,
   `TrackCreateDate` (covers both photos and video containers).
2. **Filename convention** — `YYYYMMDD`, `YYYY-MM-DD`, or Telegram Desktop's
   `DD-MM-YYYY`. These are **flagged for manual review** in the report; a date parsed
   from a filename is a convention, not a guarantee.
3. **Nothing** — the file goes to `<Label>/Undated/`. Dates are never guessed.

**Filesystem mtime is never consulted.** Google Photos downloads and Takeout zips carry
the *download* time in the filesystem timestamp, so trusting mtime would file an entire
library under the day it was exported.

## Timestamps

After placing a file, its mtime/atime are set from the resolved capture date —
equivalent in intent to:

```bash
exiftool "-FileModifyDate<DateTimeOriginal" -r <folder>
```

but driven by the *same* date used for folder placement, so a file's mtime and its
year/month folder can never disagree. Disable with `--no-timestamps`.

## Requirements

- Python ≥ 3.13, [uv](https://docs.astral.sh/uv/)
- `exiftool` — the only tool that reads photo EXIF, video container tags and vendor
  MakerNotes through one interface:

```bash
sudo apt install -y libimage-exiftool-perl
```

There are **no runtime Python dependencies**.

## Install

```bash
make install       # uv sync --group dev
```

## Usage

Dry run is the default. Nothing is written without `--apply`:

```bash
uv run vaeon <source> <destination>
uv run vaeon <source> <destination> --report reports/plan.json
uv run vaeon <source> <destination> --apply
```

| Flag | Effect |
|------|--------|
| `--apply` | Actually write files. Without it, nothing is touched. |
| `--move` | Move instead of copy. Default is copy, leaving the source intact. |
| `--by-device` | Name capture folders after the device (`samsung SM-A546B`) instead of `Camera`. |
| `--all-files` | Include non-media extensions. |
| `--no-timestamps` | Do not set mtime from the capture date. |
| `--report PATH` | Write the full per-file decision report as JSON. |

## Safety

- **Dry run by default** — `--apply` is the only thing that writes.
- **Copy, not move, by default** — the source tree survives a bad run.
- **Never overwrites.** On a name collision the file is hashed: identical content is
  reported as a duplicate and skipped; different content is written alongside with a
  `_1` suffix.
- **Dates are never invented.** No date evidence means `Undated/`.

## Development

```bash
make check     # lint + typecheck + test
make lint
make format
make typecheck
make test
```
