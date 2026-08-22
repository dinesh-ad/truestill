# (afl) THE PRODUCT HAS NO VERBOSITY CONTROL AT ALL - NO `--verbose`, NO `-q`, NO LEVELS.

*Body of backlog entry `(afl)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afl) FOUND WHILE FIXING `(afd)`, 2026-08-22.** ⚠ **Not a missing flag - a missing dimension.**
  It is the reason two other entries have nowhere to put what they must not print.

  ## MEASURED

  ```
  truestill --help          : no --verbose, no -v, no -vv, no --quiet, no -q, no --debug
  every subcommand          : the same
  ```

  Every line the product prints is printed unconditionally. There is one output level, and it is
  whatever each call site decided.

  ## WHY IT SURFACED, AND WHY IT IS NOT COSMETIC

  `(afd)` asked whether a failure list's raw `OSError` text should go behind `--verbose`.
  [clig.dev](https://clig.dev) puts developer-only detail exactly there. **The option did not
  exist to reject** - so the raw text had to be capped away instead of demoted, and the most
  specific evidence a user has when a copy fails is now elided rather than moved.

  `(aep)` has the same problem from the other side: it must stop a raw errno reaching a user, and
  the natural home for an errno is a verbose level nobody can ask for.

  ## PRIOR ART, WHICH IS UNUSUALLY SETTLED FOR A CLI QUESTION

  - **Unix convention**: `-v` / `-vv` to add detail, `-q` to remove it.
  - **[clig.dev](https://clig.dev)**: `-q, --quiet` - *"Display less output. This is particularly
    useful when displaying output for humans that you might want to hide when running in a
    script."* And `-d, --debug` for debugging output. ⚠ clig warns `-v` is ambiguous - *"can often
    mean either verbose or version"* - and suggests `-d` for verbose, which is a decision this
    entry has to make rather than inherit.
  - **[.NET](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet)**: five named levels -
    `quiet`, `minimal`, `normal`, `detailed`, `diagnostic` - with `-v` as the alias. A worked
    example of *levels* rather than a boolean, which is the shape a product with this much output
    probably needs.

  ## NOT DECIDED

  - **Boolean or levels.** `--verbose` alone is cheap; five levels is what a run producing 15,000
    lines actually calls for, and `(afm)` is about that volume.
  - **`-v` or `-d`.** clig's ambiguity warning versus the Unix habit. `truestill --version` exists,
    which is exactly the collision clig names.
  - **What each level contains.** ⚠ This is the real work, and it is a per-call-site decision
    across the whole CLI - not a flag definition. Doing it badly means a `--quiet` that hides
    something a user needed.
  - **Whether `--quiet` may hide a failure.** It must not hide a non-zero exit; whether it may
    hide the *reason* is a §9 question.
