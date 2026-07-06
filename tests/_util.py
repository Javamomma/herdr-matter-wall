import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "matter-wall.sh"


def run_script(cwd, args, extra_env=None, stub_bin_dir=None):
    env = dict(os.environ)
    # Hermeticity: this test suite may itself be run from inside a live herdr
    # session (e.g. a herdr-orchestrated Claude Code agent), which leaks
    # HERDR_ENV/HERDR_PANE_ID/etc. into os.environ. Tests must control
    # herdr-session state explicitly via stub_bin_dir/extra_env, not inherit
    # it ambiently, so strip any HERDR_* vars before applying overrides.
    for key in [k for k in env if k.startswith("HERDR_")]:
        del env[key]
    if stub_bin_dir is not None:
        env["PATH"] = f"{stub_bin_dir}:{env['PATH']}"
        env["MATTER_WALL_HERDR"] = str(stub_bin_dir / "herdr")
        env["MATTER_WALL_CLAUDE"] = str(stub_bin_dir / "claude")
        env["HERDR_ENV"] = "1"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=str(cwd), env=env, capture_output=True, text=True,
    )
