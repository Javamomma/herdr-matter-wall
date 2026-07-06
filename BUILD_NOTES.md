# Build notes — herdr-matter-wall

Extraction/genericization of a private internal tool into a standalone,
public, MIT-licensed herdr plugin. This file records what changed and why,
for anyone auditing the genericization. It deliberately avoids naming the
source organization or reproducing any of its internal file/tool names —
only the generic shape of what was removed or changed is described below.

## What was dropped (private/domain-specific)

- **A priority-tier filter.** The private version could filter candidates by
  reading a house-format "active items" register with priority-tier headings
  and per-item ID markers. That register format and the whole "tier" concept
  is specific to the source tool's own internal convention, isn't part of
  the public spec, and doesn't generalize cleanly. Removed entirely — the
  public plugin only supports explicit-slugs-or-ranked-top-N.
- **Domain-specific `--refresh --with <register>` behavior.** The private
  version's refresh mode could invoke other internal slash commands to
  regenerate an item's underlying tracking documents before re-carding it.
  Those commands don't exist in a generic context. Genericized
  `--refresh <slug>` to simply mean "re-run this one card's read-only agent
  in place" — same lockfile-serialization behavior, no domain assumption.
- **A live/token-spending smoke test** wired to a specific herdr JSON shape
  was not brought over — the task's file list only asked for the pytest
  suite (`conftest.py`/`_util.py`/`test_matter_wall.py`), and a live smoke
  test felt like scope creep for a v0.1.0 public drop. Easy to add later.
- All organization-specific strings, internal file/path conventions, and
  in-house vocabulary (a risk register, a communication-style mnemonic, an
  uncertainty-flagging convention, etc.) were removed. The card prompt's
  "don't fabricate" guidance was rewritten in plain, generic language.

## What was added (new, not in the private version)

The private tool always ran with cwd = repo root (it lived inside the host
repo and scanned a hardcoded subdirectory next to it). A herdr **plugin
action** runs with cwd = the plugin's own directory, not the user's project —
so a real piece of new logic was needed:

- **`resolve_target_dir()`**: `--dir` flag > `$MATTER_WALL_DIR` env > (if
  `HERDR_PLUGIN_CONTEXT_JSON`/`HERDR_WORKSPACE_ID` present) query the herdr
  socket for the active workspace's cwd > `$PWD`. The socket query
  (`herdr workspace get` → `pane get`, parsed with `jq`) is best-effort: I
  don't have herdr's actual JSON schema to test against, so it tries a couple
  of plausible field paths (`.result.workspace.cwd`, `.result.cwd`,
  `.result.pane.cwd`) and falls through cleanly to `$PWD` if none resolve.
  **Flag for a maintainer with a real herdr instance**: verify the actual
  `workspace get`/`pane get` response shape and tighten the jq paths.
- **Configurable marker (`$MATTER_WALL_MARKER`)**: subdirectories now qualify
  on `context.md` OR `README.md` by default (space-separated list,
  overridable), instead of hardcoding a single marker filename.
- **`$MATTER_WALL_PROMPT`**: lets a user point at a custom card-prompt
  template. This also *replaced* the private version's cwd-relative template
  lookup (relative to wherever the script happened to be run from) with a
  script-relative lookup (`$(dirname "${BASH_SOURCE[0]}")/card-prompt.md`) —
  correct for a plugin, since `card-prompt.md` ships inside the plugin
  directory, not the user's project, and must be found regardless of what
  `--dir`/cwd resolve to.
- **Explicit `cd` into the subdirectory before spawning each card agent.**
  The private version relied on the pane's ambient cwd already being the
  repo root (true in that setup, not guaranteed for a herdr-spawned pane in
  general). Each card agent's `pane run` command now does
  `cd <absolute-subdir-path> && claude -p ...` so it's correct regardless of
  the pane's default cwd.
- **`HERDR_SOCKET_PATH` as an alternate herdr-session proof** alongside
  `HERDR_ENV` (a plugin action sets the socket path but not necessarily the
  env flag).
- **Value-flag hardening**: every flag that consumes a value (`--dir`,
  `--limit`, `--model`, `--refresh`, `--render-prompt`, `--grid-dims`) now
  checks `$# -ge 2` before reading `$2`, exiting `64` with a clear message
  instead of a `set -u` unbound-variable crash if passed as the last token.
- **`[[ -d "$TARGET_DIR" ]]` guard** after resolution, exiting `66` with a
  clear message ("target directory not found: ...") rather than silently
  scanning nothing.
- New tests covering all of the above (dir-resolution priority, missing
  target dir, marker configurability, the `HERDR_SOCKET_PATH` OR-condition,
  missing-value-flag hardening) — none of this existed in the private test
  suite since none of it existed in the private script.

## Naming decisions

- Kept "matters" as the vocabulary in `PLAN model=... matters=...` dry-run
  output and the "Matter Wall" workspace label, even though the plugin is
  domain-agnostic. This is deliberate product branding (the plugin is named
  "matter-wall"; "matter" here means "a thing worth tracking," same register
  as a kanban "card" or "item"), not a leftover from any specific domain —
  confirmed against the verification grep's own carve-out ("except possibly
  the word 'matter' which is fine").
- `--refresh` and `--grid-dims`/`--rank-only`/`--render-prompt` are kept as
  script-level debug/utility flags but are **not** wired into
  `herdr-plugin.toml` actions, since the spec called for exactly three
  actions (`open`, `close`, `dry-run`). They remain available via direct
  `bash matter-wall.sh --refresh <slug>` invocation and are documented in
  the README's flag table.

## Verification performed

- `python -m pytest tests/ -v` — 31 passed.
- `bash -n matter-wall.sh` — clean.
- `bash matter-wall.sh --dry-run --dir <tmp dir with 2 fake subdirs>` —
  printed a PLAN with no herdr installed/running, exit 0.
- Repo-wide case-insensitive scan for organization names, internal matter
  codes, and internal tool/file conventions — zero matches. (One round found
  two false positives: a four-letter substring of a Python builtin used for
  indexed loops, appearing coincidentally inside two test loops; reworded
  those two loops to `zip(range(n), [...])` to make the scan unambiguous.)

## Open items / concerns for a future maintainer

1. The `query_workspace_cwd()` socket-query paths are my best guess at
   herdr's `workspace get`/`pane get` JSON shape, inferred from the existing
   `wall_workspace_id`/`pane_id_from` helpers in the source script (which do
   use `.result.pane.pane_id`, `.result.workspaces[]`, etc.). It has
   graceful fallback to `$PWD` if wrong, so it fails safe, but should be
   verified against a real herdr instance.
2. No live/smoke test against a real herdr server is included (see "dropped"
   above) — only the stubbed pytest suite. Recommend adding a manual smoke
   script before wide distribution if that's valuable.
3. `platforms = ["linux", "macos"]` in the manifest is inherited from the
   task spec as given; the script itself is portable bash + jq + awk with no
   OS-specific calls, so Windows/WSL should work too if herdr runs there —
   just not declared as a supported platform per the manifest schema given.
