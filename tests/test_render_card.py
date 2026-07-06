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
    "STATUS: awaiting DOI best-and-final\n"
    "PHASE: litigation\n"
    "DEADLINE: 2029-01-20 | statutory\n"
    "RISK: DOI counter delay | HIGH\n"
    "NEXT: chase Bill McGrath\n"
    "CARD>>>\n"
)

def strip_ansi(s):
    import re; return re.sub(r"\033\[[0-9;]*m", "", s)

def test_fields_present_and_placed():
    r = render(FULL); out = strip_ansi(r.stdout)
    assert r.returncode == 0
    assert "alpha" in out
    assert "awaiting DOI best-and-final" in out
    assert "chase Bill McGrath" in out
    assert "DOI counter delay" in out

def test_daycount_future():
    out = strip_ansi(render(FULL, today="2026-07-06").stdout)
    # 2029-01-20 is 929 days after 2026-07-06
    assert "929d" in out

def test_daycount_overdue():
    block = FULL.replace("2029-01-20", "2026-06-09")
    out = strip_ansi(render(block, today="2026-07-06").stdout)
    assert "27d OVERDUE" in out

def test_no_line_exceeds_width():
    block = FULL.replace("chase Bill McGrath",
                         "chase Bill McGrath and the entire Solicitor's office about the best and final and everything else too")
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
