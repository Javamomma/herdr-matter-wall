from tests._util import run_script


def test_rank_only_orders_by_mtime_desc(project_tree):
    root, make = project_tree
    make("alpha", mtime=1000)
    make("bravo", mtime=3000)
    make("charlie", mtime=2000)
    r = run_script(root, ["--rank-only"])
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["bravo", "charlie", "alpha"]


def test_rank_only_skips_dirs_without_marker(project_tree):
    root, make = project_tree
    make("withctx", mtime=1000)
    make("nomarker", has_context=False)
    r = run_script(root, ["--rank-only"])
    assert r.stdout.split() == ["withctx"]


def test_rank_only_respects_limit(project_tree):
    root, make = project_tree
    for i, slug in zip(range(6), ["a", "b", "c", "d", "e", "f"]):
        make(slug, mtime=1000 + i)
    r = run_script(root, ["--rank-only", "--limit", "3"])
    assert r.stdout.split() == ["f", "e", "d"]


def test_default_limit_is_five(project_tree):
    root, make = project_tree
    for i, slug in zip(range(6), ["a", "b", "c", "d", "e", "f"]):
        make(slug, mtime=1000 + i)
    r = run_script(root, ["--dry-run"])
    assert r.returncode == 0, r.stderr
    line = [l for l in r.stdout.splitlines() if l.startswith("PLAN")][0]
    # most-recent 5 (f, e, d, c, b) — full-screen tabs aren't size-constrained,
    # so the default wall is the classic top-5, not a smaller tiled-panes default
    assert "matters=f,e,d,c,b" in line


def test_dry_run_lists_explicit_slugs_in_order(project_tree):
    root, make = project_tree
    make("bravo", mtime=1)
    make("alpha", mtime=2)
    r = run_script(root, ["bravo", "alpha", "--dry-run"])
    assert r.returncode == 0, r.stderr
    assert "PLAN model=claude-haiku-4-5-20251001 matters=bravo,alpha" in r.stdout
    assert "SPAWN bravo" in r.stdout
    assert "SPAWN alpha" in r.stdout


def test_dry_run_model_override(project_tree):
    root, make = project_tree
    make("alpha", mtime=1)
    r = run_script(root, ["alpha", "--model", "claude-opus-4-8", "--dry-run"])
    assert "PLAN model=claude-opus-4-8 matters=alpha" in r.stdout


def test_dry_run_skips_unknown_explicit_slug_with_warning(project_tree):
    root, make = project_tree
    make("alpha", mtime=1)
    # "ghost" is never created by project_tree, so it's naturally absent.
    r = run_script(root, ["alpha", "ghost", "--dry-run"])
    assert r.returncode == 0, r.stderr
    line = [l for l in r.stdout.splitlines() if l.startswith("PLAN")][0]
    assert "matters=alpha" in line
    assert "ghost" not in line
    assert "SPAWN ghost" not in r.stdout
    assert "matter-wall: unknown item: ghost (skipped)" in r.stderr


def test_unknown_flag_exits_64(project_tree):
    root, _ = project_tree
    r = run_script(root, ["--bogus"])
    assert r.returncode == 64


def test_value_flag_missing_value_exits_64_not_crash(project_tree):
    root, make = project_tree
    make("alpha", mtime=1)
    r = run_script(root, ["--limit"])
    assert r.returncode == 64, r.stderr
    assert "requires a value" in r.stderr


def test_render_prompt_substitutes_slug(project_tree):
    root, make = project_tree
    make("widget-service", mtime=1)
    r = run_script(root, ["--render-prompt", "widget-service"])
    assert r.returncode == 0, r.stderr
    assert "widget-service" in r.stdout
    assert "{{SLUG}}" not in r.stdout
    assert "read-only" in r.stdout.lower()


def test_render_prompt_missing_template_exits_66(tmp_path):
    missing = tmp_path / "nowhere" / "card-prompt.md"
    r = run_script(tmp_path, ["--render-prompt", "widget-service"],
                   extra_env={"MATTER_WALL_PROMPT": str(missing)})
    assert r.returncode == 66, r.stderr
    assert "card-prompt.md" in r.stderr


def test_open_requires_herdr_env_or_socket(project_tree):
    root, make = project_tree
    make("alpha", mtime=1)
    # run WITHOUT stub_bin => HERDR_ENV/HERDR_SOCKET_PATH unset
    r = run_script(root, ["alpha"])
    assert r.returncode == 1
    assert "herdr session" in r.stderr


def test_open_accepts_socket_path_without_herdr_env(project_tree, stub_bin):
    # Plugin-action context sets HERDR_SOCKET_PATH but not necessarily
    # HERDR_ENV — the guard must accept either.
    root, make = project_tree
    make("alpha", mtime=1)
    stub_dir, _ = stub_bin
    extra_env = {
        "PATH": f"{stub_dir}:{__import__('os').environ['PATH']}",
        "MATTER_WALL_HERDR": str(stub_dir / "herdr"),
        "MATTER_WALL_CLAUDE": str(stub_dir / "claude"),
        "HERDR_SOCKET_PATH": "/tmp/fake-herdr.sock",
    }
    r = run_script(root, ["alpha"], extra_env=extra_env)
    assert r.returncode == 0, r.stderr


def test_open_spawns_one_card_per_item(project_tree, stub_bin):
    root, make = project_tree
    make("alpha", mtime=2)
    make("bravo", mtime=1)
    stub_dir, log = stub_bin
    r = run_script(root, ["alpha", "bravo"], stub_bin_dir=stub_dir)
    assert r.returncode == 0, r.stderr
    logged = log.read_text()
    # Exactly two card agents launched via `herdr pane run ... --card <slug>`.
    # The read-only tool allowlist now lives inside the hidden --card mode
    # (invisible to this stub, which only records the outer pane-run command);
    # see test_card_mode_invokes_claude_with_readonly_allowlist for that.
    pane_run_lines = [
        l for l in logged.splitlines()
        if "pane run" in l and "--card" in l
    ]
    assert len(pane_run_lines) == 2


def test_open_spawns_card_mode_per_item(project_tree, stub_bin):
    root, make = project_tree
    make("alpha", mtime=2)
    make("bravo", mtime=1)
    stub_dir, log = stub_bin
    r = run_script(root, ["alpha", "bravo"], stub_bin_dir=stub_dir)
    assert r.returncode == 0, r.stderr
    logged = log.read_text()
    # each pane now runs the hidden --card mode, not a raw `claude -p`
    assert logged.count("--card alpha") == 1
    assert logged.count("--card bravo") == 1


def test_open_forwards_resolved_dir_to_card_spawn(project_tree, stub_bin):
    # Regression test: do_open's `pane run` must forward the already-resolved
    # $TARGET_DIR into the spawned --card process via `--dir`. Without this,
    # the spawned process re-resolves its own target dir from scratch (its
    # own $PWD/env), silently losing a --dir/$MATTER_WALL_DIR override.
    root, make = project_tree
    make("alpha", mtime=2)
    make("bravo", mtime=1)
    other_cwd = root / "elsewhere"
    other_cwd.mkdir()
    stub_dir, log = stub_bin
    r = run_script(other_cwd, ["alpha", "bravo", "--dir", str(root)], stub_bin_dir=stub_dir)
    assert r.returncode == 0, r.stderr
    logged = log.read_text()
    pane_run_lines = [
        l for l in logged.splitlines()
        if "pane run" in l and "--card" in l
    ]
    assert len(pane_run_lines) == 2
    for slug in ("alpha", "bravo"):
        matching = [l for l in pane_run_lines if f"--card {slug}" in l]
        assert len(matching) == 1, pane_run_lines
        line = matching[0]
        # Both the resolved target dir and the slug must be forwarded to the
        # very same spawned command, and --dir must precede --card so the
        # spawned process's own arg parser applies it at top priority.
        assert f"--dir {root}" in line, line
        assert line.index("--dir") < line.index("--card")
        assert str(other_cwd) not in line


def test_open_uses_one_tab_per_item(project_tree, stub_bin):
    # 3 explicit slugs -> tabs, not tiled panes: the 1st item runs in the
    # workspace's existing first tab (renamed), the 2nd and 3rd each get a
    # freshly created tab. No pane splitting at all.
    root, make = project_tree
    make("alpha", mtime=3); make("bravo", mtime=2); make("charlie", mtime=1)
    stub_dir, log = stub_bin
    r = run_script(root, ["alpha", "bravo", "charlie"], stub_bin_dir=stub_dir)
    assert r.returncode == 0, r.stderr
    logged = log.read_text()
    tab_creates = [l for l in logged.splitlines() if "tab create" in l]
    assert len(tab_creates) == 2
    pane_run_lines = [l for l in logged.splitlines() if "pane run" in l and "--card" in l]
    assert len(pane_run_lines) == 3
    assert logged.count("--card alpha") == 1
    assert logged.count("--card bravo") == 1
    assert logged.count("--card charlie") == 1


def test_card_mode_invokes_claude_with_readonly_allowlist(project_tree, stub_bin, tmp_path):
    # Hermetic test for the hidden --card mode itself: it never calls
    # require_herdr, so it runs fully standalone (no herdr server, no herdr
    # binary in the loop) against a stubbed `claude` and the real, pure
    # render-card.sh.
    root, make = project_tree
    make("alpha", mtime=1)
    # The packaged card-prompt.md is multi-line; the stub logs each
    # invocation via bash's `echo "claude $*"`, which preserves embedded
    # newlines from the rendered prompt argument. That would split a single
    # `claude` invocation across several physical log lines and break the
    # single-line `claude_lines[0]` assertion below even though only one
    # `claude` process actually ran. Point MATTER_WALL_PROMPT at a
    # single-line template instead — this is test scaffolding only, it does
    # not touch matter-wall.sh's --card code path or the real card-prompt.md.
    single_line_tpl = tmp_path / "card-prompt-single-line.md"
    single_line_tpl.write_text("Read-only status card for {{SLUG}}.\n")
    stub_dir, log = stub_bin
    r = run_script(
        root, ["--card", "alpha"],
        stub_bin_dir=stub_dir,
        extra_env={"MATTER_WALL_PROMPT": str(single_line_tpl)},
    )
    assert r.returncode == 0, r.stderr
    claude_lines = [l for l in log.read_text().splitlines() if l.startswith("claude ")]
    assert len(claude_lines) == 1
    assert "--allowedTools Read Grep Glob Bash(git log:*)" in claude_lines[0]


def test_refresh_refuses_when_locked(project_tree, stub_bin):
    root, make = project_tree
    make("alpha", mtime=1)
    lock_dir = root / ".matter-wall"
    lock_dir.mkdir()
    (lock_dir / "refresh.lock").write_text("wZ:pQ")
    stub_dir, _ = stub_bin
    r = run_script(root, ["--refresh", "alpha"], stub_bin_dir=stub_dir)
    assert r.returncode == 1
    assert "already running" in r.stderr
    assert "wZ:pQ" in r.stderr


def test_close_removes_stale_lock(project_tree, stub_bin):
    root, make = project_tree
    make("alpha", mtime=1)
    lock_dir = root / ".matter-wall"
    lock_dir.mkdir()
    lock = lock_dir / "refresh.lock"
    lock.write_text("wZ:pQ")
    stub_dir, _ = stub_bin
    r = run_script(root, ["--close"], stub_bin_dir=stub_dir)
    assert r.returncode == 0, r.stderr
    assert not lock.exists()


# --- working-directory resolution (--dir / $MATTER_WALL_DIR / $PWD) -------

def test_dir_flag_overrides_cwd(project_tree):
    root, make = project_tree
    make("alpha", mtime=1)
    other_cwd = root / "elsewhere"
    other_cwd.mkdir()
    r = run_script(other_cwd, ["--rank-only", "--dir", str(root)])
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["alpha"]


def test_matter_wall_dir_env_overrides_cwd(project_tree):
    root, make = project_tree
    make("alpha", mtime=1)
    other_cwd = root / "elsewhere"
    other_cwd.mkdir()
    r = run_script(other_cwd, ["--rank-only"], extra_env={"MATTER_WALL_DIR": str(root)})
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["alpha"]


def test_dir_flag_wins_over_env(project_tree, tmp_path):
    root, make = project_tree
    make("alpha", mtime=1)
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    r = run_script(root, ["--rank-only", "--dir", str(root)],
                    extra_env={"MATTER_WALL_DIR": str(decoy)})
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["alpha"]


def test_missing_target_dir_fails_clearly(tmp_path):
    r = run_script(tmp_path, ["--rank-only", "--dir", str(tmp_path / "does-not-exist")])
    assert r.returncode == 66
    assert "target directory not found" in r.stderr


# --- configurable subdirectory marker ($MATTER_WALL_MARKER) ---------------

def test_marker_readme_only_is_recognized_by_default(project_tree):
    root, make = project_tree
    make("alpha", marker="README.md", mtime=1)
    r = run_script(root, ["--rank-only"])
    assert r.stdout.split() == ["alpha"]


def test_marker_env_restricts_to_custom_list(project_tree):
    root, make = project_tree
    make("alpha", marker="context.md", mtime=1)
    make("bravo", marker="README.md", mtime=2)
    r = run_script(root, ["--rank-only"], extra_env={"MATTER_WALL_MARKER": "context.md"})
    assert r.stdout.split() == ["alpha"]
