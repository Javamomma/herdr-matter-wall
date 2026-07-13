# Build notes — v0.3.0 (full-brief cards, one matter per full-screen tab)

Port of the full-brief card redesign (built + tested first in a private
internal fork) into this public plugin. This file documents what changed
between v0.2.0 and v0.3.0, why, and what a maintainer with a real herdr
instance should double-check.

## What changed

### `render-card.sh`: full-brief card sections

The `<<<CARD ... CARD>>>` contract grew two new list sections on top of the
v0.2.0 fields:

```
<<<CARD
STATUS: ...
PHASE: ...
DEADLINE: <date> | <label>
RISK: <text> | <HIGH|MED|LOW>
RECENT:
- <YYYY-MM-DD> <thing that happened>
- ... (newest first)
AWAITING:
- <thing this item is waiting on>
- ...
NEXT: ...
CARD>>>
```

`RECENT` and `AWAITING` are list headers followed by `- ` bullet lines,
parsed by a new `list_field()` awk helper that reads until the next
ALL-CAPS `KEY:` header or block end. Rendering changes:

- **Word-wrap, not truncate.** Long `STATUS`/`RISK`/`NEXT` values and list
  bullets now wrap onto hanging-indented continuation lines (`wrap()` +
  `wrapped_line()`/`frameline()`) instead of being cut short with an
  ellipsis. A single token that's still too long to fit even one line hard-
  truncates with `…` (unchanged behavior for that edge case).
- **Caps:** `RECENT` shows up to 6 bullets (with a dim "…(+N more)" note
  past that); `AWAITING` shows up to 3 with no overflow note. The `AWAITING`
  section (its `── Awaiting ──` rule + bullets) is omitted entirely when
  there's nothing outstanding.
- **New section rule:** a dim `── <label> ──` divider (`rule()`), used for
  both `Recent (last 5–10d)` and `Awaiting`.
- **New `◆` deadline glyph**, replacing the old `📅` emoji glyph — plain
  ANSI box-drawing renders more reliably across terminal fonts than an
  emoji glyph.
- **`PHASE` renders on its own dim line** (`phase: <value>`) instead of
  being folded silently; it's suppressed entirely on the no-block fallback
  card.

This file is byte-identical to the private source version except for one
line removed from the header comment (a `docs/...` spec-path reference that
doesn't exist in this repo) — same convention as the v0.2.0 port.

### `matter-wall.sh`: one matter per full-screen tab (tiling removed)

`do_open` no longer tiles panes into a grid. It now opens one tab per item:
the first item runs in the workspace's own initial tab (renamed to the
item's slug via `tab rename`); every subsequent item gets a freshly created
tab (`tab create --workspace <ws> --label <slug>`). The `grid_dims()`
helper and the `--grid-dims` flag/dispatch case are removed entirely — full-
screen tabs aren't size-constrained the way a tiled pane grid was, so
there's no longer a "how many columns" computation to do.

`do_card`'s width now defaults to the pane's full `$COLUMNS` (fallback 80
if unset) instead of the old narrow-pane fallback of 40, capped at 100 so a
very wide terminal doesn't stretch the card absurdly:

```bash
local w; w="${COLUMNS:-$(tput cols 2>/dev/null || echo 80)}"; [[ "$w" =~ ^[0-9]+$ ]] || w=80; (( w > 100 )) && w=100
```

The `cd "${TARGET_DIR}/${slug}"` behavior in `do_card` is unchanged from
v0.2.0 — `--card` still resolves and `cd`s into the item's own subdirectory
before invoking the card agent, and `do_open` still forwards the already-
resolved `$TARGET_DIR` into each spawned `--card` process via `--dir`.

`do_refresh` was left untouched (still spawns inline via a split pane, not
a tab) — out of scope for this task, same as v0.2.0's note on it.

### `card-prompt.md`: rewritten for the full-brief contract

Sourcing instructions are unchanged (generic: `context.md`, `README.md`,
`STATUS.md`/`NOTES.md`/`CHANGELOG.md` if present) plus two additions: a
`git log --since="10 days ago" ...` invocation for dated `RECENT` bullets,
and a `find . -maxdepth 2 -type f -mtime -10` check for recently-touched
files as a secondary signal. The emitted block now asks for `RECENT`
(4–6 dated bullets, newest first, grounded in something actually read) and
`AWAITING` (1–3 items, omitted entirely if nothing's outstanding) in
addition to the v0.2.0 fields. Same "no fabrication" discipline as before:
absent files/facts render as `NONE` rather than being guessed at.

### `herdr-plugin.toml`: `version = "0.3.0"`

### Tests

- **`tests/test_render_card.py`**: added 7 tests for the full-brief
  sections — `PHASE` line rendering, `RECENT` bullets rendering newest-
  first, `AWAITING` bullets rendering under a headed rule, `AWAITING`
  omitted when absent, the 6-bullet `RECENT` cap with a "+N more" note, the
  3-bullet `AWAITING` cap with no overflow note, and a long bullet wrapping
  onto a continuation line without any rendered line exceeding the
  requested width. Also added the single-overlong-token hard-truncate
  regression test carried over from the private source. All fixtures use
  the repo's existing generic placeholders (`billing-service`, `Jane Doe`,
  `vendor SLA breach`, etc.) — no new company/personal-specific strings.
- **`tests/test_matter_wall.py`**: removed `test_grid_dims` (the tiling
  helper it tested no longer exists); replaced
  `test_open_multi_row_tiles_down_and_spawns_all` with
  `test_open_uses_one_tab_per_item`, which asserts on `tab create` count and
  per-item `--card <slug>` spawns instead of `pane split --direction down`;
  added `test_default_limit_is_five` (the default was already `5` in this
  repo's v0.1.0 port, unlike the private source which changed it in this
  same round — the test was simply missing here). Removed the now-unused
  `import pytest` (it was only used by the removed `test_grid_dims`
  parametrize decorator).
- **`tests/conftest.py`**: the `stub_bin` fixture's fake `herdr` script
  gained `tab create` / `tab list` / `tab rename` branches so the new
  `do_open` tab logic has something to respond to under test.
- All 42 tests pass (`16` render-card, up from `8` in v0.2.0 — full-brief
  coverage added; `26` matter-wall, down from `33` in v0.2.0 — the 9
  parametrized `test_grid_dims` cases are gone, netted against the tiling
  test being replaced by the tab test and the new default-limit test).

### README

- Replaced the "tiles ... as a live wall" framing and the 3-side-by-side
  tiled-pane mockup with a single full-brief card mockup (showing `PHASE`,
  the `◆` glyph, `Recent`/`Awaiting` sections) and a note that each item
  gets its own full-screen tab.
- Replaced the "Tiling" design-notes bullet (square-grid pane splitting)
  with a "One matter per full-screen tab" bullet describing the new
  tab-per-item model and the `$COLUMNS`-capped-at-100 width.
- Updated the card-rendering design-notes bullet to list the full field set
  (`RECENT`/`AWAITING` as list headers) and the wrap/cap behavior.
- Changed "wall pane" → "wall tab" in the `--card` usage explanation.

## What was NOT changed

- `do_refresh` still spawns its card agent inline via a split pane (not a
  tab) — out of scope for this task, consistent with v0.2.0.
- No new `herdr-plugin.toml` action was added for tabs specifically — the
  existing `open`/`close`/`dry-run` actions are unaffected by the
  pane-vs-tab implementation detail.
- No further genericization was needed in `card-prompt.md`'s source list
  beyond the two additions above — the file was already fully genericized
  in v0.1.0/v0.2.0.

## Leakage check

Ran the required grep for a list of internal identifiers (organization
names, personal names, internal paths, internal tool/file conventions)
across `*.sh`/`*.md`/`*.toml`/`*.py` — result: clean. No company/personal-
specific strings found.

## Verification run

- `bash -n matter-wall.sh render-card.sh` — clean.
- `python -m pytest tests/ -v` — 42 passed.
- `grep -n grid_dims matter-wall.sh` — empty (confirmed removed).
- Diffed `render-card.sh` against the private source with the header
  comment's spec-path line stripped from both sides — identical.

## Not done (per task instructions)

Committed locally only — **not pushed**. The controller pushes after a
leakage re-scan.
