#!/usr/bin/env bash
# render-card.sh — draw ONE colored, width-fitted status card.
# Reads the agent's stdout on STDIN (expects a <<<CARD ... CARD>>> block).
# Usage: render-card.sh <slug> <width> [today]
# Pure presentation: no LLM, no herdr. Must always print a card (never abort).
set -uo pipefail

SLUG="${1:-item}"
WIDTH="${2:-40}"; [[ "$WIDTH" =~ ^[0-9]+$ ]] || WIDTH=40; (( WIDTH < 24 )) && WIDTH=24
TODAY="${3:-${MATTER_WALL_TODAY:-$(date +%F)}}"

RED=196; AMBER=214; GREEN=42; CYAN=45; GOLD=178; DIM=240
USE_COLOR=0
if [[ -z "${NO_COLOR:-}" ]] && { [[ -t 1 ]] || [[ -n "${MATTER_WALL_FORCE_COLOR:-}" ]]; }; then USE_COLOR=1; fi
c()    { (( USE_COLOR )) && printf '\033[38;5;%sm' "$1"; return 0; }
bold() { (( USE_COLOR )) && printf '\033[1m'; return 0; }
rst()  { (( USE_COLOR )) && printf '\033[0m'; return 0; }

# bash 3.2 has no ${var^^}/${var,,}; fold case with tr instead.
upper() { printf '%s' "$1" | tr '[:lower:]' '[:upper:]'; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# portable date→epoch (midnight): BSD `date -j -f` first, GNU `date -d` fallback.
to_epoch() {
  local s="$1" e
  e="$(date -j -f "%Y-%m-%d %H:%M:%S" "$s 00:00:00" +%s 2>/dev/null)" && { printf '%s' "$e"; return 0; }
  e="$(date -d "$s" +%s 2>/dev/null)" && { printf '%s' "$e"; return 0; }
  return 1
}

raw="$(cat)"
block="$(printf '%s\n' "$raw" | awk '/<<<CARD/{f=1;next} /CARD>>>/{f=0} f')"
field() { printf '%s\n' "$block" | grep -m1 "^$1:" | sed "s/^$1:[[:space:]]*//"; }
# Extract "- " bullet lines under a LIST header ("RECENT:"/"AWAITING:") until
# the next ALL-CAPS "KEY:" header or block end.
list_field() {
  local key="$1"
  printf '%s\n' "$block" | awk -v key="${key}:" '
    index($0, key) == 1 { f=1; next }
    /^[A-Z][A-Z_]*:/ { f=0 }
    f && /^-/ { sub(/^-[[:space:]]*/, ""); print }
  '
}

FALLBACK=0
declare -a RECENT_ITEMS=() AWAITING_ITEMS=()
if [[ -n "$block" ]]; then
  STATUS="$(field STATUS)"; PHASE="$(field PHASE)"
  DEADLINE="$(field DEADLINE)"; RISK="$(field RISK)"; NEXT="$(field NEXT)"
  RECENT_ITEMS=()
  while IFS= read -r _l || [[ -n "$_l" ]]; do RECENT_ITEMS+=("$_l"); done < <(list_field RECENT)
  AWAITING_ITEMS=()
  while IFS= read -r _l || [[ -n "$_l" ]]; do AWAITING_ITEMS+=("$_l"); done < <(list_field AWAITING)
else
  FALLBACK=1
  first="$(printf '%s\n' "$raw" | grep -m1 -v '^[[:space:]]*$' | tr -s '[:space:]' ' ' | sed 's/^ //;s/ $//')"
  STATUS="(no summary)"; [[ -n "$first" ]] && STATUS="(no summary) — $first"
  PHASE=""; DEADLINE="NONE"; RISK="NONE"; NEXT="none"
fi
[[ -z "${STATUS:-}" ]] && STATUS="(no summary)"
: "${DEADLINE:=NONE}" "${RISK:=NONE}" "${NEXT:=none}" "${PHASE:=}"

# deadline
dl_text=""; dl_rank=-1
if [[ -n "$DEADLINE" && "$(upper "$DEADLINE")" != "NONE" ]]; then
  d="${DEADLINE%%|*}"; d="$(printf '%s' "$d" | sed 's/^ *//;s/ *$//')"
  lbl=""; [[ "$DEADLINE" == *"|"* ]] && lbl="$(printf '%s' "${DEADLINE#*|}" | sed 's/^ *//;s/ *$//')"
  de="$(to_epoch "$d" || true)"; te="$(to_epoch "$TODAY" || true)"
  if [[ -n "$de" && -n "$te" ]]; then
    days=$(( (de - te) / 86400 ))
    if   (( days <  0 )); then dl_text="$d · $(( -days ))d OVERDUE"; dl_rank=2
    elif (( days == 0 )); then dl_text="$d · today";                dl_rank=2
    elif (( days <= 7 )); then dl_text="$d · ${days}d";             dl_rank=2
    elif (( days <= 30 )); then dl_text="$d · ${days}d";            dl_rank=1
    else                        dl_text="$d · ${days}d";            dl_rank=0
    fi
  else
    dl_text="$d${lbl:+ · $lbl}"; dl_rank=0   # unparseable date: show it, no count
  fi
fi

# risk
risk_text=""; risk_rank=-1
if [[ -n "$RISK" && "$(upper "$RISK")" != "NONE" ]]; then
  rt="${RISK%%|*}"; rt="$(printf '%s' "$rt" | sed 's/^ *//;s/ *$//')"
  sev=""; [[ "$RISK" == *"|"* ]] && sev="$(printf '%s' "${RISK#*|}" | sed 's/^ *//;s/ *$//' | tr '[:lower:]' '[:upper:]')"
  case "$sev" in HIGH) risk_rank=2;; MED|MEDIUM) risk_rank=1; sev=MED;; LOW) risk_rank=0;; *) risk_rank=0; sev="${sev:-}";; esac
  risk_text="$rt${sev:+ · $sev}"
fi

worst=-1; (( dl_rank > worst )) && worst=$dl_rank; (( risk_rank > worst )) && worst=$risk_rank
case "$worst" in 2) BORDER=$RED;; 1) BORDER=$AMBER;; *) BORDER=$GREEN;; esac
(( FALLBACK )) && BORDER=$AMBER
rankcol() { case "$1" in 2) printf '%s' $RED;; 1) printf '%s' $AMBER;; 0) printf '%s' $GREEN;; *) printf '%s' $DIM;; esac; }

INNER=$(( WIDTH - 4 ))          # content width between "│ " and " │"
trunc() { local s="$1" m="$2"; (( m < 1 )) && m=1; if (( ${#s} > m )); then printf '%s…' "${s:0:m-1}"; else printf '%s' "$s"; fi; }
# repeat a (possibly multi-byte) char N times; `tr` is byte-wise and mangles UTF-8, so build in bash
repeat_char() { local ch="$1" n="$2" s="" i; (( n <= 0 )) && return 0; for (( i = 0; i < n; i++ )); do s+="$ch"; done; printf '%s' "$s"; }

# word-wrap TEXT to MAXW columns (like `fold -s`): break on spaces, no
# mid-word breaks unless a single token exceeds MAXW (then hard-truncate with
# an ellipsis). Result lines land in the WRAP_OUT array (always >=1 line).
wrap() {
  local text="$1" maxw="$2"
  (( maxw < 1 )) && maxw=1
  WRAP_OUT=()
  local word cur=""
  for word in $text; do
    if (( ${#word} > maxw )); then
      [[ -n "$cur" ]] && { WRAP_OUT+=("$cur"); cur=""; }
      WRAP_OUT+=("$(trunc "$word" "$maxw")")
      continue
    fi
    if [[ -z "$cur" ]]; then
      cur="$word"
    elif (( ${#cur} + 1 + ${#word} <= maxw )); then
      cur="$cur $word"
    else
      WRAP_OUT+=("$cur"); cur="$word"
    fi
  done
  [[ -n "$cur" ]] && WRAP_OUT+=("$cur")
  (( ${#WRAP_OUT[@]} == 0 )) && WRAP_OUT=("")
}

# print one framed content line WITH a leading icon (first line of a field).
# args: icon icon_display_width text valuecolor
line() {
  local icon="$1" iw="$2" text="$3" col="$4"
  local maxt=$(( INNER - iw - 1 )); (( maxt < 1 )) && maxt=1
  text="$(trunc "$text" "$maxt")"
  local vw=$(( iw + 1 + ${#text} )); local pad=$(( INNER - vw )); (( pad < 0 )) && pad=0
  c "$BORDER"; printf '│'; rst; printf ' %s ' "$icon"
  [[ -n "$col" ]] && c "$col"; printf '%s' "$text"; [[ -n "$col" ]] && rst
  printf '%*s ' "$pad" ''; c "$BORDER"; printf '│'; rst; printf '\n'
}

# print one framed content line with NO icon — used for wrapped continuation
# lines and section rules. Content is truncated/padded to exactly INNER cols.
frameline() {
  local text="$1" col="$2"
  text="$(trunc "$text" "$INNER")"
  local pad=$(( INNER - ${#text} )); (( pad < 0 )) && pad=0
  c "$BORDER"; printf '│ '; rst
  [[ -n "$col" ]] && c "$col"; printf '%s' "$text"; [[ -n "$col" ]] && rst
  printf '%*s' "$pad" ''; c "$BORDER"; printf ' │'; rst; printf '\n'
}

# print a wrapped field: first line via `line` (with icon), continuation
# lines via `frameline`, hanging-indented under the icon.
wrapped_line() {
  local icon="$1" iw="$2" text="$3" col="$4"
  local avail=$(( INNER - iw - 1 )); (( avail < 1 )) && avail=1
  wrap "$text" "$avail"
  line "$icon" "$iw" "${WRAP_OUT[0]}" "$col"
  local indent; indent="$(repeat_char ' ' $(( iw + 1 )))"
  local i
  for (( i = 1; i < ${#WRAP_OUT[@]}; i++ )); do
    frameline "${indent}${WRAP_OUT[$i]}" "$col"
  done
}

# dim section rule, e.g. "── Recent (last 5–10d) ──", dashes fill to INNER.
rule() {
  local label="$1" prefix fill content
  prefix="── ${label} "
  fill=$(( INNER - ${#prefix} ))
  if (( fill > 0 )); then content="${prefix}$(repeat_char '─' "$fill")"; else content="$prefix"; fi
  frameline "$content" "$DIM"
}

# top rule with slug (gold), fill to WIDTH
top() {
  local label; label="$(trunc "$SLUG" $(( WIDTH - 4 )) )"
  local used=$(( 2 + ${#label} ))   # "╭ " + label
  local fill=$(( WIDTH - used - 2 )); (( fill < 0 )) && fill=0   # -2 for the trailing " " + "╮"
  c "$BORDER"; printf '╭ '; rst; bold; c "$GOLD"; printf '%s' "$label"; rst
  printf ' '; c "$BORDER"; repeat_char '─' "$fill"; printf '╮'; rst; printf '\n'
}
bottom() { c "$BORDER"; printf '╰'; repeat_char '─' $(( WIDTH - 2 )); printf '╯'; rst; printf '\n'; }

# --- draw ---
top
wrapped_line "●" 1 "$STATUS" ""
if (( ! FALLBACK )) && [[ -n "$PHASE" ]]; then
  wrap "phase: $PHASE" "$INNER"; for _seg in "${WRAP_OUT[@]}"; do frameline "$_seg" "$DIM"; done
fi
if [[ -n "$dl_text" ]]; then line "◆" 1 "$dl_text" "$(rankcol "$dl_rank")"; else line "◆" 1 "none" "$DIM"; fi
if [[ -n "$risk_text" ]]; then wrapped_line "⚠" 1 "$risk_text" "$(rankcol "$risk_rank")"; else line "⚠" 1 "none" "$DIM"; fi

if (( ! FALLBACK )); then
  rule "Recent (last 5–10d)"
  if (( ${#RECENT_ITEMS[@]} == 0 )); then
    wrapped_line "•" 1 "none" "$DIM"
  else
    n=${#RECENT_ITEMS[@]}; cap=6; (( n < cap )) && cap=$n
    for (( i = 0; i < cap; i++ )); do wrapped_line "•" 1 "${RECENT_ITEMS[$i]}" ""; done
    (( n > 6 )) && wrapped_line "•" 1 "…(+$(( n - 6 )) more)" "$DIM"
  fi

  if (( ${#AWAITING_ITEMS[@]} > 0 )); then
    rule "Awaiting"
    n=${#AWAITING_ITEMS[@]}; cap=3; (( n < cap )) && cap=$n
    for (( i = 0; i < cap; i++ )); do wrapped_line "•" 1 "${AWAITING_ITEMS[$i]}" ""; done
  fi
fi

if [[ -n "$NEXT" && "$(lower "$NEXT")" != "none" ]]; then wrapped_line "▶" 1 "$NEXT" "$CYAN"; else line "▶" 1 "nothing pending" "$DIM"; fi
bottom
c "$DIM"; printf ' as of %s\n' "$(date +%H:%M)"; rst
exit 0
