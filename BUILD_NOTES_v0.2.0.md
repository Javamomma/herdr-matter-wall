# Build notes — v0.2.0 (colored status cards)

Port of the card-rendering redesign (built + tested first in a private
internal fork) into this public plugin. This file documents what changed
between v0.1.0 and v0.2.0, why, and what a maintainer with a real herdr
instance should double-check.

## What changed

### New: `render-card.sh`

A standalone, pure-bash renderer. It has no LLM and no herdr dependency: it
reads an agent's stdout on stdin, looks for a fenced

```
<<<CARD
STATUS: ...
PHASE: ...
DEADLINE: <date> | <label>
RISK: <text> | <HIGH|MED|LOW>
NEXT: ...
CARD>>>
```

block, and draws a colored, width-fit box (`╭─ slug ─╮ / │ │ / ╰─╯`) sized to
the terminal's `$COLUMNS` (or a caller-supplied width). Border color encodes
the worst of the deadline/risk severity (red = overdue or high, amber = due
soon or medium, green = healthy/none). Day-counts are computed by the
renderer from the date the agent reports — the agent is instructed not to do
that arithmetic itself. If the agent's output has no parseable block at all,
the renderer still always prints *something* (a dim "(no summary)" card) and
always exits `0` — a single bad card is never allowed to take down the whole
wall.

This file is byte-identical to the private source version except for one
line removed from the header comment (a `docs/...` spec-path reference that
doesn't exist in this repo).

### New: hidden `--card <slug>` mode in `matter-wall.sh`

```bash
do_card() {
  local slug="$1"
  local w; w="${COLUMNS:-$(tput cols 2>/dev/null || echo 40)}"
  printf '\033[2m⏳ %s …\033[0m\n' "$slug"
  cd "${TARGET_DIR}/${slug}" 2>/dev/null || true
  local out
  out="$(timeout "${MATTER_WALL_CARD_TIMEOUT:-120}" "$CLAUDE" -p "$(render_prompt "$slug")" \
        --model "$MODEL" --allowedTools 'Read Grep Glob Bash(git log:*)' 2>/dev/null)" || true
  clear 2>/dev/null || printf '\033[2J\033[H'
  printf '%s' "$out" | MATTER_WALL_FORCE_COLOR=1 bash "${SCRIPT_DIR}/render-card.sh" "$slug" "$w"
}
```

`do_card` reuses `$TARGET_DIR` — the same global the script computes once
(`resolve_target_dir()`, run right after arg parsing: `--dir` flag >
`$MATTER_WALL_DIR` > herdr-socket workspace cwd > `$PWD`) and that `do_open`
already used. There's no separate resolution path to keep in sync: `--card`
and `do_open` are guaranteed to agree on the target directory because they
read the same variable.

`do_open`'s per-pane spawn changed from directly inlining `cd ... && claude
-p ...` into the `herdr pane run` command to just:

```bash
"$HERDR" pane run "$pane" "bash $(printf %q "$0") --card $(printf %q "$slug")"
```

i.e. each pane now re-invokes this same script in `--card` mode instead of
duplicating the cd/claude/allowlist logic inline. `--card` is not wired into
`herdr-plugin.toml` as its own action (no per-item slug to bind it to at
install time) — it's purely an internal spawn target for `do_open`, though
it's also documented in the README as directly runnable for one-off testing
against a single item.

`do_refresh` was intentionally left untouched (inline `cd && claude -p ...`,
same as before) — the task scope was `do_open`'s spawn only.

### Rewrote `card-prompt.md`

Old prompt asked for an ad hoc "compact card" (`Status: / Next milestone: /
Top risk: / Last activity: / Needs attention:`) with no machine-parseable
structure. New prompt asks for the `<<<CARD ... CARD>>>` block
`render-card.sh` expects (`STATUS`/`PHASE`/`DEADLINE`/`RISK`/`NEXT`), tells
the agent to emit the raw date it read (not a day-count — the renderer
computes that), and to use `NONE`/`none` conventions for absent fields.
Sources it's told to read are unchanged (generic: `context.md`, `README.md`,
`STATUS.md`/`NOTES.md`/`CHANGELOG.md` if present, `git log` for the current
directory) — this file was already fully genericized in v0.1.0, no
company-specific rewrite needed here.

### `herdr-plugin.toml`: `version = "0.2.0"`

### Tests

- **New `tests/test_render_card.py`** (copied from the private source,
  8 tests): field placement, future/overdue day-count math, width/truncation
  (no line ever exceeds the requested width), color-on-high-risk, `NO_COLOR`
  opt-out, fallback-card-on-no-block, and dim/green styling for all-`NONE`
  fields. Needed only a two-line path-constant fix for this repo's flat
  layout (`REPO = parents[1]`, `RC = REPO / "render-card.sh"` instead of the
  private repo's `bin/` subdirectory layout).
- **Updated `tests/test_matter_wall.py`**: the two tests that asserted on the
  old inline `claude -p` spawn string (`test_open_spawns_one_card_per_item`,
  `test_open_multi_row_tiles_down_and_spawns_all`) now assert on `--card`
  instead, since that's what's actually in the `pane run` command now. Added
  `test_open_spawns_card_mode_per_item` (exact `--card <slug>` count per
  item) and, per the task's ask for a hermetic public allowlist test, added
  **`test_card_mode_invokes_claude_with_readonly_allowlist`**: it runs
  `--card` directly (no herdr stub interaction needed — `do_card` never
  calls `require_herdr`) against a stubbed `claude` and asserts the logged
  invocation carries `--allowedTools Read Grep Glob Bash(git log:*)`
  verbatim. It overrides `$MATTER_WALL_PROMPT` with a single-line template
  for the test only, to avoid the packaged multi-line `card-prompt.md`
  splitting the stub's single logged invocation across multiple physical
  log lines (a test-harness quirk of `echo "claude $*"`, not a real
  multi-invocation bug — same technique the private source's test suite
  used). This test **does not require herdr** at all: no herdr binary, no
  herdr server, no herdr socket — it validates `--card`'s safety invariant
  in complete isolation.
- All 41 tests pass (`8` render-card + `33` matter-wall, up from `31` in
  v0.1.0: 2 new `--card`-mode tests, net of the 0 removed).

### README

- Replaced the old plain-text card mockup with one reflecting the new
  box-drawing/emoji card shape.
- Added a UTF-8 locale line to Requirements: `render-card.sh` slices strings
  by character for truncation/padding, which needs a UTF-8 locale to handle
  the box-drawing and emoji characters correctly (this environment runs
  `C.UTF-8`, which is fine — flagging for any deployment target that isn't).
- Documented `--card <slug>` in Usage and the env/flags table, plus new
  `$MATTER_WALL_CARD_TIMEOUT` / `$MATTER_WALL_FORCE_COLOR` / `$NO_COLOR`
  rows.
- Added a Design Notes bullet on the card-rendering contract (block format,
  pure/no-LLM renderer, always-exits-0/fallback guarantee) and a Testing
  bullet noting `test_render_card.py` needs no stubs.

## What was NOT changed

- `do_refresh` still spawns its card agent inline (not via `--card`) — out
  of scope for this task.
- No new `herdr-plugin.toml` action was added for `--card` — it has no
  natural per-item binding at plugin-install time; it's reached only via
  `do_open`'s spawn or direct script invocation.
- No further genericization was needed in `card-prompt.md`'s source list —
  that was already done in the v0.1.0 extraction.

## Leakage check

Grepped the working tree for a list of internal identifiers (organization
names, personal names, internal paths, and internal tool/file conventions) —
result: clean. No company/personal-specific strings found.

## Verification run

- `bash -n matter-wall.sh render-card.sh` — clean.
- `python -m pytest tests/ -v` — 41 passed.
- Manual smoke test: `MATTER_WALL_CLAUDE=<stub> MATTER_WALL_DIR=<tmp>
  COLUMNS=48 bash matter-wall.sh --card widget-service` against a
  hand-written stub `claude` emitting a `<<<CARD...CARD>>>` block — produced
  a correctly colored (amber, medium-risk/26-day-out) box, cleared the
  screen first, and exited 0.

## Not done (per task instructions)

Committed locally only — **not pushed**. The controller pushes after a
leakage re-scan.
