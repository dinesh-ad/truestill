# (act) AN UNNAMED ROOT IS LABELLED WITH THE LITERAL STRING `Library`, WHICH COLLIDES WITH ITSELF.

*Body of backlog entry `(act)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(act) AN UNNAMED ROOT IS LABELLED WITH THE LITERAL STRING `Library`, WHICH COLLIDES WITH
  ITSELF.** Recorded 2026-08-10, split out of `(acr)` deliberately rather than folded in: `(acr)`
  is a correctness fix at the moment of naming, and this is a **behaviour change at registration**
  that alters what gets written into a marker on a user's disk. Mixing them would put a change of
  behaviour inside a fix.
  - ⚠ **RE-COUNTED 2026-08-22: FIVE SITES, NOT THREE**, and the line numbers below have all moved
    - `service/drives.py:364`, `:382`, `:383`, `service/organize.py:1126`, `cli.py:2795`. The
    registration work since (`(afc)`, `(afn)`) added paths without changing this default, which is
    the entry's own point arriving twice: a literal repeated at each site grows a site every time
    someone adds one. **Cited by symbol from here on**; the original count is kept below because a
    figure that grew is evidence and a figure quietly corrected is not.
  - Three of the four registration sites mint `label=path.name or "Library"`
    (`service/drives.py:382`, `service/organize.py:1126`, `cli.py:2795`).
    ⚠ **THOSE THREE READ `:381`, `:847` AND `:2033` UNTIL 2026-08-27, AND THE MIDDLE ONE WAS
    279 LINES OUT.** The bullet above says *"cited by symbol from here on"* and the numbers six
    lines below it were then repaired twice by OFFSET - `cli.py` went 2017 -> 2025 -> 2033 in one
    day while the real site was 2730. `cli-app-parity.md`'s ruling covers exactly this: *"an
    offset is a guess about a diff, and a citation repaired from a guess is a citation nobody has
    read"*. Re-resolved by grepping the literal. `Path("/").name` is `""`,
    so **organizing to a filesystem root** - or any path whose final component is empty - produces
    the literal label `Library`. Two of them are indistinguishable by name, and unlike a folder
    called `Backup` this one was never a name the user chose.
  - **`(acr)` makes it survivable, not fixed.** Two `Library` drives are now told apart by their
    recorded paths wherever they are named together, so this is no longer a wrong pointer. It is
    still a placeholder presented as a name.
  - **Not urgent, and small.** The fallback fires only for a root-like path, which no measurement
    has yet seen in a real catalog. Worth a decision - a better fallback, or refusing to mint a
    label at all and asking - not a rush.
