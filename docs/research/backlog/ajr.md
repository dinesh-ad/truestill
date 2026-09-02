# (ajr) A LETTER CITED IN CODE CAN RESOLVE TO NO ENTRY, AND NOTHING CHECKS THAT DIRECTION.

*Body of backlog entry `(ajr)`, under **Internal / tooling**. The index is
[`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

- **(ajr) A LETTER CITED IN CODE CAN RESOLVE TO NO ENTRY, AND NOTHING CHECKS THAT DIRECTION.**
  Filed 2026-09-02 (P186) from `(ajl)`.

## WHAT IS WRONG, AND WHERE

`24986b0` (`feat(aiq)`) wrote `` `(ajl)` `` into `service/organize.py`, `app.js`, `cli.py` and
`models.py` - seven citations - as if a letter had been allocated. The record went under `(aiq)`
gap 1 and no `(ajl)` row was ever written. A code comment citing a letter nobody can look up
implies a record that does not exist, which is worse than no citation.

Four guards read letters, all in one direction: `test_backlog_references.py`,
`test_backlog_letters_are_unique.py`, `test_backlog_headlines_agree.py` and
`test_closed_entries_leave_the_backlog.py` read the two index files;
`test_live_documents_cite_code_that_exists.py` checks that a document's citation reaches code.
None reads a citation in code and asks whether the letter is defined.

## MEASURED 2026-09-02

```
defined=$(grep -ohE '^- (~~)?\*\*\([a-z]{1,3}\)' docs/BACKLOG.md docs/SHIPPED.md | grep -oE '\([a-z]+\)' | tr -d '()' | sort -u)
cited=$(git grep -ohE '`\([a-z]{1,3}\)`' -- 'packages/*/src/*.py' 'packages/truestill-app/src/truestill_app/static/app.js' | grep -oE '[a-z]+' | sort -u)
comm -13 <(echo "$defined") <(echo "$cited")
```

| | count |
|---|---|
| letters cited in code, backtick form | 151 |
| letters defined in the two index files | 285 |
| cited and defined nowhere | **1** - `(ajl)` |

The backtick form is the discriminator. The bare `\([a-z]{1,3}\)` matches sixty-odd call
arguments - `(db)`, `(exc)`, `(key)` - and is useless. The `~~` strikethrough form must count as a
definition or `(gg)` and `(mm)` read as undefined.

## THE QUESTION THIS ENTRY CARRIES

**Is one a rate?** A guard here would be red on the day it is written, over a class no existing
guard covers - `(ago)`'s bar. But one instance found by a state check is evidence of one
instance, and `(ajl)` is now recorded, so the guard would be green the moment it landed. Re-run
the census above before building. If it reads zero again, this is a ruling that the pattern is
rare and the census is the guard; if it grows, build the test.

The industry shape is annotated-TODO checking - CI fails when a `TODO` names a ticket that does
not exist or is closed ([todocheck](https://github.com/presmihaylov/todocheck)). Here the ticket
is a letter and the tracker is two markdown files, so the check is the three lines above.

## RELATED

`(agf)` - the same failure in the letters section's own history, cited before its entry existed.
`(aht)`, `(ahz)` - a symbol-name check standing in for a capability check, the neighbouring class.
