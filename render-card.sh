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

raw="$(cat)"
block="$(printf '%s\n' "$raw" | awk '/<<<CARD/{f=1;next} /CARD>>>/{f=0} f')"
field() { printf '%s\n' "$block" | grep -m1 "^$1:" | sed "s/^$1:[[:space:]]*//"; }

FALLBACK=0
if [[ -n "$block" ]]; then
  STATUS="$(field STATUS)"; DEADLINE="$(field DEADLINE)"; RISK="$(field RISK)"; NEXT="$(field NEXT)"
else
  FALLBACK=1
  first="$(printf '%s\n' "$raw" | grep -m1 -v '^[[:space:]]*$' | tr -s '[:space:]' ' ' | sed 's/^ //;s/ $//')"
  STATUS="(no summary)"; [[ -n "$first" ]] && STATUS="(no summary) — $first"
  DEADLINE="NONE"; RISK="NONE"; NEXT="none"
fi
[[ -z "${STATUS:-}" ]] && STATUS="(no summary)"
: "${DEADLINE:=NONE}" "${RISK:=NONE}" "${NEXT:=none}"

# deadline
dl_text=""; dl_rank=-1
if [[ -n "$DEADLINE" && "${DEADLINE^^}" != "NONE" ]]; then
  d="${DEADLINE%%|*}"; d="$(printf '%s' "$d" | sed 's/^ *//;s/ *$//')"
  lbl=""; [[ "$DEADLINE" == *"|"* ]] && lbl="$(printf '%s' "${DEADLINE#*|}" | sed 's/^ *//;s/ *$//')"
  de="$(date -d "$d" +%s 2>/dev/null || true)"; te="$(date -d "$TODAY" +%s 2>/dev/null || true)"
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
if [[ -n "$RISK" && "${RISK^^}" != "NONE" ]]; then
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

# print one framed content line.  args: icon icon_display_width text valuecolor
line() {
  local icon="$1" iw="$2" text="$3" col="$4"
  local maxt=$(( INNER - iw - 1 )); (( maxt < 1 )) && maxt=1
  text="$(trunc "$text" "$maxt")"
  local vw=$(( iw + 1 + ${#text} )); local pad=$(( INNER - vw )); (( pad < 0 )) && pad=0
  c "$BORDER"; printf '│'; rst; printf ' %s ' "$icon"
  [[ -n "$col" ]] && c "$col"; printf '%s' "$text"; [[ -n "$col" ]] && rst
  printf '%*s ' "$pad" ''; c "$BORDER"; printf '│'; rst; printf '\n'
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
line "●" 1 "$STATUS" ""
if [[ -n "$dl_text" ]]; then line "📅" 2 "$dl_text" "$(rankcol "$dl_rank")"; else line "📅" 2 "none" "$DIM"; fi
if [[ -n "$risk_text" ]]; then line "⚠" 1 "$risk_text" "$(rankcol "$risk_rank")"; else line "⚠" 1 "none" "$DIM"; fi
if [[ -n "$NEXT" && "${NEXT,,}" != "none" ]]; then line "▶" 1 "$NEXT" "$CYAN"; else line "▶" 1 "nothing pending" "$DIM"; fi
bottom
c "$DIM"; printf ' as of %s\n' "$(date +%H:%M)"; rst
exit 0
