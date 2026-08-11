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
had to be replaced:** `Wayanad` (1 row in `allCountries`, 2,063 real files) and a mall-named folder
(1 row, 46 real files) are both real folder names the larger tier would make strippable. Same
direction, different examples.

## 3. What is unaffected, because it is a property of the data

- **A colloquial short name resolves to its official long form** through the `alternatenames`
  column of `cities500` - the case that motivated the split, and the one no small model knew.
- **Matching per WORD is unsafe on this library, and the evidence is the strongest available:**
  `Gokul` - a person's name, in 634 of the maintainer's files - is a populated place in India
  (pop 4,351) and would be stripped as a place. `Sea` resolves to Seattle, `Wedding` to a district
  of Berlin, `Day` to Dayton. Only whole segments split on explicit separators are safe.
- **The folder that motivated the segmentation rule is real** - 141 files, captured on one day in
  2015 - and it carries two `~` separators with a **U+0060** where an apostrophe belongs. Verified
  against the catalog after it was doubted. The name itself is not reproduced here: the shape is
  the whole of the argument, and the shape is what survives redaction.

## 4. Memory: the advertised lever does nothing, and the effective one is not what it looks like

Measured 2026-08-11, three sizes, CPU only, context 512, peak RSS from `VmHWM`. **Deliberately no
model or version named** - the family moved three releases during the ten days this was discussed,
so a pinned name would be the first thing to rot. Sizes and quantisations are what reproduce.

| size | quant | KV cache | file | peak RSS | RSS - file |
|---|---|---|---|---|---|
| ~0.8B | Q4_K_M | f16 | 533 MB | 885 MB | 352 MB |
| ~0.8B | IQ4_XS | q8_0 | 493 MB | **682 MB** | 189 MB |
| ~2B | Q4_K_M | f16 | 1,281 MB | 1,929 MB | 648 MB |
| ~2B | IQ4_XS | q8_0 | 1,173 MB | **1,331 MB** | 158 MB |
| ~4B | Q4_K_M | f16 | 2,741 MB | 4,291 MB | 1,550 MB |
| ~4B | IQ4_XS | q8_0 | 2,477 MB | **2,739 MB** | 262 MB |

**KV-cache quantisation is worth 5 MB and is the wrong lever.** At context 512 the cache is
negligible - `q8_0` against `f16` moved 885 to 879, 1,929 to 1,924, 4,291 to 4,289. Raising context
to 4096 added only ~40 MB. A folder name is a few tokens, so anyone reaching for cache
quantisation here is spending effort on nothing. **This inverts the advice** that cache
quantisation is the standard answer for a model that is slightly too big: it is, for long-context
work, and this is not that.

**The effective lever is weight format, and not for the reason it is sold.** `IQ4_XS` saves ~108 MB
of *file* at 2B and **593 MB of peak RSS**. The `RSS - file` column is where it shows: 648 MB of
overhead above the weights becomes 158 MB. Same pattern at all three sizes (352 to 189, 648 to 158,
1,550 to 262), so it is a property of the format rather than a measurement artefact of one size.
Whatever that overhead is - repacking, compute buffers - the K-quant path allocates it and this
format does not.

**Not below 4 bits.** An external on-device study measured a ~1B model losing MMLU 46.3 to 43.1 at
3-bit and to 31.4 at 2-bit; small models have the least redundancy to spare. Not tried here, and
recorded so nobody tries it as the next step.

**And the constraint this was optimised against did not exist.** The "1 GB working ceiling" was a
phrase repeated between two documents with no constant, gate or test behind it - see
`ENGINEERING_STANDARD.md` §4's thirty-fifth member. For a **user-invoked subprocess** that someone
triggers and waits for, on a 22 GB machine, 1,331 MB is unremarkable. The measurements above stand;
the ranking they were being used to justify does not.

## 5. The case nothing solves, recorded so it is not rediscovered

**A folder named as a company cohort code followed by a venue** - the shape `<company> <batch-code>
<venue>` - was returned unchanged or as `NONE` by every size, at every quantisation, in every round,
including the round where the paths carried their real nesting. The correct reading keeps the venue
and drops the cohort prefix.

**The gazetteer cannot help either**, and that is the useful half: the venue is a shopping mall, and
a populated-places gazetteer does not contain malls. So this case is outside both halves of the
split - the data source has no row for it, and the model has no reliable knowledge of it (every size
invented a different long name for it when asked directly, and none said it did not know).

It is recorded as **known-unsolvable by the measured approaches**, not as an open gap. A future
attempt needs a different source - a POI dataset (`(acu)`) - or the user typing the name, which is
what the screen already offers.

## 6. THE DECIDING MEASUREMENT: the model never beats the rules on this library

Everything above characterises the model. **None of it compared the model to the thing it must
beat**, which is the folder rule that already ships. Measured 2026-08-11, and it is why the line is
filed rather than built.

**The clusters are real, not a fixture.** The dated files under the unfenced pair form **10
clusters** by consecutive capture day - the grouping the screen actually feeds `suggest_name`, and
the grouping two earlier rounds got wrong. The rules produce a usable name on **9 of 10**; the
tenth is the cohort-prefix case in §5.

| cluster shape | rules | model, three candidates |
|---|---|---|
| eight single-folder clusters | the folder name, tidied | the same string, verbatim |
| two of those | year stripped | **keeps the year the rules strip** |
| the four-day trip | `Wayanad` | `Wayanad '14`, three times - keeps the year, and offers one reading in three slots |
| the venue cluster | the folder name | unchanged; §5's case, still unsolved |

**Top candidate identical-or-worse on 10 of 10, strictly worse on 3.** The one place it adds
anything is a second candidate on the single cluster spanning two folders, and that candidate is
§5's unsolvable case, unsolved. A model that keeps a year the rules remove, and fills three
candidate slots with one reading, is undoing work that already ships.

⚠ **A RIG FAULT WAS CAUGHT BEFORE IT BECAME A FINDING, and that is worth more than the result.**
The first run returned every candidate with a leading `/`, which reads exactly like the model
echoing its input - the failure this record's own §1 is about. It was **the prompt**: folders were
listed as paths. Re-run with a path-free listing, zero echoes, and the table above.

That is the **fourth** appearance of this class here and **the first that did not reach a report**.
The fault was mine both times; the difference was **reading the candidates rather than the score**.
A score is a number that survives a broken rig, and the strings did not.

### What this does not prove, stated in both directions

This library's folders were **named by hand**. The feature's premise is that a model reads a
*messy* folder better than rules do, and there are no messy folders here to test it on. The premise
is therefore **untested, not disproved** (`ENGINEERING_STANDARD.md` §4, twenty-first member: one
library is a test bed, never a specification).

And the converse holds with equal force: **a decision to build still needs evidence, and there is
none** on the only library that can be measured.

## 6. An open question for the maintainer, recorded rather than decided

**394 of 2,695 catalog rows have `source_path` inside the fenced folder**, and three
strings used as fixture came from there. Nothing was read from the mount - they were in the catalog
and in the documentation before the fence was reinstated. But `decisions.py` excludes path hints
from the drive document precisely so that *the existence of that folder* does not travel, while
these documents quote its contents by name.

**Should folder names from inside the fence keep appearing in documentation?** Unanswered here on
purpose.

**Whichever way it is answered, the dated records must not be redacted**, and the reason is that
their rules are *derived from* those exact strings. The U+0060 finding is a claim about one folder's punctuation.
The 70% threshold is documented as untuned because the Wayanad cluster sits at 70.4%. "No spelling
correction, ever" is justified by naming the proper nouns no dictionary holds. Replace the names
with placeholders and each rule becomes an assertion with its evidence removed - which is the same
damage as rewriting a record to match the present.
