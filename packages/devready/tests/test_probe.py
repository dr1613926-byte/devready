import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from devready.probe import probe


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/missing":
            self.send_response(404)
        else:
            self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def _serve():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_probe_reports_http_status():
    srv = _serve()
    try:
        result = probe("http://127.0.0.1:%d/health" % srv.server_port, timeout=2)
        assert result["reachable"] is True
        assert result["status"] == 200
        assert result["phases_ms"]["dns"] >= 0
        assert result["phases_ms"]["http"] >= 0
    finally:
        srv.shutdown()


def test_probe_counts_error_status_as_reachable():
    srv = _serve()
    try:
        result = probe("http://127.0.0.1:%d/missing" % srv.server_port, timeout=2)
        assert result["reachable"] is True
        assert result["status"] == 404
    finally:
        srv.shutdown()


def test_probe_invalid_url():
    result = probe("not-a-url")
    assert result["reachable"] is False
    assert result["error"] == "invalid URL"


def test_probe_unreachable():
    result = probe("http://127.0.0.1:1/health", timeout=1)
    assert result["reachable"] is False
    assert result["error"]
