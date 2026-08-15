# (abc) `check_product_name.SUBCOMMANDS` should be derived, not transcribed.

*Body of backlog entry `(abc)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abc) `check_product_name.SUBCOMMANDS` should be derived, not transcribed.** Recorded
  2026-08-04, when Analyze 3b tripped over it: the list had never gained `analyze` or
  `repoint-sources`, so writing either invocation in prose was flagged as the product name in
  lowercase. Both entries were added; the class was not fixed.
  - **Why it is a class and not a typo.** The guard's own docstring says the list *"mirrors the
    parser rather than guessing"*. It does not mirror anything - it is a copy, and it has now
    drifted twice. Same shape as the `ALL_RULES` tuple in `test_layout_scheme.py`, which stopped
    covering the one rule whose routing had changed, and was fixed by deriving it from the enum.
  - **Why it was not done here.** The authority is `cli.py`'s dispatch table, so deriving it
    means a repo script importing `truestill_cli` - a direction nothing in `scripts/` currently
    takes, and one that changes what `make check` needs installed to run. That is its own
    decision, not a footnote to a streaming commit.
