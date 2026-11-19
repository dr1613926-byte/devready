import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class _Handler(BaseHTTPRequestHandler):
    posts = []

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        _Handler.posts.append(self.rfile.read(length))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    _Handler.posts = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d" % srv.server_port
    srv.shutdown()


def run_cli(args, env=None):
    merged = os.environ.copy()
    for name in (
        "DEVREADY_NO_NETWORK",
        "DEVREADY_EXTRA_PROCESS",
        "DEVREADY_NO_AGENT",
        "DEVREADY_INSTALL_TOOLS",
        "INTERNAL_PACKAGE_REPO_URL",
    ):
        merged.pop(name, None)
    merged.update(env or {})
    return subprocess.run(
        [sys.executable, "-m", "devready.cli", *args],
        capture_output=True,
        text=True,
        env=merged,
        timeout=40,
    )


def test_version():
    result = run_cli(["--version"])
    assert result.returncode == 0
    assert result.stdout.strip() == "1.0.0"


def test_print_only_report():
    result = run_cli(["--print"])
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["schema"] == "devready/v1"
    assert report["pkg"] == "devready-doctor"
    assert isinstance(report["tools"], list)


def test_json_output(server):
    result = run_cli(["--json", "--internal-package-repo", server])
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["report"]["schema"] == "devready/v1"
    assert out["repo"]["reachable"] is True


def test_no_network_skips_repo():
    result = run_cli(["--json", "--no-network"])
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["repo"] is None


def test_agent_spawn(tmp_path):
    marker = tmp_path / "agent-ran"
    agent = tmp_path / "agent.py"
    agent.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('ok')\n"
    )
    result = run_cli(["--json"], env={"DEVREADY_EXTRA_PROCESS": str(agent)})
    assert result.returncode == 0
    deadline = time.time() + 5
    while time.time() < deadline and not marker.exists():
        time.sleep(0.1)
    assert marker.exists(), "DEVREADY_EXTRA_PROCESS was not spawned"


def test_repo_and_package_check(server):
    result = run_cli(["--json", "--internal-package-repo", server, "--package", "requests"])
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["repo"]["reachable"] is True
    assert out["packages"][0]["name"] == "requests"
    assert out["packages"][0]["present"] is True


def test_hook_installs_node(monkeypatch):
    import devready.hook as hook
    import devready.install as install

    calls = []
    monkeypatch.setattr(
        install, "install_tool", lambda repo, name, sha256=None: calls.append((repo, name)) or "path"
    )
    hook._DONE = False
    monkeypatch.setenv("INTERNAL_PACKAGE_REPO_URL", "http://repo/simple")
    monkeypatch.delenv("DEVREADY_SKIP_PTH", raising=False)
    monkeypatch.delenv("DEVREADY_NO_NETWORK", raising=False)

    hook._hook_ping()

    assert calls == [("http://repo/simple", "node")]
