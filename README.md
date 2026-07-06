# herdr-matter-wall

A [herdr](https://herdr.dev) plugin that tiles the most-active subdirectories
of a project as a live wall of read-only AI status cards — one small AI agent
per subdirectory, each summarizing that item's status into a compact card.

Think of it as a glanceable wall of your active work areas: services in a
monorepo, packages in a workspace, projects in a portfolio, matters in a
practice — any set of subdirectories you want a standing status board for.

```
┌─ billing-service          ┌─ auth-service             ┌─ notifications
│ Status: mid-refactor      │ Status: stable            │ Status: blocked on…
│ Next milestone: …         │ Next milestone: none found│ Next milestone: …
│ Top risk: …                │ Top risk: none found      │ Top risk: …
│ Last activity: …           │ Last activity: …          │ Last activity: …
│ Needs attention: …         │ Needs attention: nothing  │ Needs attention: …
└─                           └─                          └─
```

Each card agent is spawned with a strict read-only tool allowlist — it can
read files and `git log`, and nothing else. It cannot write, edit, or run
arbitrary commands.

## Requirements

- [herdr](https://herdr.dev) >= 0.7.0
- the [`claude`](https://claude.com/product/claude-code) CLI, logged in
- `jq`
- `bash`

## Install

```
herdr plugin install Javamomma/herdr-matter-wall
```

## Local development

Clone this repo, then link it as a local plugin instead of installing from
the registry:

```
git clone https://github.com/Javamomma/herdr-matter-wall
herdr plugin link ./herdr-matter-wall
```

`herdr plugin link` skips the build step — this plugin is pure bash and has
no build to run.

## Usage

Once installed or linked, invoke the plugin's actions from herdr:

```
herdr plugin action invoke javamomma.matter-wall.open
herdr plugin action invoke javamomma.matter-wall.dry-run
herdr plugin action invoke javamomma.matter-wall.close
```

Or run the script directly for local testing / scripting:

```
bash matter-wall.sh --dry-run              # preview the plan, no herdr needed
bash matter-wall.sh                        # open the wall (top-5 by recency)
bash matter-wall.sh billing-service auth-service   # open specific items
bash matter-wall.sh --close                # tear the wall down
bash matter-wall.sh --refresh billing-service      # re-run one card in place
```

### How it picks subdirectories

A subdirectory counts as a candidate if it contains a `context.md` or a
`README.md` (configurable — see below). Candidates are ranked by recency:
`max(last git-commit time for that path, newest file mtime under it)`. By
default the top 5 are shown; pass explicit names to open exactly those
instead, in the order given.

### Working-directory resolution

As a herdr plugin action, this script's own working directory is the
**plugin's** directory, not your project. It resolves the *target* project
directory to scan, in this order:

1. `--dir <path>` flag
2. `$MATTER_WALL_DIR` environment variable
3. If running as a plugin action (herdr sets `HERDR_PLUGIN_CONTEXT_JSON` or
   `HERDR_WORKSPACE_ID`), the active workspace's cwd, queried over the herdr
   socket (`herdr workspace get` / `pane get`, cwd parsed with `jq`) — best
   effort; falls through if the query fails
4. `$PWD`

### Environment variables and flags

| Name | Type | Default | Purpose |
|---|---|---|---|
| `--dir <path>` | flag | — | Target project directory (highest priority) |
| `$MATTER_WALL_DIR` | env | — | Target project directory (used if `--dir` absent) |
| `$MATTER_WALL_MARKER` | env | `context.md README.md` | Space-separated list of marker filenames; a subdirectory qualifies if it has ANY of them |
| `--limit <n>` | flag | `5` | Max cards to show when no explicit names are given |
| `--model <name>` | flag | `claude-haiku-4-5-20251001` | Model used for each card agent |
| `--refresh <slug>` | flag | — | Re-run a single card in place (serialized — refuses if another refresh is running) |
| `--close` | flag | — | Tear down the wall workspace |
| `--dry-run` | flag | — | Print the plan (or the refresh/close plan) without touching herdr |
| `$MATTER_WALL_HERDR` | env | `$HERDR_BIN_PATH` or `herdr` | Path to the herdr binary |
| `$MATTER_WALL_CLAUDE` | env | `claude` | Path to the claude binary |
| `$MATTER_WALL_PROMPT` | env | `<plugin dir>/card-prompt.md` | Override the card prompt template |
| `$MATTER_WALL_STATE_DIR` | env | `<target dir>/.matter-wall` | Where the refresh lockfile lives |

The script also accepts either `$HERDR_ENV` or `$HERDR_SOCKET_PATH` as proof
it's running inside a herdr session (a plugin action sets the socket path but
not necessarily `HERDR_ENV`).

## Keybinding

Keybindings are not part of the plugin manifest — add one yourself in
`~/.config/herdr/config.toml`:

```toml
[[keys.command]]
key = "ctrl+shift+m"
type = "plugin_action"
command = "javamomma.matter-wall.open"
```

## Design notes

- **Serialized refresh:** `--refresh <slug>` takes a lockfile
  (`<target dir>/.matter-wall/refresh.lock`) so two refreshes never race each
  other. `--close` clears a stale lock.
- **Tiling:** panes are arranged in a roughly square grid, `cols =
  ceil(sqrt(n))`, filled first across a row (splitting right) then down
  (splitting down, round-robin across columns) as more items are added.
- **Idempotent open:** opening the wall again closes any existing "Matter
  Wall" workspace first, so you don't accumulate stale boards.
- **Fail-visible:** unknown flags and missing required flag values exit `64`;
  a missing target directory or missing prompt template exits `66`; running
  outside herdr exits `1` with a clear message. Nothing fails silently.

## Testing

```
python -m pytest tests/ -v
```

The suite stubs out `herdr` and `claude` as logging shell scripts under a
temp `PATH`, so it never talks to a real herdr server or spends any tokens.

## License

MIT — see [LICENSE](LICENSE).
