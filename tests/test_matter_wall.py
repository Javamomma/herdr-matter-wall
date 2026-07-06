import pytest

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


@pytest.mark.parametrize("n,expected", [
    (1, "1 1"), (2, "2 1"), (3, "2 2"), (4, "2 2"),
    (5, "3 2"), (6, "3 2"), (7, "3 3"), (8, "3 3"), (9, "3 3"),
])
def test_grid_dims(project_tree, n, expected):
    root, _ = project_tree
    r = run_script(root, ["--grid-dims", str(n)])
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == expected


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
    # Exactly two card agents launched via `herdr pane run ... claude -p ...`.
    pane_run_lines = [
        l for l in logged.splitlines()
        if "pane run" in l and "claude -p" in l
    ]
    assert len(pane_run_lines) == 2

    # The read-only tool allowlist is the feature's core safety invariant:
    # every spawned card must carry it verbatim, with no write-capable tools.
    allowlist = "Read Grep Glob Bash(git log:*)"
    for line in pane_run_lines:
        assert allowlist in line


def test_open_multi_row_tiles_down_and_spawns_all(project_tree, stub_bin):
    # 5 explicit slugs -> cols=ceil(sqrt(5))=3, rows=ceil(5/3)=2, so the
    # down-split (multi-row) branch of the tiler must run at least once.
    root, make = project_tree
    for i, slug in zip(range(5), ["alpha", "bravo", "charlie", "delta", "echo"]):
        make(slug, mtime=i)
    stub_dir, log = stub_bin
    r = run_script(
        root,
        ["alpha", "bravo", "charlie", "delta", "echo"],
        stub_bin_dir=stub_dir,
    )
    assert r.returncode == 0, r.stderr
    logged = log.read_text()
    down_splits = [
        l for l in logged.splitlines()
        if "pane split" in l and "--direction down" in l
    ]
    assert len(down_splits) >= 1
    pane_run_lines = [
        l for l in logged.splitlines()
        if "pane run" in l and "claude -p" in l
    ]
    assert len(pane_run_lines) == 5


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
