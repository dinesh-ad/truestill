# (ahg) `cli-app-parity.md` IS KEYED BY CLI SUBCOMMAND, SO AN APP-ONLY CAPABILITY HAS NO ROW.

*Body of backlog entry `(ahg)`, under **Internal / tooling**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahg) `cli-app-parity.md` IS KEYED BY CLI SUBCOMMAND, SO AN APP-ONLY CAPABILITY HAS NO ROW.**
  Filed 2026-08-25 (P68), from `(ahd)`'s Q376 finding.

  ## THE DEFECT

  The table is **one row per CLI subcommand**. A capability with no subcommand therefore gets no
  row - so the document whose stated purpose is *"if the UI arc starts tomorrow, what is actually
  missing?"* **cannot see an app-only capability at all.** Structural, not an oversight.

  Measured: `bake` had **zero** mentions under any name until `(ahd)` gave it a subcommand and
  therefore a row. ⚠ **`backup` was the second instance and is gone as of 2026-08-25** - `(ahf)`
  stage 2 gave it a subcommand, so it is a CLI row now rather than an invisible app-only
  capability. **One instance left: `trip apply`**, which still has no row and no deferral.
  ⚠ **That is the class being closed one capability at a time, which is not the same as fixing
  it**: each one only became visible because someone went looking. The re-key below is what makes
  the next one visible without anybody looking.

  ## THE PROPOSED SHAPE

  **One row per CAPABILITY, one column per SURFACE**, each cell `supported` / `partial` / `absent`
  with the implementing `file:line`. An app-only feature then **must** appear with an empty CLI
  cell - the gap becomes visible by construction rather than by someone thinking to look - and the
  reverse gap (`reclaim`, CLI-only by recorded deferral) is caught by the same table instead of
  needing the separate list the document carries today.

  ## PRIOR ART, and each answers a different half

  * **Nextcloud `occ`** claims parity in prose in **both** directions - *"these commands replicate
    the functionality in the Nextcloud Web GUI, plus two new features"* - and there are open
    requests for the reverse. The failure mode of writing parity down without **keying** it.
  * **Git** separates plumbing from porcelain and documents which contract each command honours.
    The capability is defined once; each surface is a stated contract against it.
  * **Kubernetes Gateway API** defines behaviour in a spec with **feature tiers** and validates
    implementations against it rather than trusting them - the answer to *"who checks the table"*.
  * **Docker CLI** and **kubectl** are thin clients over a documented API, so the API **is** the
    registry and parity is auditable against the spec rather than against prose.

  ## WHAT A GUARD CAN AND CANNOT PIN

  ⚠ **Understating this is better than implying a guard that does not exist.**
  `test_the_cli_app_parity_table_is_complete.py` today derives subcommand names from the **AST of
  `cli.py`** and asserts each appears in the document. It says so itself: *"This checks
  completeness, not correctness."*

  **CAN be pinned, and this is the re-key's real content** - both surface inventories, each from
  the source that declares it:

  | pinned from | what it catches |
  |---|---|
  | `add_parser(...)` names in `cli.py` (AST) - **today's check** | a new subcommand missing from the table |
  | `operation="..."` strings in `server.py` - **new** | **an app capability missing from the table**, which is the whole defect |

  **CANNOT be pinned**, and the reason is that nothing declares it: there is **no registry of
  capabilities** in this codebase. A capability is a human-chosen label spanning one CLI entry and
  one route, and no source of truth emits that grouping. So:

  * the **row label** stays a human read;
  * every **cell verdict** (`supported`/`partial`/`absent`) stays a human read - the same limit the
    existing test already declares about the route column;
  * what becomes mechanical is that **no declared surface entry is absent from the document**, in
    **both** directions.

  That is a real strengthening and it is smaller than "the table is now verified". Both halves
  stated, so nobody reads the second as the first.

  ## WHAT RE-KEYING WOULD BREAK - censused before proposing

  | reader | effect |
  |---|---|
  | `test_the_cli_app_parity_table_is_complete.py` | **survives if each CLI cell still names the subcommand**, because it text-matches AST-derived names against the document. The re-key must keep the name in the cell |
  | `test_live_documents_cite_code_that_exists.py:LIVING` | the document is in the LIVING set, so every `file:line` in the new cells must resolve. More cells means more citations to keep true |
  | `CLAUDE.md`'s map row | states **"5 subcommands with no route, plus `catalog --move`, and six partial"**. ⚠ **"six partial" is already wrong - there are FIVE partial rows today**, corrected in P68 while checking this. A capability re-key changes the shape of that claim entirely and it must be rewritten, not adjusted |
  | `agq.md:33` | already notes the completeness test *"will not see this by itself"* - the same limit, recorded once already |
  | `PROJECT_STATUS.md:225`, `ahd.md`, `SHIPPED.md`, `user-evidence-log.md:66`, `ENGINEERING_STANDARD.md:776` and `:2006` | prose references to the document as a whole; none cites a row, so none breaks |

  **Nothing reads the table's row keys programmatically except that one test**, which is the
  finding that makes the re-key affordable.
