# (ald) A REGEX CENSUS UNDER-COUNTED A SHAPE BY 20%, AND THE GUARD FOUND THE REST ON ITS FIRST RUN.

*Body of backlog entry `(ald)`, under **Records - evidence, explicitly not work**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

**Filed 2026-09-18 (P252). Record only - do not build.** The work it came out of shipped in
`0d57696`; what is kept here is the **method**, not the defect.

## WHAT HAPPENED

Diagnosing three red nightly runs found a test slicing source between two independently-located
markers, which had inverted into `''`. The standing rule is to census the class rather than fix
the instance, so the class was censused **with `git grep`**:

```sh
git grep -nE '\[[^]]*\.index\([^)]*\)[[:space:]]*:[[:space:]]*[^]]*\.index\(' -- '*.py'
```

It returned **four** sites, and that number was reported as the census. The guard written from it -
`test_no_test_slices_source_between_two_markers.py`, which walks the AST instead - failed on its
**first run** against a **fifth**:

```
tests/e2e/test_settings_is_a_shelf_not_a_task_screen.py:_settings_markup
```

## WHY THE REGEX COULD NOT SEE IT

The fifth site is the same expression spread over four lines:

```python
    return markup[
        markup.index('id="screen-settings"') : markup.index(
            "</section>", markup.index('id="screen-settings"')
        )
    ]
```

A line-oriented pattern cannot match an expression that is not on a line. **Nothing about the
regex was wrong**; it was the wrong instrument for a shape whose definition is syntactic.

## THE RULE THIS IS EVIDENCE FOR

⚠ **A census of a SYNTACTIC shape is run with a parser, and a census run with `grep` reports a
floor rather than a count.** `git grep` remains right for a *string* - a claim, a name, a spelling -
which is what `(aka)`'s sweep rule is about and that rule is untouched. The distinction is whether
the thing being counted is text or structure.

**The cost was not the miss.** It was that the miss was reported as a completed census, in a turn
whose own standard is that a census is re-run before it is acted on. The fifth site was found by
luck of sequencing - the guard happened to be written before the report was believed.

⚠ **This is the second instrument-choice failure recorded against a census in this project.**
`(alb)` recorded one where the count was taken on *physical lines* while the table grouped them,
so 20 sites read as 16 and the entry contradicted itself in three places. Same family: the number
was produced by a tool that was not counting the thing the sentence claimed.

## WHAT IS NOT PROPOSED

- **A guard on censuses.** There is nothing to assert: a guard would have to know which instrument
  a human chose for a count that is not in the tree. `(ago)`'s bar refuses it.
- **Re-censusing the other closed entries.** Not retroactive, for the reason the absence
  convention gives about going red on the past.
