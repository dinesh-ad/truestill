# (akc) NO BINDING RULE GOVERNS REACT, TYPESCRIPT, TAILWIND OR THE GENERATED CONTRACT.

*Body of backlog entry `(akc)`, under **Rulings**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(akc)** Ruled 2026-09-04 (P211). **A gap is recorded; nothing is to be built.**

  ## THE CHECK THAT FOUND IT

  ```sh
  grep -ciE "react|typescript|tailwind" docs/IMPLEMENTATION_STANDARDS.md docs/ENGINEERING_STANDARD.md
  grep -ciE "openapi|api\.d\.ts"        docs/IMPLEMENTATION_STANDARDS.md docs/ENGINEERING_STANDARD.md
  ```

  On 2026-09-04: **2 and 0** for the frontend stack, **1 and 0** for the generated contract. And
  `CLAUDE.md`'s own map routes the question to a document it labels as not binding:

  > | What are the rules for TypeScript, React, Tailwind and Rust? |
  > `docs/frontend-and-shell-standard-research.md` - a **record**, not the canon |

  So the phase that is entirely React, TypeScript and a derived contract is governed by nothing in
  the canon, while the finished engine phase is governed by 86 members and 48 rows.

  ## THE RULING: DO NOT FILL IT SPECULATIVELY

  **Every §4 member earned its place by naming a real failure**, and the section's own retirement
  bar is the same test read backwards - *"name what it was written for, and show that the failure
  can no longer happen"*. Writing frontend rules now would put text in the canon that has never
  caught anything, which is the one thing the section has never done in 86 members.

  ⚠ **And the asymmetry is not evidence of neglect - it is evidence of how the canon is built.**
  The engine has 86 members *because* the engine was built; the count is a record of failures
  survived, not of attention paid. A frontend canon of comparable size before the first screen
  ships would be a canon of guesses.

  **So: the gap is named so a cold start is not misled into thinking silence means "no rules
  apply", and the first real frontend failure writes the first rule.** `docs/react-migration-plan.md`
  carries the working decisions in the meantime and says so.

  ## WHAT WOULD CHANGE THIS

  A frontend defect that reaches a user, or a second one of the same shape. At that point the rule
  is written the way every other member was: from the failure, naming it.
