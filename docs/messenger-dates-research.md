# Messenger filename dates are delivery dates, not capture dates - recon + decision

Status: **Decided and shipped (2026-07-28).** Ruling R1 of the layout correction. Recorded
because the finding is narrower than the ruling as stated, and the narrowing is the whole point.

---

## 1. The question

Does truestill's date chain use a WhatsApp/Telegram filename date to *place* a file? If so it
must stop: those names carry the moment a file was sent, received or exported, not the moment
the photo was taken.

## 2. Recon - the answer is yes

`dates.resolve_capture_datetime` evaluates four tiers and the last is
`date_from_filename(path.name)` → `DateSource.FILENAME` (`dates.py`). That function tries three
patterns (`dates.py:44-46`), and the module's own comments name the messenger conventions they
were written for:

| Pattern | Matches | Example named in the source |
|---|---|---|
| `_COMPACT_DATE` | `YYYYMMDD` | `IMG-20250804-WA0020.jpg` (WhatsApp) |
| `_ISO_DATE` | `YYYY-MM-DD` | `photo_2024-01-15_12-30-45.jpg` (Telegram mobile) |
| `_EURO_DATE` | `DD-MM-YYYY` | `photo_1@29-10-2021_09-30-00.jpg` (Telegram Desktop) |

So a 2015 holiday photo forwarded to you today was being filed under **today**. That is worse
than `Undated/`: an honest gap invites a fix, a confident wrong answer does not, and §1 already
says dates are never guessed.

## 3. The finding that narrows the ruling

**The same pattern serves screenshots, and there it is correct.**
`Screenshot_20260721_001427.png` matches `_COMPACT_DATE` too - but a screenshot's filename stamp
*is* its capture moment, written by the device at the instant of capture. Refusing the
**pattern** would have sent every screenshot in a library to `Undated/`, which is a real
regression dressed as a fix.

The refusal is therefore scoped to the **convention**, not the pattern. `NAME_PATTERNS`
(`categorize.py:46`) already identifies messenger and social files precisely and is the existing
evidence for that judgement, so `categorize.is_messenger_filename` reuses it rather than
inventing a second list that could drift from the first.

**Rejected alternative - drop the date patterns.** Simpler and wrong, per above.
**Rejected alternative - a new regex list in `dates.py`.** Two lists describing "is this a
messenger file" would disagree the first time one was extended; the categorizer's list is
already the authority and is already tested.

## 4. What shipped

`_filename_capture_date` refuses a filename date when `is_messenger_filename` matches, so such
files fall through to `DateSource.NONE` → `Undated/`. Embedded metadata is untouched: a
messenger file that still carries real EXIF is dated by it, which is pinned.

**Complexity:** `is_messenger_filename` is `O(len(NAME_PATTERNS))` anchored regex matches per
file - a constant (~15) independent of library size. The pass stays **O(n)** in files and adds
no I/O. Measured cost is in the microseconds against a per-file budget dominated by hashing in
the milliseconds; the module already documents that trade for the tiers it evaluates eagerly.

## 5. On the five tests that changed

All five used a WhatsApp filename as a *fixture* for "a file whose only date is in its name" -
none asserted that messenger dates should be trusted. Each keeps its original intent with the
fixture renamed to `IMG_20250804_120000.jpg`, an Android **camera** name (underscores, no
`-WA<n>`), whose filename date genuinely is a capture date. The FILENAME tier itself is still
exercised, and a dedicated test now pins that a screenshot name is still trusted - so the
substitution cannot be hiding the tier silently breaking.
