# The golden corpus snapshot - evidence, not CI coverage

`input-dates.tsv` records, for every media file under one real machine's
`/data/TruestillLibrary/Input`, what the date resolver decided, which `DateSource` and tag it
came from, and the placement `plan` would produce. Read-only both ways: recording it moves
nothing, and nothing in the product reads it.

```
uv run python scripts/golden_corpus.py record   # regenerate after a deliberate rule change
uv run python scripts/golden_corpus.py check    # compare today's code against the snapshot
```

⚠ **ON DEMAND ONLY - this never runs in CI, and that is a stated limit, not an oversight.**
The corpus is Ad's machine; a runner does not have it. A fixture that cannot run in CI must
say so rather than look like coverage (`(agq)`'s lesson: silence is not coverage). What CI
*does* own is the differential logic - `test_golden_corpus_diff.py` pins that a rule change
moving thousands of files reads as one counted `source -> source` line per transition with
capped, announced examples, never a wall of paths.

**Measured 2026-08-23** on ext4 (`/dev/nvme0n1p1`, `/data`): `record` 49.9 s, `check` 49.0 s
over 7,790 media files (17,237 files, 24 GB under the root) - a tool someone re-runs, not a
ritual. The snapshot header carries machine, filesystem, count and the full source
distribution, so a distribution shift appears in the first screen of any diff.

The corpus includes the two format repos (`exif-samples`, `metadata-extractor-images`) copied
under `Input/` - so the snapshot spans format edges as well as one lineage's real library, per
the corpus doctrine in `CLAUDE.md`.
