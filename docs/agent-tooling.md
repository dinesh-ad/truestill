# Agent tooling - what Claude Code has installed here, and what each tool may do

Recorded 2026-09-02 (P192). **A living document**: it lists the things that live OUTSIDE this
repository and would be missing from a fresh clone, and the rule that governs each.

## 1. The fence gap - a fact with a consequence, stated first

`IMPLEMENTATION_STANDARDS.md` §5's fence row records that the corpus fence has two enforcement
layers, permission deny rules and a sandbox read-deny, and that both cover Claude's file tools and
bash while **MCP and hooks are covered by neither**. So **an MCP tool is outside the fence**: nothing
stops it carrying a fenced path or a file's content to a third party except the agent's choice.

**The 21st server's tool surface was measured** (`tools/list`, 2026-09-02, 35 tools): **none of
them reads a file**. Every tool takes a query string, an id, or an optional `context` object. What
reaches 21st.dev is exactly what the agent puts into `query`, `prompt`, `instruction` or `context`
(a `.21st/design.json`-shaped description of the project's stack and tokens). That is the usable
distinction:

| group | tools | what leaves the machine | cost |
|---|---|---|---|
| catalog and account reads | `search`, `search_picker`, `get_inspiration`, `search_logo`, `get_theme`, `get_usage`, `get_profile`, every `list_*` | the query text, plus `context` only if sent | free, unmetered |
| component code | `get_component` | an id | metered: 2 per day on the free tier |
| generation | `generate`, `iterate_generation`, `get_generation`, `get_take` | the prompt, the instruction, `context` if sent | credits |
| account writes | `bookmark`, `*_list`, `edit_*`, `delete_*`, `submit_*`, `upload_profile_media` | ids, listing text, an uploaded image | free |

**The rule**: a call that carries project facts is a decision each time, never a default. No
fenced path, no file content, no token, no catalog path in a query or a `context`. The site's
*"review the UI we have"* and *"build screens"* copy describes agent-side work on the returned
`copyPrompt`; the server has no tool that does it.

## 2. The 21st MCP - local scope, and a key that was exposed once

- **Where**: `~/.claude.json`, under this project's entry, scope **local**. Verify with
  `claude mcp get 21st`; remove with `claude mcp remove 21st -s local`. ⚠ **Not project scope**:
  that writes `.mcp.json`, which is not gitignored, with the key inside it.
- ⚠ **The key was exposed once.** On 2026-09-02 it was pasted into a chat, so it sat in a session
  transcript and a plan file on disk before it was installed. **The maintainer rotates it.** Until
  the rotated key is written back (`claude mcp remove 21st -s local`, then `claude mcp add` with
  the new header), the value in `~/.claude.json` is the exposed one. Do not assume the key there
  has always been private.
- **`DECISIONS.md` D12 applies to what is pulled from the catalog, not to the tool.** The catalog
  carries Aceternity and Magic UI; a component that imports Motion is refused on arrival. Registry
  components also import `lucide-react`, which is refused by ruling - replace the glyphs the way
  `components/ui/icons.tsx` does.

## 3. The `ui-ux-pro-max` plugin - user scope, query mode only

- **Where**: `~/.claude/plugins/cache/ui-ux-pro-max-skill/`, installed as a plugin from the
  `nextlevelbuilder/ui-ux-pro-max-skill` marketplace at user scope, beside the already-enabled
  `frontend-design` plugin. 23 MB on disk, **nothing in this repository**. Installed at 2.13.0,
  which is what its marketplace manifest declares while the repository tags v2.15.0; `claude plugin
  update ui-ux-pro-max@ui-ux-pro-max-skill` moves it.
- ⚠ **Why not `uipro init --ai claude`**: it writes 2.6 MB of CSV and JSON into `.claude/skills/`,
  and only `.claude/settings.local.json` is gitignored there. The data would be tracked.
- **How it is used here**: search mode, one domain or one stack per query -
  `--domain ux`, `--domain typography`, `--stack react`, `--stack shadcn`. Its output is a
  recommendation; `tokens.css`, `brand.md` and D12 win. **Never `--design-system --persist`**: it
  writes `design-system/<slug>/MASTER.md` into the project root, a tracked document restating a
  palette that `organize-grid-design.md` records as *inherited, not chosen*.

## 4. `DESIGN.md` - read, not adopted

`voltagent/awesome-design-md` collects 73 `DESIGN.md` files in the Google Stitch format: visual
theme, palette and roles, typography, component stylings, layout, depth, do's and don'ts,
responsive behaviour, an agent prompt guide. Truestill already states each of those in
`tokens.css`, `brand.md` and `organize-grid-design.md`, so a root `DESIGN.md` would be a third
copy of the palette. **Not adopted.** If one is ever wanted it is generated from `tokens.css`,
never hand-written; that is the maintainer's ruling to make.

## 5. What a fresh clone does not have

| item | lives in | in the repo |
|---|---|---|
| the `github` and `21st` MCP servers | `~/.claude.json` | no |
| the `frontend-design` and `ui-ux-pro-max` plugins | `~/.claude/plugins/` | no |
| the two fence layers | `~/.claude/settings.json` | no - `IMPLEMENTATION_STANDARDS.md` §5 says so |
| `TMPDIR=/data/tmp/truestill` | `.claude/settings.local.json` | no, gitignored |

A fresh clone has this document and the conventions alone.
