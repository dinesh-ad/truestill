# Google Takeout (Google Photos) format - field notes

Research for **Takeout Rescue Mode**. Verified against current (2024–2026) sources; the
format drifts, so this records what is true now and what is *inconsistent by design*.
Primary sources are linked at the bottom.

> **One-line summary:** Takeout scatters each photo's real metadata into a JSON *sidecar*,
> stamps the files with the download date, and ships every album as a folder of **byte-identical
> duplicate copies**. The sidecar naming is inconsistent across (and within) exports.

## 1. Sidecar naming - the messy part

For a media file `IMG_1234.jpg`, its metadata sidecar may appear as **any** of these, and
different variants co-occur in the same export:

| Variant | Example | Notes |
|---|---|---|
| Full-name + `.json` | `IMG_1234.jpg.json` | The long-standing classic form |
| Stripped-ext + `.json` | `IMG_1234.json` | Also classic; inconsistent which you get |
| **Supplemental** (late 2024+) | `IMG_1234.jpg.supplemental-metadata.json` | The current default naming |
| **Truncated supplemental** | `IMG_1234.jpg.supplemental-metada.json`, `…supplemental-me.json`, `…supplementa.json`, `…suppl.json` | Google caps the **total filename length** (~46 chars for the media stem; the whole sidecar name gets clipped), so the `supplemental-metadata` word is cut at arbitrary points |
| **Duplicate-number suffix** | media `IMG_1234(1).jpg` → sidecar `IMG_1234.jpg(1).json` | The `(1)` moves to **after** the extension, before `.json`. With supplemental naming this appears as `…supplemental-metadata(1).json` too - inconsistent |

**Edge cases that must be handled:**

- **`-edited` variants** (`IMG_1234-edited.jpg`) get **no sidecar of their own** - strip the
  `-edited` suffix and use the original's sidecar. Edited files appear only in year folders,
  not albums.
- **Live Photos** (an `.HEIC`/`.jpg` + paired `.MP4`) may share one sidecar; the video half
  often has none.
- **Missing sidecars** - Google sometimes omits the JSON entirely for a file. Must degrade
  gracefully (fall back to embedded EXIF / filename, never crash).
- **Sidecar without media** - an orphan `.json` with no matching file; ignore.

**Robust matcher (what the mature tools converge on):** build an index of every `*.json` in a
folder once, then for each media file try candidate keys in priority order (exact,
stripped-ext, supplemental, truncated-prefix, `(n)`-relocated), each an O(1) lookup. Never
scan all sidecars per media file. Match within the **same directory** only.

## 2. Authoritative metadata fields

Sidecar JSON structure (fields we care about):

```json
{
  "title": "IMG_1234.jpg",
  "description": "Beach sunset with the family",
  "photoTakenTime": { "timestamp": "1692113136", "formatted": "Aug 15, 2023, 2:25:36 PM UTC" },
  "creationTime":   { "timestamp": "1692200000", "formatted": "..." },
  "geoData":     { "latitude": 36.778259, "longitude": -119.417931, "altitude": 15.0 },
  "geoDataExif": { "latitude": 36.778259, "longitude": -119.417931, "altitude": 15.0 }
}
```

- **Capture date → `photoTakenTime.timestamp`.** Unix epoch **seconds, as a string, in UTC.**
  Authoritative for *when the photo was taken*.
- **`creationTime.timestamp`** is the *upload* time - a poor fallback (often months off). Use
  only if `photoTakenTime` is absent, and flag it as low-confidence.
- **GPS → `geoData` / `geoDataExif`** decimal degrees. **`(0.0, 0.0)` means "no GPS"**, not
  Null Island - treat all-zero as absent. Prefer `geoDataExif` (from the file) then `geoData`.
- `title` is the original filename; `description` is user text.

### ⚠️ Timezone: the load-bearing caveat

`photoTakenTime` is **UTC with no local offset recorded.** vaeon's date model is *naive local
wall-clock* (EXIF `DateTimeOriginal`, which is already local). Feeding a UTC instant into that
model naively shifts the time-of-day by the local offset and, for captures near midnight, can
shift the **date** - which would change the `YYYY/MM` folder and the filename prefix. This is
the single biggest correctness risk of the feature and is addressed in the plan (§Plan).

## 3. Folder layout & album duplication

- **`Photos from YYYY/`** - year folders keyed on `photoTakenTime`'s year. **Most complete**:
  contain every photo *and* the `-edited` versions.
- **Album folders** - named by album title (or `Untitled`, `Untitled(1)`, …). Contain
  **byte-for-byte duplicate copies** of photos already in the year folders (no edited versions).
  An album folder may carry an album-level `metadata.json` (album title/description).
- **Consequence:** a photo in *k* albums appears **k+1 times**, identical bytes. This is the
  bulk of Takeout's notorious size blow-up.

## 4. How this composes with vaeon (why it's mostly assembly, not new logic)

| Takeout problem | vaeon capability that already solves it |
|---|---|
| Album duplicate copies | Exact SHA-256 dedup collapses byte-identical copies (tier 1, skip) |
| `-edited` near-duplicates | Perceptual dedup keeps **both** and flags - the edit is preserved, not dropped |
| Stripped dates | The dating evidence chain - needs a new **Takeout-sidecar tier** inserted |
| No capture date at all | `Undated/` (never guessed) |
| Wrong file timestamps | We already ignore mtime for dating and set mtime from capture date |
| Album → event mapping | The existing `--events` review flow can pre-seed names from album titles |

The only genuinely new pieces are: the **sidecar matcher**, a **JSON→evidence adapter** (with
the timezone handling), **album-membership recording** (catalog), and an **exiftool write step**
to bake recovered metadata into the organized copy.

## 5. Engineering flags to resolve before building (see §Plan in the review message)

1. **Timezone** (§2) - the big one. Proposed: EXIF-local wins when present & sane; else use
   `photoTakenTime` with an explicit, documented policy (UTC date, optional `--tz` offset).
2. **Writing EXIF into the copy** changes the copy's bytes (metadata only; exiftool does **not**
   re-encode pixels, so it's lossless). This is intended enrichment but is a departure from
   "the copy is byte-identical to the source" - worth stating loudly. Videos exiftool can't
   write get a documented fallback.
3. **Matcher correctness > cleverness** - an explicit, well-tested candidate ladder beats a
   fuzzy heuristic; fuzzy matching risks attaching the *wrong* photo's date.

## Sources

- google-photos-exif - matching logic & `-edited`/`(1)` rules:
  <https://github.com/mattwilson1024/google-photos-exif>
- GooglePhotosTakeoutHelper #353 - supplemental-metadata rename & truncation:
  <https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper/issues/353>
- immich-go #652 / metadata-extraction - supplemental handling, matching ladder:
  <https://github.com/simulot/immich-go/issues/652> ·
  <https://deepwiki.com/simulot/immich-go/4.1-metadata-extraction>
- ente #4953 - real-world supplemental-metadata import breakage:
  <https://github.com/ente/ente/issues/4953>
- Metadata Fixer - JSON schema, duplicate-photo explanation:
  <https://metadatafixer.com/learn/google-takeout-json-files-explained> ·
  <https://metadatafixer.com/learn/google-takeout-duplicate-photos-explained>
- google-photos-metadata-fix - Takeout structure (year vs album folders):
  <https://deepwiki.com/joshua-holmes/google-photos-metadata-fix/9.1-google-takeout-structure>
