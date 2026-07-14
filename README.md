# herdr-matter-wall

A [herdr](https://herdr.dev) plugin that opens the most-active subdirectories
of a project as a live wall of read-only AI status cards — one small AI agent
per subdirectory, each in its own full-screen tab, summarizing that item's
status into a full status brief.

Think of it as a glanceable wall of your active work areas: services in a
monorepo, packages in a workspace, projects in a portfolio, matters in a
practice — any set of subdirectories you want a standing status board for.

```
╭ billing-service ─────────────────────────╮
│ ● mid-refactor, migration in review       │
│   phase: refactor                         │
│ ◆ 2026-08-01 · 12d                        │
│ ⚠ none                                    │
│ ── Recent (last 5–10d) ── ──────────────  │
│ • 2026-07-09 merged migration PR          │
│ • 2026-07-07 code review with team        │
│ ── Awaiting ── ─────────────────────────  │
│ • QA sign-off on staging                  │
│ ▶ ship the migration                      │
╰────────────────────────────────────────────╯
 as of 14:32
```

Each item gets one card like this, full-screen in its own tab (switch tabs
with herdr's usual `prefix+1..9` / `prefix+n` bindings). Every card is drawn
by a small, pure bash renderer (`render-card.sh`) from a compact structured
block the agent emits — colored and border-severity-coded by deadline/risk
(red = overdue or high risk, amber = due soon or medium risk, green =
healthy), width-fit to the tab, `NO_COLOR`-aware. The agent itself is spawned
with a strict read-only tool allowlist — it can read files and `git log`,
and nothing else. It cannot write, edit, or run arbitrary commands.

## Requirements

- [herdr](https://herdr.dev) >= 0.7.0
- the [`claude`](https://claude.com/product/claude-code) CLI, logged in
- `jq`
- `bash` >= 3.2 — no bash-4 builtins are used, so the stock macOS
  `/bin/bash` works; GNU and BSD `find`/`date`/`stat` are both supported
- `timeout` (or `gtimeout`) is optional — without it, card agents are
  bounded by a built-in pure-bash watchdog instead
- a UTF-8 locale (the card renderer slices strings by character for
  truncation/padding, which assumes single-byte-safe UTF-8 handling)

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
bash matter-wall.sh --card billing-service         # render one card to stdout, standalone
```

`--card <slug>` is what each wall tab actually runs under the hood (`open`
spawns `bash matter-wall.sh --card <slug>` per tab): it `cd`s into the
item's subdirectory, runs the read-only card agent, then pipes its output
through `render-card.sh` to draw the box. It's also handy to run directly
against a single item without opening the whole wall.

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
| `--card <slug>` | flag | — | Render one card standalone: `cd` into the item, run the card agent, pipe through `render-card.sh` |
| `--close` | flag | — | Tear down the wall workspace |
| `--dry-run` | flag | — | Print the plan (or the refresh/close plan) without touching herdr |
| `$MATTER_WALL_HERDR` | env | `$HERDR_BIN_PATH` or `herdr` | Path to the herdr binary |
| `$MATTER_WALL_CLAUDE` | env | `claude` | Path to the claude binary |
| `$MATTER_WALL_PROMPT` | env | `<plugin dir>/card-prompt.md` | Override the card prompt template |
| `$MATTER_WALL_STATE_DIR` | env | `<target dir>/.matter-wall` | Where the refresh lockfile lives |
| `$MATTER_WALL_CARD_TIMEOUT` | env | `120` (seconds) | Timeout for the card agent invoked by `--card` |
| `$MATTER_WALL_FORCE_COLOR` | env | — | Force `render-card.sh` to emit color even when stdout isn't a TTY (set automatically when `--card` pipes into it) |
| `$NO_COLOR` | env | — | Standard no-color opt-out, honored by `render-card.sh` |

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
- **One matter per full-screen tab:** the first item runs in the workspace's
  own initial tab (renamed to the item's slug); every subsequent item gets a
  freshly created tab. No pane splitting/tiling — each card gets the full
  pane width, so `render-card.sh` fits it to `$COLUMNS` (capped at 100)
  instead of a cramped tiled-pane width.
- **Idempotent open:** opening the wall again closes any existing "Matter
  Wall" workspace first, so you don't accumulate stale boards.
- **Fail-visible:** unknown flags and missing required flag values exit `64`;
  a missing target directory or missing prompt template exits `66`; running
  outside herdr exits `1` with a clear message. Nothing fails silently.
- **Card rendering is a separate, pure step:** the card agent's prompt asks
  for a fenced `<<<CARD ... CARD>>>` block (`STATUS`/`PHASE`/`DEADLINE`/
  `RISK`/`RECENT`/`AWAITING`/`NEXT` — `RECENT` and `AWAITING` are list
  headers followed by `- ` bullet lines); `render-card.sh` parses that block
  and draws the box, word-wrapping long fields and bullets instead of
  truncating them, capped at 6 `RECENT` bullets and 3 `AWAITING` bullets. It
  never calls an LLM or herdr itself, always exits `0`, and falls back to a
  dim "(no summary)" card if the agent's output doesn't contain a well-formed
  block — a card is never allowed to error the whole wall out.

## Testing

```
python -m pytest tests/ -v
```

The suite stubs out `herdr` and `claude` as logging shell scripts under a
temp `PATH`, so it never talks to a real herdr server or spends any tokens.
`tests/test_render_card.py` exercises `render-card.sh` directly (no stubs
needed — it's pure bash reading stdin) for width-fitting, truncation,
day-count math, color/`NO_COLOR` behavior, and the no-block fallback.

## License

MIT — see [LICENSE](LICENSE).
