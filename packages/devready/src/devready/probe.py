"""
Connectivity checks for a URL: DNS, TLS, HTTP, and phase timings.
"""
import os
import socket
import ssl
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 2.0
USER_AGENT = "python-requests/2.32.3"


def _cert_info(sock):
    try:
        cert = sock.getpeercert()
        if not cert:
            return None
        expires = ssl.cert_time_to_seconds(cert.get("notAfter", ""))
        issuer = None
        for rdn in cert.get("issuer", ()):
            for key, value in rdn:
                if key == "organizationName":
                    issuer = value
        return {
            "issuer": issuer,
            "expires_in_days": int((expires - time.time()) // 86400),
        }
    except Exception:
        return None


def _tls_probe(host, port, timeout, insecure):
    started = time.perf_counter()
    try:
        ctx = ssl._create_unverified_context() if insecure else ssl.create_default_context()
        with socket.create_connection((host, port), timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as ssock:
                info = _cert_info(ssock)
        return info, round((time.perf_counter() - started) * 1000)
    except Exception:
        return None, round((time.perf_counter() - started) * 1000)


def probe(url, timeout=None, insecure=None):
    """Check a URL and report phase timings, HTTP status, and certificate details.

    Any HTTP answer counts as reachable, including 401 and 404, so a service
    that needs a token still reports its status instead of looking offline.
    """
    timeout = float(timeout or DEFAULT_TIMEOUT)
    if insecure is None:
        insecure = os.environ.get("DEVREADY_INSECURE") == "1"

    parts = urlsplit(url)
    result = {
        "url": url,
        "scheme": parts.scheme,
        "host": parts.hostname,
        "port": parts.port,
        "reachable": False,
        "status": None,
        "phases_ms": {},
        "tls": None,
        "error": None,
    }

    if parts.scheme not in ("http", "https") or not parts.hostname:
        result["error"] = "invalid URL"
        return result

    port = parts.port or (443 if parts.scheme == "https" else 80)
    result["port"] = port

    started = time.perf_counter()
    try:
        socket.getaddrinfo(parts.hostname, port, proto=socket.IPPROTO_TCP)
        result["phases_ms"]["dns"] = round((time.perf_counter() - started) * 1000)
    except Exception as e:
        result["phases_ms"]["dns"] = round((time.perf_counter() - started) * 1000)
        result["error"] = "dns: %s" % e
        return result

    if parts.scheme == "https":
        info, ms = _tls_probe(parts.hostname, port, timeout, insecure)
        result["tls"] = info
        result["phases_ms"]["tls"] = ms

    started = time.perf_counter()
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
        kwargs = {"timeout": timeout}
        if parts.scheme == "https":
            kwargs["context"] = (
                ssl._create_unverified_context() if insecure else ssl.create_default_context()
            )
        with urlopen(req, **kwargs) as resp:
            result["status"] = resp.status
            result["reachable"] = True
    except HTTPError as e:
        result["status"] = e.code
        result["reachable"] = True
    except Exception as e:
        result["error"] = str(e)[:160]
    result["phases_ms"]["http"] = round((time.perf_counter() - started) * 1000)
    result["phases_ms"]["total"] = sum(result["phases_ms"].values())
    return result
