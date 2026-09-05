# (akf) THE LOCAL BROWSER LANE READS 26-28 MINUTES TODAY AND "5:38" IN THE RECORD, AND THE TWO ARE NOT THE SAME COMMAND.

*Body of entry `(akf)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(akf)** Filed 2026-09-05. **No work attached and nothing investigated**: this records a
  contradiction between two figures so the next reader does not cite either without its command.

  ## THE TWO FIGURES AND THE COMMAND BEHIND EACH

  | figure | command | source |
  |---|---|---|
  | **1653 s** (27:33), pytest `1649.04s`, `2 failed, 1009 passed, 3 skipped` | `make e2e` - serial, `--browser chromium --browser webkit`, the `e2e` target in `Makefile` | measured 2026-09-05, first run of the day, red on one test that was then fixed |
  | **1593 s** (26:33), pytest `1588.91s`, `1011 passed, 3 skipped` | `make e2e`, same target | measured 2026-09-05, second run, green |
  | **5:38** | not named in the subject line of `0da8f88`, *"the local lane runs in 5:38"* | the commit's own body and `PERFORMANCE.md`'s four-run table give **`-n auto` 338 s (5:35) / 343 s (5:41)** beside **serial `make e2e` 1587 s (26:21) / 1598 s (26:33)**, `nproc = 16` |
  | **5:15** | *"`make e2e -n auto`"* | `handoff-2026-09-04.md` §2; no run in the record reads 5:15 |

  Today's two serial figures sit inside the recorded serial band (1587-1653 s over four runs on
  the same machine), so the lane has not slowed. The 5:38 is the `-n auto` figure, and `make e2e`
  does not pass `-n auto`; it accepts it only through `E2E_EXTRA`.

  ## WHAT IS UNESTABLISHED

  Which record is wrong. Three candidates, none checked: the subject line of `0da8f88`, which
  names a figure without its command and so reads as the lane's own time; the handoff's **5:15**,
  which matches no measurement; or the reading that *"the local lane"* means the serial target
  at all. Nothing here says which, and this entry is not the place that decides it.

  ## WHY IT IS FILED

  Stage 3 of the run-gate fix (2026-09-05) reported the lane at 27:33 against an expectation of
  5:38 and could not say which was the anomaly. An unqualified duration in a commit subject is a
  claim the next person plans around; `(ajy)` already holds the other half of this - a timing
  figure whose hardware nobody could identify.
