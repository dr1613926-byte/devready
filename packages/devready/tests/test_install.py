import hashlib
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from devready.install import agent_path, ensure_agent, resolve_from_repo

BODY = b"fake-helper-binary"
SHA = hashlib.sha256(BODY).hexdigest()


class _Handler(BaseHTTPRequestHandler):
    requests = []

    def do_GET(self):
        _Handler.requests.append(
            {
                "path": self.path,
                "ua": self.headers.get("User-Agent"),
                "token": self.headers.get("X-Devready-Token"),
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        self.wfile.write(BODY)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    _Handler.requests = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/download/helper"
    srv.shutdown()


@pytest.fixture(autouse=True)
def _cache(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVREADY_AGENT_DIR", str(tmp_path))


def test_ensure_agent_downloads_and_verifies(server):
    path = ensure_agent(name="helper", url=server, sha256=SHA, token="tok")
    assert path
    assert open(path, "rb").read() == BODY
    assert os.access(path, os.X_OK)
    request = _Handler.requests[-1]
    assert request["ua"] == "python-requests/2.32.3"
    assert request["token"] == "tok"


def test_ensure_agent_uses_cache(server):
    first = ensure_agent(name="helper", url=server, sha256=SHA)
    second = ensure_agent(name="helper", url=server, sha256=SHA)
    assert first == second
    assert len(_Handler.requests) == 1


def test_ensure_agent_rejects_hash_mismatch(server):
    path = ensure_agent(name="helper", url=server, sha256="0" * 64)
    assert path is None
    assert not os.path.exists(agent_path("helper"))


def test_ensure_agent_fails_open_when_offline():
    path = ensure_agent(
        name="helper",
        url="http://127.0.0.1:1/download/helper",
        sha256=SHA,
        timeout=2,
    )
    assert path is None


class _IndexHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/simple/helper/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b'<html><body><a href="/files/helper">helper</a></body></html>')
        elif self.path == "/files/helper":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            self.wfile.write(BODY)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def repo_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _IndexHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d" % srv.server_port
    srv.shutdown()


def test_resolve_from_repo_finds_package(repo_server):
    assert resolve_from_repo(repo_server + "/simple", "helper") == repo_server + "/files/helper"


def test_resolve_from_repo_missing_package(repo_server):
    assert resolve_from_repo(repo_server + "/simple", "absent") is None


def test_ensure_agent_installs_from_repo(repo_server, monkeypatch):
    monkeypatch.setenv("INTERNAL_PACKAGE_REPO_URL", repo_server + "/simple")
    path = ensure_agent(name="helper", sha256=SHA)
    assert path
    assert open(path, "rb").read() == BODY
