# (aca) The app and the CLI disagree about when an organize run needs confirming.

*Body of backlog entry `(aca)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aca) The app and the CLI disagree about when an organize run needs confirming.** Recorded
  2026-08-08 while making the app's confirm word mode-aware.
  - **The divergence.** The app gates all three modes behind a typed word. The CLI's
    `_confirm_in_place` returns `True` immediately unless `--in-place`, so **copy and move ask for
    nothing at all**. One operation, two ceremonies, decided by which surface the user happened to
    open - the same shape as the clean-empty trash defect, where whether a folder was recoverable
    depended on the surface rather than on the operation.
  - **The word itself no longer diverges**: in-place asks for `move` on both, and copy asks for
    `copy` in the app, which the CLI never asks for at all. What is left is the *whether*.
  - **RECOMMENDATION, recorded although we are not acting on it: close it by RELAXING THE APP,
    not by tightening the CLI.** The typed word is a ceremony for an irreversible act, and it
    should cost something exactly where something is at stake. In-place moves a user's files with
    no copy left behind, which is why it earned a word on both surfaces. Copy writes new files and
    changes nothing; move is guarded by verify-then-delete and by `undo-organize`. Requiring a
    typed word for copy spends the user's attention on the safest thing they can do, and a
    ceremony that fires on everything stops meaning anything on the one case that matters - which
    is the same reason the irreversibility line was reframed rather than shown on copy.
  - **Tightening the CLI instead would be the wrong direction twice**: it would add a prompt to a
    non-interactive surface people script, and it would spread the ceremony rather than aim it.
  - **Not acted on** because it removes a guard, and removing a guard on the strength of an
    argument rather than evidence is how the guard was justified in the first place. It wants the
    maintainer's decision, not an engineer's tidy-up.
