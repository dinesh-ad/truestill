# (ajq) PORTABLE EXPORT: NOTHING TRUESTILL RECORDS SURVIVES LEAVING TRUESTILL

*Body of backlog entry `(ajq)`, under **Ideas / deferred**. The index is
[`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-09-01 (P185) as the **scoped remainder of a refusal**, so the research behind it is not
re-derived by the next person who asks the same question. `(acg)` ruled it out of its own scope and
said why; this is where it lives instead.

## 1. THE QUESTION

`(acg)` made album membership survive a **rebuilt Truestill catalog**. It does not make anything
survive **leaving Truestill**. A user who stops using the product still loses the organising work,
because `.truestill-decisions.json` is a Truestill document that only Truestill reads.

## 2. THE FIELD'S ANSWER, AND IT IS UNANIMOUS

- **PhotoPrism #721** - remove and reinstall the container and *"the photos_albums is empty"*, no
  albums in the UI, on an unmodified library.
- **A 2018 survey of Piwigo, Gallery2 and Silvermine** - *"None of the systems had a mechanism to
  export images and metadata in a portable format... There seems to be no path to create a portable
  album using any of those systems."*
- **digiKam** keys album roots on the **volume UUID**: replace a drive and every album path breaks
  though the folders are identical.
- **A user advising other users (Marder, Feb 2026)** - *"Albums in Immich are stored only in the
  database. If you leave Immich, your album organization is gone... Prefer tags over albums so your
  organizational work is portable."* His reason is the mechanism: tags reach XMP sidecars as
  `digikam:TagsList`, which digiKam and Lightroom read back.

🔑 **The only portable mechanism anyone uses is a sidecar file beside the photograph.**

## 3. WHY `(acg)` REFUSED IT, RECORDED SO IT IS NOT RE-ARGUED

1. **File count.** The product writes **one** file per drive root today -
   `DECISIONS_NAME = ".truestill-decisions.json"`. Per-photo XMP on the library measured in
   [`soak-five-record.md`](../../soak-five-record.md) (**10,745 media files**) is **10,745 new
   files** where there is now one.
2. 🔑 **It creates a two-file atomicity problem the product does not have.** Every organize,
   migrate, rename and undo would have to move a photo *and* its sidecar together or leave a lie
   behind. `(aba)` spent a session on what a single stale path costs; this multiplies that by every
   file.
3. **Stray per-file companions are already a defect class here** - `organizer.py` carries a label
   for exiftool `*_original` sidecars precisely so they are never counted as photographs.
4. **It answers a different question** from the one `(acg)` was ranked on.

## 4. WHAT `(acg)` LEFT IN PLACE FOR IT

**The hard half is done.** `catalog.Catalog.album_members` returns `name -> [sha256]`, which is
exactly the input an exporter needs; nothing in that ruling forecloses this one. What is missing is
a writer and a decision about where the file goes.

## 5. WHAT IS NOT ESTABLISHED

- **Whether any user has asked.** The field evidence above is other products' users, not Truestill's.
  [`user-evidence-log.md`](../../user-evidence-log.md) carries no entry for this.
- **Whether `exiftool` writing XMP per file is affordable**, unmeasured - though
  [`preview-performance-profile.md`](../../preview-performance-profile.md) measured exiftool at
  **74% of cloud-mount wall** on a read-only pass, which is not encouraging.
- **Whether tags, rather than albums, are the right noun** - Marder's actual advice. Truestill has
  no tags.

## RELATED

`(acg)` (shipped 2026-09-01 - the rebuild half, and the refusal this entry records),
`(ajp)` (the orphan defect found beside it), `(abd)` (one catalog or many).
