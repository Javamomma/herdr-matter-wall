#!/usr/bin/env bash
# matter-wall — a glanceable herdr board of a project's most-active
# subdirectories. Spawns one read-only AI card agent per subdirectory pane;
# hybrid serialized --refresh so cards never trample each other.
set -euo pipefail

HERDR="${MATTER_WALL_HERDR:-${HERDR_BIN_PATH:-herdr}}"
CLAUDE="${MATTER_WALL_CLAUDE:-claude}"
DEFAULT_MODEL="claude-haiku-4-5-20251001"
DEFAULT_LIMIT=5
ALLOWLIST='Read Grep Glob Bash(git log:*)'
WORKSPACE_LABEL="Matter Wall"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# card-prompt.md ships alongside this script (the plugin's own directory),
# NOT the target project — herdr runs plugin actions with cwd=plugin dir.
PROMPT_TPL="${MATTER_WALL_PROMPT:-${SCRIPT_DIR}/card-prompt.md}"

# --- subdirectory marker ---------------------------------------------------
# A subdirectory is a candidate if it contains any one of these files.
# Default: context.md OR README.md. Override with a space-separated list.
declare -a MARKER_NAMES=()
resolve_marker_names() {
  local raw="${MATTER_WALL_MARKER:-context.md README.md}"
  read -ra MARKER_NAMES <<< "$raw"
}
resolve_marker_names

has_marker() {
  local dir="$1" name
  for name in "${MARKER_NAMES[@]}"; do
    [[ -f "${dir%/}/${name}" ]] && return 0
  done
  return 1
}

# --- target directory resolution -------------------------------------------
# Priority: --dir flag > $MATTER_WALL_DIR env > (if running as a herdr plugin
# action) the active workspace's cwd, queried over the herdr socket > $PWD.
TARGET_DIR_FLAG=""

query_workspace_cwd() {
  local ws="${HERDR_WORKSPACE_ID:-}"
  if [[ -z "$ws" && -n "${HERDR_PLUGIN_CONTEXT_JSON:-}" ]]; then
    ws="$(jq -r '.workspace_id? // .workspace?.workspace_id? // empty' <<<"$HERDR_PLUGIN_CONTEXT_JSON" 2>/dev/null || true)"
  fi
  [[ -n "$ws" ]] || return 1

  # Some herdr versions surface cwd directly on the workspace.
  local cwd
  cwd="$("$HERDR" workspace get "$ws" 2>/dev/null | jq -r '.result.workspace.cwd? // .result.cwd? // empty' 2>/dev/null || true)"
  if [[ -n "$cwd" && "$cwd" != "null" ]]; then
    printf '%s\n' "$cwd"; return 0
  fi

  # Fall back to the workspace's first pane.
  local pane
  pane="$("$HERDR" pane list --workspace "$ws" 2>/dev/null | jq -r '.result.panes[0].pane_id? // empty' 2>/dev/null || true)"
  [[ -n "$pane" ]] || return 1
  cwd="$("$HERDR" pane get "$pane" 2>/dev/null | jq -r '.result.pane.cwd? // .result.cwd? // empty' 2>/dev/null || true)"
  [[ -n "$cwd" && "$cwd" != "null" ]] || return 1
  printf '%s\n' "$cwd"
}

resolve_target_dir() {
  if [[ -n "$TARGET_DIR_FLAG" ]]; then printf '%s\n' "$TARGET_DIR_FLAG"; return; fi
  if [[ -n "${MATTER_WALL_DIR:-}" ]]; then printf '%s\n' "$MATTER_WALL_DIR"; return; fi
  if [[ -n "${HERDR_PLUGIN_CONTEXT_JSON:-}" || -n "${HERDR_WORKSPACE_ID:-}" ]]; then
    local cwd
    if cwd="$(query_workspace_cwd)"; then
      printf '%s\n' "$cwd"; return
    fi
  fi
  printf '%s\n' "$PWD"
}

# --- ranking -----------------------------------------------------------
list_candidates() {
  local d
  for d in "${TARGET_DIR}"/*/; do
    [[ -d "$d" ]] || continue
    has_marker "$d" || continue
    basename "$d"
  done
}

item_recency() {
  local slug="$1" dir="${TARGET_DIR}/${slug}" git_ts fs_ts
  git_ts="$(git -C "${TARGET_DIR}" log -1 --format=%ct -- "$slug" 2>/dev/null || true)"
  git_ts="${git_ts:-0}"
  fs_ts="$(find "$dir" -type f -printf '%T@\n' 2>/dev/null | cut -d. -f1 | sort -rn | head -1)"
  fs_ts="${fs_ts:-0}"
  (( git_ts > fs_ts )) && echo "$git_ts" || echo "$fs_ts"
}

rank_items() {
  local limit="$1" slug
  list_candidates | while IFS= read -r slug; do
    printf '%s\t%s\n' "$(item_recency "$slug")" "$slug"
  done | sort -rn -k1,1 | head -n "$limit" | cut -f2
}

select_items() {
  # Explicit slugs win (verbatim order, unknown ones skipped with a warning);
  # otherwise rank all candidates and keep the top-N.
  if [[ ${#SLUGS[@]} -gt 0 ]]; then
    local slug
    for slug in "${SLUGS[@]}"; do
      if [[ -d "${TARGET_DIR}/${slug}" ]] && has_marker "${TARGET_DIR}/${slug}"; then
        printf '%s\n' "$slug"
      else
        echo "matter-wall: unknown item: $slug (skipped)" >&2
      fi
    done
  else
    rank_items "$LIMIT"
  fi
}

render_prompt() {
  local slug="$1"
  [[ -f "$PROMPT_TPL" ]] || { echo "matter-wall: missing $PROMPT_TPL" >&2; exit 66; }
  sed "s/{{SLUG}}/${slug}/g" "$PROMPT_TPL"
}

require_herdr() {
  if [[ -z "${HERDR_ENV:-}" && -z "${HERDR_SOCKET_PATH:-}" ]]; then
    echo "matter-wall: run inside a herdr session (HERDR_ENV/HERDR_SOCKET_PATH unset)" >&2
    exit 1
  fi
  "$HERDR" status server >/dev/null 2>&1 || { echo "matter-wall: herdr server not running" >&2; exit 1; }
}

grid_dims() {
  local n="$1" cols rows
  cols=$(awk -v n="$n" 'BEGIN{c=int(sqrt(n)); if(c*c<n)c++; print c}')
  rows=$(awk -v n="$n" -v c="$cols" 'BEGIN{r=int(n/c); if(r*c<n)r++; print r}')
  echo "$cols $rows"
}

wall_workspace_id() {
  "$HERDR" workspace list 2>/dev/null \
    | jq -r '.result.workspaces[]? | select(.label=="Matter Wall") | .workspace_id' | head -1
}

wall_first_pane() {
  local ws="$1"
  "$HERDR" pane list --workspace "$ws" 2>/dev/null | jq -r '.result.panes[0].pane_id // empty'
}

pane_id_from() { jq -r '.result.pane.pane_id // .result.root_pane.pane_id // empty'; }

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

do_open() {
  require_herdr
  mapfile -t chosen < <(select_items)
  [[ ${#chosen[@]} -gt 0 ]] || { echo "matter-wall: no items to show" >&2; exit 1; }
  echo "matter-wall: opening ${#chosen[@]} ${MODEL} card agent(s) (~${#chosen[@]} calls)"

  # Idempotency: close any existing wall.
  local existing; existing="$(wall_workspace_id || true)"
  [[ -n "$existing" ]] && "$HERDR" workspace close "$existing" >/dev/null 2>&1 || true

  # Create workspace; capture root pane.
  local ws root; root="$("$HERDR" workspace create --label "$WORKSPACE_LABEL" --no-focus | pane_id_from)"
  ws="$(wall_workspace_id)"

  # Tile: build panes list starting from root.
  local n="${#chosen[@]}"; read -r cols _ < <(grid_dims "$n")
  declare -a panes=("$root") col_bottom=()
  # first row: split root right (cols-1) times
  local i last="$root"
  for ((i=1; i<cols && ${#panes[@]}<n; i++)); do
    last="$("$HERDR" pane split "$last" --direction right --no-focus | pane_id_from)"
    panes+=("$last")
  done
  col_bottom=("${panes[@]}")
  # remaining panes: split downward, round-robin across columns
  local c=0
  while (( ${#panes[@]} < n )); do
    local target="${col_bottom[$c]}"
    local np; np="$("$HERDR" pane split "$target" --direction down --no-focus | pane_id_from)"
    panes+=("$np"); col_bottom[$c]="$np"
    c=$(( (c+1) % cols ))
  done

  # Spawn one read-only card agent per pane via the hidden --card mode, which
  # cd's into the item's own subdirectory, renders the prompt, invokes the
  # model, then hands the transcript to render-card.sh for a colored,
  # width-fitted card (a plugin-action pane's default cwd is not guaranteed
  # to be the target project, so --card does an explicit, absolute cd).
  local idx=0 slug pane
  for slug in "${chosen[@]}"; do
    pane="${panes[$idx]}"; idx=$((idx+1))
    "$HERDR" pane rename "$pane" "$slug" >/dev/null 2>&1 || true
    "$HERDR" pane run "$pane" "bash $(printf %q "${SCRIPT_DIR}/$(basename "$0")") --dir $(printf %q "$TARGET_DIR") --card $(printf %q "$slug")"
  done
  echo "matter-wall: wall up (workspace ${ws})"
}

do_refresh() {
  local slug="$1"
  require_herdr
  { [[ -d "${TARGET_DIR}/${slug}" ]] && has_marker "${TARGET_DIR}/${slug}"; } \
    || { echo "matter-wall: unknown item: $slug" >&2; exit 64; }
  if [[ -f "$LOCK" ]]; then
    echo "matter-wall: a refresh is already running (pane $(cat "$LOCK"))" >&2; exit 1
  fi
  mkdir -p "$(dirname "$LOCK")"
  local ws root; ws="$(wall_workspace_id || true)"
  if [[ -n "$ws" ]]; then
    root="$("$HERDR" pane split "$(wall_first_pane "$ws")" --direction down --no-focus | pane_id_from)"
  else
    root="$("$HERDR" workspace create --label "$WORKSPACE_LABEL" --no-focus | pane_id_from)"
  fi
  echo "$root" > "$LOCK"
  # shellcheck disable=SC2064
  trap "rm -f '$LOCK'" EXIT
  "$HERDR" pane rename "$root" "refresh:$slug" >/dev/null 2>&1 || true
  local prompt; prompt="$(render_prompt "$slug")"
  "$HERDR" pane run "$root" "cd $(printf %q "${TARGET_DIR}/${slug}") && $CLAUDE -p $(printf %q "$prompt") --model $MODEL --allowedTools 'Read Grep Glob Bash(git log:*)' ; echo MATTERWALL_REFRESH_DONE"
  "$HERDR" wait output "$root" --match MATTERWALL_REFRESH_DONE --timeout 600000 >/dev/null 2>&1 || true
  rm -f "$LOCK"; trap - EXIT
  echo "matter-wall: refresh complete ($slug)"
}

do_close() {
  require_herdr
  local ws; ws="$(wall_workspace_id || true)"
  [[ -n "$ws" ]] && "$HERDR" workspace close "$ws" >/dev/null 2>&1 || true
  rm -f "$LOCK"
  echo "matter-wall: closed"
}

# --- arg parsing -------------------------------------------------------
MODE="open"
LIMIT="$DEFAULT_LIMIT"
MODEL="$DEFAULT_MODEL"
REFRESH_SLUG=""
RENDER_SLUG=""
CARD_SLUG=""
GRID_N=""
DRY_RUN=0
declare -a SLUGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir)
      [[ $# -ge 2 ]] || { echo "matter-wall: --dir requires a value" >&2; exit 64; }
      TARGET_DIR_FLAG="$2"; shift 2;;
    --rank-only) MODE="rank-only"; shift;;
    --grid-dims)
      [[ $# -ge 2 ]] || { echo "matter-wall: --grid-dims requires a value" >&2; exit 64; }
      MODE="grid-dims"; GRID_N="$2"; shift 2;;
    --close) MODE="close"; shift;;
    --refresh)
      [[ $# -ge 2 ]] || { echo "matter-wall: --refresh requires a value" >&2; exit 64; }
      MODE="refresh"; REFRESH_SLUG="$2"; shift 2;;
    --render-prompt)
      [[ $# -ge 2 ]] || { echo "matter-wall: --render-prompt requires a value" >&2; exit 64; }
      MODE="render-prompt"; RENDER_SLUG="$2"; shift 2;;
    --card)
      [[ $# -ge 2 ]] || { echo "matter-wall: --card requires a value" >&2; exit 64; }
      MODE="card"; CARD_SLUG="$2"; shift 2;;
    --limit)
      [[ $# -ge 2 ]] || { echo "matter-wall: --limit requires a value" >&2; exit 64; }
      LIMIT="$2"; shift 2;;
    --model)
      [[ $# -ge 2 ]] || { echo "matter-wall: --model requires a value" >&2; exit 64; }
      MODEL="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    --*) echo "matter-wall: unknown argument: $1" >&2; exit 64;;
    *) SLUGS+=("$1"); shift;;
  esac
done

TARGET_DIR="$(resolve_target_dir)"
[[ -d "$TARGET_DIR" ]] || { echo "matter-wall: target directory not found: $TARGET_DIR" >&2; exit 66; }

STATE_DIR="${MATTER_WALL_STATE_DIR:-${TARGET_DIR}/.matter-wall}"
LOCK="${STATE_DIR}/refresh.lock"

print_plan() {
  local items; items="$(select_items | paste -sd, -)"
  echo "PLAN model=${MODEL} matters=${items}"
  local slug
  for slug in ${items//,/ }; do echo "SPAWN ${slug}"; done
}

case "$MODE" in
  rank-only) rank_items "$LIMIT";;
  grid-dims) grid_dims "$GRID_N";;
  render-prompt) render_prompt "$RENDER_SLUG";;
  card) do_card "$CARD_SLUG";;
  refresh)
    if [[ "$DRY_RUN" -eq 1 ]]; then echo "PLAN refresh=${REFRESH_SLUG}"; exit 0; fi
    do_refresh "$REFRESH_SLUG";;
  close)
    if [[ "$DRY_RUN" -eq 1 ]]; then echo "PLAN close"; exit 0; fi
    do_close;;
  open)
    if [[ "$DRY_RUN" -eq 1 ]]; then print_plan; exit 0; fi
    do_open;;
esac
