# Path-component safety for user-supplied names - recon + design

Status: **Decided and shipped (2026-07-28).** Step 2b-san of the layout correction.

Event names became directories when the year-first layout adopted
`2014-08-20 - Goa Trip`. A name a user types is now a path component, which moves it from a
display string to something a filesystem has to accept on Linux, macOS **and** Windows. This
records what actually constrains such a component, what truestill already handled, and the four
gaps that were closed.

---

## 1. What a path component must survive

| Constraint | Source of truth | Already handled? |
|---|---|---|
| Illegal characters `< > : " / \| ? * \` and control chars | Windows naming rules; `/` also matters on POSIX | **Yes** - `_VALUE_ILLEGAL` |
| Reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) | Windows; reserved **case-insensitively and with any extension** (`aux.jpg` is still `AUX`) | **Yes** - `_is_reserved` splits the stem and casefolds |
| Trailing dots and spaces | Windows silently strips them, so `Trip.` and `Trip` become the same directory | **Yes** - `_sanitize_value` trims |
| **Unicode normalization** | macOS HFS+/APFS historically store NFD; Linux stores bytes verbatim | **No - gap 1** |
| **Component byte length** | ext4/APFS/NTFS cap a component at **255 bytes**, not characters | **No - gap 2** |
| **Two events colliding on one folder name** | truestill's own naming, not the filesystem's | **No - gap 3** |

## 2. The gaps, and why each matters

**Gap 1 - normalization.** `Café` can be one of two byte sequences: NFC (`é` as one code point)
or NFD (`e` + combining accent). They render identically and compare unequal. A name typed on a
Mac and a name typed on Linux could therefore produce two directories that look the same in a
file manager, and a re-run could fail to recognise its own previous output. **NFC is the
correct target**: it is what the W3C recommends for interchange, what Linux tooling assumes, and
what APFS accepts and preserves. Normalizing on the way in makes the stored form deterministic
regardless of where the name was typed.

**Gap 2 - bytes, not characters.** The existing cap was 60 *characters*. For ASCII that is well
inside the limit, but every filesystem in play caps a component at **255 bytes**, and a
character can be up to 4 bytes in UTF-8 - so 60 emoji is 240 bytes and 64 would overflow a
naive char-based limit set at 255. Truncation also has to land on a **character boundary**:
slicing UTF-8 bytes blindly produces an invalid sequence, which surfaces as a mangled name or an
OS error rather than a clean shortening.

**Gap 3 - two events, one folder.** Two events on the same date whose names sanitize to the same
string ("Goa Trip" and "Goa/Trip", or "Goa Trip" and "goa trip" on a case-insensitive
filesystem) render one folder name. Files from two distinct events would merge silently. This
is not a filesystem constraint - it is truestill's own, created by making names human-readable,
and it has to be **detected and disambiguated before anything is written**, which means at
preview time where the user can still see it.

## 3. Rejected alternatives

- **Rejecting unsafe names instead of repairing them.** Wrong shape for this product: the name
  is often already recorded against an event, and failing a whole run over a colon in a trip
  name would be hostile. Repair and *report* matches the never-silent rule already in force.
- **NFD instead of NFC.** Would match old HFS+ behaviour and nothing else; modern APFS does not
  require it, and Linux would then hold decomposed names that most tooling renders but few
  normalize back.
- **Hashing a colliding name.** Deterministic and unreadable - it destroys the readability the
  whole change exists to deliver. A numeric suffix keeps the name and admits the collision.
- **Capping at 255 characters.** The limit is bytes; this would pass tests on ASCII and fail on
  a user's first non-Latin trip name.

## 4. Complexity

All per-name work is linear in the length of the name, which is bounded by the cap - so per
file it is effectively constant, and the pass stays **O(n)** in library size.

| Operation | Cost |
|---|---|
| Reserved-name check | **O(1)** - one `frozenset` lookup on the casefolded stem |
| Illegal-character replace + trim | **O(k)** in name length |
| NFC normalization | **O(k)** |
| Byte-boundary truncation | **O(k)** |
| Collision detection + disambiguation | **O(m)** across *m* events, one dict pass - not O(m²) |

Nothing here is worse than linear on library size, and none of it touches per-file I/O.
