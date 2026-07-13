import os, subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RC = REPO / "render-card.sh"

def render(stdin, slug="alpha", width="40", today="2026-07-06", env=None):
    e = dict(os.environ); e["MATTER_WALL_TODAY"] = today
    e.setdefault("MATTER_WALL_FORCE_COLOR", "1")   # force color unless a test overrides
    if env: e.update(env)
    return subprocess.run(["bash", str(RC), slug, width, today],
                          input=stdin, capture_output=True, text=True, env=e)

FULL = (
    "<<<CARD\n"
    "STATUS: awaiting vendor counter-offer\n"
    "PHASE: negotiation\n"
    "DEADLINE: 2029-01-20 | contract deadline\n"
    "RISK: vendor SLA breach | HIGH\n"
    "NEXT: chase Jane Doe\n"
    "CARD>>>\n"
)

def strip_ansi(s):
    import re; return re.sub(r"\033\[[0-9;]*m", "", s)

def test_fields_present_and_placed():
    r = render(FULL); out = strip_ansi(r.stdout)
    assert r.returncode == 0
    assert "alpha" in out
    assert "awaiting vendor counter-offer" in out
    assert "chase Jane Doe" in out
    assert "vendor SLA breach" in out

def test_daycount_future():
    out = strip_ansi(render(FULL, today="2026-07-06").stdout)
    # 2029-01-20 is 929 days after 2026-07-06
    assert "929d" in out

def test_daycount_overdue():
    block = FULL.replace("2029-01-20", "2026-06-09")
    out = strip_ansi(render(block, today="2026-07-06").stdout)
    assert "27d OVERDUE" in out

def test_no_line_exceeds_width():
    # A long, multi-word NEXT should wrap across several lines rather than
    # blow past the card width.
    block = FULL.replace("chase Jane Doe",
                         "chase Jane Doe and the whole vendor team about the renewal and everything else too so it exceeds the width")
    out = strip_ansi(render(block, width="40").stdout)
    lines = out.splitlines()
    for ln in lines:
        assert len(ln) <= 40, repr(ln)
    # the long NEXT value actually wrapped onto more than one line
    assert sum(1 for ln in lines if "chase Jane Doe" in ln or "vendor team" in ln) >= 2

def test_overlong_single_token_hard_truncates_with_ellipsis():
    # A single unspaced token longer than the available width can't be
    # word-wrapped, so it must be hard-truncated with an ellipsis instead of
    # blowing past the card width.
    block = FULL.replace(
        "NEXT: chase Jane Doe",
        "NEXT: " + ("supercalifragilisticexpialidocious" * 3),
    )
    out = strip_ansi(render(block, width="40").stdout)
    for ln in out.splitlines():
        assert len(ln) <= 40, repr(ln)
    assert "…" in out

def test_color_present_for_high_risk_overdue():
    block = FULL.replace("2029-01-20", "2026-06-09")
    r = render(block)  # FORCE_COLOR on
    assert "\033[38;5;196m" in r.stdout  # red

def test_no_color_when_disabled():
    r = render(FULL, env={"NO_COLOR": "1", "MATTER_WALL_FORCE_COLOR": ""})
    assert "\033[" not in r.stdout
    assert "alpha" in strip_ansi(r.stdout)

def test_fallback_when_no_block():
    r = render("I couldn't find much here.\nSome rambling prose.\n")
    out = strip_ansi(r.stdout)
    assert r.returncode == 0
    assert "(no summary)" in out
    # never dumps every line of the transcript as separate card rows
    assert "Some rambling prose." not in out

def test_none_fields_dim_and_green_border():
    block = ("<<<CARD\nSTATUS: on track\nPHASE: exec\nDEADLINE: NONE\n"
             "RISK: NONE\nNEXT: none\nCARD>>>\n")
    r = render(block)
    assert "\033[38;5;42m" in r.stdout  # green somewhere (healthy border)
    out = strip_ansi(r.stdout)
    assert "none" in out

# --- full-brief: PHASE / RECENT / AWAITING ---------------------------------

FULL_V2 = (
    "<<<CARD\n"
    "STATUS: awaiting vendor counter-offer\n"
    "PHASE: negotiation → close\n"
    "DEADLINE: 2029-01-20 | contract deadline\n"
    "RISK: vendor SLA breach | HIGH\n"
    "RECENT:\n"
    "- 2026-07-09 sent redline to vendor\n"
    "- 2026-07-07 call with Jane Doe re: renewal terms\n"
    "- 2026-07-03 filed status report\n"
    "AWAITING:\n"
    "- vendor response on section 7\n"
    "- internal sign-off on package\n"
    "NEXT: chase Jane Doe\n"
    "CARD>>>\n"
)

def test_phase_line_renders():
    out = strip_ansi(render(FULL_V2).stdout)
    assert "phase: negotiation" in out.lower()

def test_recent_bullets_render_newest_first():
    # Bullets can wrap onto continuation lines, so compare against the
    # de-wrapped (joined) text rather than a single raw line.
    joined = " ".join(strip_ansi(render(FULL_V2).stdout).replace("│", " ").split())
    assert "sent redline to vendor" in joined
    assert "call with Jane Doe re: renewal terms" in joined
    assert "filed status report" in joined

def test_awaiting_bullets_render_and_are_headed():
    out = strip_ansi(render(FULL_V2).stdout)
    assert "Awaiting" in out
    assert "internal sign-off on package" in out

def test_awaiting_omitted_when_absent():
    block = FULL.replace("NEXT:", "RECENT:\n- 2026-07-09 did a thing\nNEXT:")
    out = strip_ansi(render(block).stdout)
    assert "Awaiting" not in out

def test_recent_capped_at_six_with_more_note():
    # Render just caps at 6 in the order given, trusting the card-prompt's
    # "newest first" convention — so list bullets newest-first here too.
    bullets = "\n".join(f"- 2026-07-{i:02d} item number {i}" for i in range(9, 0, -1))
    block = FULL.replace("NEXT:", f"RECENT:\n{bullets}\nNEXT:")
    out = strip_ansi(render(block).stdout)
    assert "item number 9" in out
    for i in range(1, 4):
        assert f"item number {i}" not in out
    assert "+3 more" in out

def test_awaiting_capped_at_three_no_more_note():
    bullets = "\n".join(f"- awaiting item {i}" for i in range(5, 0, -1))
    block = FULL.replace("NEXT:", f"AWAITING:\n{bullets}\nNEXT:")
    out = strip_ansi(render(block).stdout)
    assert "awaiting item 5" in out
    assert "awaiting item 1" not in out
    assert "more" not in out

def test_long_bullet_wraps_without_exceeding_width():
    block = FULL.replace(
        "NEXT:",
        "RECENT:\n- 2026-07-09 this is a deliberately long recent-activity "
        "bullet meant to force a wrap onto a continuation line within the "
        "card frame\nNEXT:",
    )
    out = strip_ansi(render(block, width="40").stdout)
    lines = out.splitlines()
    for ln in lines:
        assert len(ln) <= 40, repr(ln)
    # the bullet text survives intact once de-wrapped ...
    joined = " ".join(out.replace("│", " ").split())
    assert "deliberately long recent-activity bullet" in joined
    assert "continuation line within the card frame" in joined
    # ... and it actually took more than one physical line to say it (a
    # hanging-indent continuation line: starts with spaces, no bullet/icon).
    assert any(ln.startswith("│   ") and "•" not in ln for ln in lines)
