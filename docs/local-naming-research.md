# A local naming helper: what was measured, and what the measurement was worth

> **MEASUREMENT RECORD, 2026-08-10/11. Nothing is built, nothing is recommended, and no model is
> named here on purpose** - the landscape moved twice in the ten days this was discussed, so a
> pinned name would be the first thing to go stale. Sizes, licences and candidates live in the
> session that measured them.
>
> This file exists for one reason: **two rounds of numbers were produced and both are void.**
> Without this record the next person finds the conclusions and not the reasons they cannot be
> cited.

## 1. The numbers are void, and not in a direction that can be corrected for

Both rounds fed **leaf folder names as standalone strings**. They are not standalone. Measured in
the catalog on 2026-08-11:

```
TruestillLibrary/Input/2014/Wayanad '14/Gokul CAM        493 files
TruestillLibrary/Input/2014/Wayanad '14/Day 1/Vj 1       172 files
```

`Wayanad '14` is **2,063 files across 13 folders**, with device and day subfolders beneath it.
`Gokul CAM`, `Day 1` and `Vj 1` were each asked about as though a user had named a folder that and
nothing else.

**The shipped rule is a hierarchy rule** - deepest ancestor level, 0 to 3, whose majority is >= 70%
(`folder-name-suggestion-research.md`). Flattening the input removed the structure the rule exists
to navigate, so what was measured is not a harder version of the question; it is a different one.
Every per-case score from both rounds is therefore **void rather than pessimistic**, and none of it
should be quoted. `ENGINEERING_STANDARD.md` §4's seventeenth member is the rule this broke: a
fixture drawn from the library that quietly drops the property under test.

## 2. One token in the fixture was a transcription, and it was load-bearing

The fixture used `Sivaram`. The folder is **`Siveram & My Treat ILP`** (45 files); `Sivaram`
appears nowhere in the catalog. It mattered, because the two were measured against the gazetteer
tiers and they do not agree:

| | `cities500` | `allCountries` |
|---|---|---|
| `Siveram` (the real folder) | 0 rows | **0 rows** |
| `Sivaram` (the transcription) | 0 rows | **3 rows** |

So the published reason for preferring the thinner tier - *"the larger tier reintroduces Sivaram"* -
was evidence about a string nobody has. **The conclusion survives on real tokens and the evidence
had to be replaced:** `Wayanad` (1 row in `allCountries`, 2,063 real files) and `Phoenix Mall`
(1 row, 46 real files) are both real folder names the larger tier would make strippable. Same
direction, different examples.

## 3. What is unaffected, because it is a property of the data

- **`Trichy` resolves to `Tiruchirappalli`** through the `alternatenames` column of `cities500`.
- **Matching per WORD is unsafe on this library, and the evidence is the strongest available:**
  `Gokul` - a person's name, in 634 of the maintainer's files - is a populated place in India
  (pop 4,351) and would be stripped as a place. `Sea` resolves to Seattle, `Wedding` to a district
  of Berlin, `Day` to Dayton. Only whole segments split on explicit separators are safe.
- **`Trichy~Thanjavur~Gokul` + U+0060 + `s Marriage` is real**, 141 files, captured 2015-10-25.
  Verified against the catalog after it was doubted; `folder-name-suggestion-research.md` records
  the character correctly.

## 4. An open question for the maintainer, recorded rather than decided

**394 of 2,695 catalog rows have `source_path` inside the fenced `Crypto Folder`**, and three
strings used as fixture came from there. Nothing was read from the mount - they were in the catalog
and in the documentation before the fence was reinstated. But `decisions.py` excludes path hints
from the drive document precisely so that *the existence of a Crypto Folder* does not travel, while
these documents quote its contents by name.

**Should folder names from inside the fence keep appearing in documentation?** Unanswered here on
purpose.

**Whichever way it is answered, the dated records must not be redacted**, and the reason is that
their rules are *derived from* those exact strings. The U+0060 finding is a claim about one folder.
The 70% threshold is documented as untuned because the Wayanad cluster sits at 70.4%. "No spelling
correction, ever" is justified by naming the proper nouns no dictionary holds. Replace the names
with placeholders and each rule becomes an assertion with its evidence removed - which is the same
damage as rewriting a record to match the present.
