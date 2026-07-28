# Decommissioning the category-first layout - rationale

Status: **Done (2026-07-28).** Step 2f, the close of the layout-correction arc.

---

## 1. Bridge, then burn

The year-first correction was built as a *bridge*: a pin that wrote down an existing library's
shape, a legacy scheme that rendered it, load-time leniency so a stored `{category}` template
kept parsing, and a Settings framing that explained the old layout to whoever was still on it.
All of that existed to carry real libraries across, and all of it earned its place while there
were libraries on the far bank.

Both real drives are now year-first, verified 2,269/0/0 each, and there are **zero external
users** - the product is pre-launch. So the compat machinery protects nobody, and every branch
of it is a second way for the code to behave that nothing exercises. A bridge kept after the
crossing is not caution; it is a path someone can still walk off.

## 2. The undo question, settled before anything was deleted

Both drives carried armed undo records pointing **back** to category-first.
`undo_migration` was checked rather than assumed: it touches no layout, scheme, template or
render code at all - it is pure path restoration from journal rows. So it would have survived
the decommission *mechanically*.

It was retired anyway, on Dinesh's explicit confirm (`I retire both records`), because it would
have survived into a state the product could no longer describe:

- undo restores a category-first tree but does **not** change the stored layout, which stays
  year-first, so the next organize splits the library silently;
- after decommission there is no supported way to set a matching layout - the constant is gone
  and `{category}` is rejected at the timeline door - so the only exit is migrating forward
  again, which undoes the undo.

**Retired deliberately and logged, not silently dropped:** 2,269 journal rows and one run row
for *The Memory Cabinet*, and the same for *Output*. `migrate-layout --undo` on either drive now
answers "no reversible migration exists for this drive" - an honest sentence, not a trace.

Reversibility remains a feature: every future migration arms its own record. What was retired
was two specific records pointing at a layout that no longer exists.

## 3. What the removal exposed

Two real defects, both caught by tests rather than review, and both worth recording because they
are the argument for doing this kind of removal *with* a suite rather than by inspection.

**The pin lost its trigger.** Deleting the legacy guard took the `has_placed_files()` check with
it, so the pin would have fired on a brand-new, never-organized library - defeating the narrow
trigger the whole mechanism was designed around.

**`effective_layout_string` was coupled to the default's shape.** Making it return
`DEFAULT_TEMPLATE_STRING` when nothing is stored looked equivalent and was not: the default's
evented and un-evented timelines *differ*, and a single string cannot carry that, so events
silently flattened into the `Everyday` bucket. It now returns what is stored and nothing else,
letting `resolve_scheme` fall back to the whole `DEFAULT_SCHEME`. This is the third time the
same lesson has bitten in this arc: **one string cannot express two shapes.**

## 4. Rejected alternative

**Keep the compat path "just in case".** It reads as prudent and is the opposite: an untested
second behaviour, a `{category}` acceptance the timeline door otherwise forbids, and a Settings
string using a word ("legacy") that no user should ever see because no user has that layout. The
right time to delete a bridge is when the last real library has crossed and been verified on the
other side - which is exactly where this stood.
