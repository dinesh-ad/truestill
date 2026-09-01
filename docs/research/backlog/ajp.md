# (ajp) A DELETED FILE LEAVES ITS ALBUM MEMBERSHIP BEHIND, AND SQLITE REUSES THE ROWID

*Body of backlog entry `(ajp)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md);
the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-09-01 (P185), found while checking `(acg)`'s migration cost. **Split off rather than
folded in**, on `(aiy)`/`(ajo)`'s test: it is wrong today independent of any portability question.

## 1. 🔑 THE MECHANISM, THREE FACTS THAT ARE EACH FINE ALONE

`catalog.Catalog.forget_organized` drops the `files` row once no copy remains:

```python
            if not remaining:
                conn.execute("DELETE FROM files WHERE sha256 = ?", (sha256,))
```

1. **It does not touch `file_albums`**, so the membership rows survive their file.
2. **There is no foreign key.** The table is declared
   `CREATE TABLE IF NOT EXISTS file_albums (file_id INTEGER NOT NULL, album_id INTEGER NOT NULL,
   PRIMARY KEY (file_id, album_id));` - no `REFERENCES`, no `ON DELETE CASCADE`.
3. **The schema has zero `AUTOINCREMENT`** (`grep -c AUTOINCREMENT catalog.py` → `0`), so
   `files.id INTEGER PRIMARY KEY` is a plain rowid and **SQLite is free to reuse it** for the next
   inserted row.

**Together: an orphaned membership row can silently attach a DIFFERENT photograph to the deleted
one's album.** Not a missing album - a wrong one, which is the direction `(ack)` named as the
expensive one: *"A missing trip is visible to a user; a trip that absorbed another's days is not."*

## 2. IT IS REACHABLE

`forget_organized` is called from `undo.py`. Undoing an organize is an ordinary act, and it is the
one path that deletes `files` rows in normal use.

## 3. WHAT IS **NOT** ESTABLISHED

- **Whether it has happened to anyone.** No rowid reuse has been observed here; SQLite reuses the
  largest free rowid, so it needs a delete followed by an insert. **Not measured**, and the entry
  does not claim it has.
- **Whether other tables have the same shape.** Only `file_albums` was checked, because `(acg)` was
  the subject. `events`, `trips` and `file_copies` were not examined for orphan paths.

## 4. THE FIX SHAPE, NOT RULED

Deleting the membership beside the file is the obvious answer and is probably right. The
alternative - a foreign key with `ON DELETE CASCADE` - is a **schema migration on a published
product** and would need `PRAGMA foreign_keys` to be on, which was not checked.

⚠ **`(acg)` deliberately shipped without touching this**, because its fix needed no schema change
and this one may.

## RELATED

`(acg)` (shipped 2026-09-01 - membership now travels by sha256, which is unaffected by this),
`(ack)` (the wrong-owner direction), `(agv)` (a mark must not claim an outcome nobody observed).
