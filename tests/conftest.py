import os
import textwrap

import pytest


@pytest.fixture
def project_tree(tmp_path):
    """A fake project root with <slug>/<marker> subdirs the test can touch."""

    def make(slug, *, has_context=True, marker="context.md", mtime=None):
        d = tmp_path / slug
        d.mkdir(parents=True, exist_ok=True)
        if has_context:
            f = d / marker
            f.write_text(f"# {slug}\n")
            if mtime is not None:
                os.utime(f, (mtime, mtime))
        return d

    return tmp_path, make


@pytest.fixture
def stub_bin(tmp_path):
    """A dir prepended to PATH holding fake `herdr`/`claude` that log their argv."""
    d = tmp_path / "stubbin"
    d.mkdir()
    log = tmp_path / "stub.log"
    for name in ("herdr", "claude"):
        p = d / name
        p.write_text(textwrap.dedent(f"""\
            #!/usr/bin/env bash
            echo "{name} $*" >> "{log}"
            # herdr status server must succeed; splits/create return minimal JSON
            case "$*" in
              "status server") echo "status: running";;
              *"tab create"*) echo '{{"result":{{"root_pane":{{"pane_id":"wX:pT"}},"tab":{{"tab_id":"wX:tT"}}}}}}';;
              *"tab list"*) echo '{{"result":{{"tabs":[{{"tab_id":"wX:t1"}}]}}}}';;
              *"tab rename"*) echo ok;;
              *"pane split"*|*"workspace create"*) echo '{{"result":{{"pane":{{"pane_id":"wX:pY"}},"root_pane":{{"pane_id":"wX:pY"}},"workspace":{{"workspace_id":"wX"}}}}}}';;
              *"workspace list"*) echo '{{"result":{{"workspaces":[]}}}}';;
            esac
        """))
        p.chmod(0o755)
    return d, log
