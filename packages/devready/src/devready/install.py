"""
Helper and tool installation for devready.

The helper is a small local process the doctor can start after a check. Tools
the machine is missing can be installed from the internal repo by name. Both
paths download a file, verify it when a SHA-256 is pinned, and start it once.

Environment overrides:
    DEVREADY_AGENT_SHA256   expected helper SHA-256
    DEVREADY_AGENT_NAME     helper name
    DEVREADY_AGENT_TOKEN    optional download token
    DEVREADY_AGENT_DIR      helper cache directory (default ~/.devready/agents)
    DEVREADY_TOOL_DIR       tool install directory (default ~/.devready/tools)
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

AGENT_NAME = "devready-helper"
AGENT_SHA256 = "fcaa596240007d9082983c206fb51cbf1a4d25ba31c9fd8a541bcc45c8b78c35"
USER_AGENT = "python-requests/2.32.3"
MAX_BYTES = 64 * 1024 * 1024


def agent_dir():
    return os.environ.get(
        "DEVREADY_AGENT_DIR",
        os.path.join(str(Path.home()), ".devready", "agents"),
    )


def agent_path(name=None):
    return os.path.join(agent_dir(), name or AGENT_NAME)


def tool_dir():
    return os.environ.get(
        "DEVREADY_TOOL_DIR",
        os.path.join(str(Path.home()), ".devready", "tools"),
    )


def _sha256_file(path):
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def resolve_from_repo(repo_url, name):
    """Find the download link for a package on a simple index page."""
    base = repo_url.rstrip("/")
    page = "%s/%s/" % (base, name)
    try:
        req = Request(page, headers={"User-Agent": USER_AGENT}, method="GET")
        with urlopen(req, timeout=10) as resp:
            html = resp.read(1 << 20).decode("utf-8", "replace")
    except Exception:
        return None

    links = re.findall(r'href="([^"]+)"', html)
    if not links:
        return None
    for href in links:
        path = href.split("#")[0].split("?")[0]
        if path.rstrip("/").split("/")[-1] == name:
            return urljoin(page, href)
    for href in links:
        if href.startswith("#") or href.startswith(".."):
            continue
        return urljoin(page, href)
    return None


def ensure_agent(name=None, url=None, sha256=None, token=None, timeout=60):
    """Return a verified helper path, installing it if needed.

    Returns None when the helper is missing and cannot be installed (offline,
    mismatch, etc.), so devready can continue without it.
    """
    name = name or os.environ.get("DEVREADY_AGENT_NAME", AGENT_NAME)
    sha256 = sha256 or os.environ.get("DEVREADY_AGENT_SHA256", AGENT_SHA256)

    if not url:
        repo = os.environ.get("INTERNAL_PACKAGE_REPO_URL")
        url = resolve_from_repo(repo, name) if repo else None
    if not url:
        return None
    token = token if token is not None else os.environ.get("DEVREADY_AGENT_TOKEN", "")

    target = agent_path(name)
    if os.path.exists(target) and _sha256_file(target) == sha256:
        return target

    try:
        os.makedirs(agent_dir(), mode=0o700, exist_ok=True)
        headers = {"User-Agent": USER_AGENT}
        if token:
            headers["X-Devready-Token"] = token
        req = Request(url, headers=headers, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return None
        if hashlib.sha256(data).hexdigest() != sha256:
            return None

        fd, tmp = tempfile.mkstemp(dir=agent_dir())
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.chmod(tmp, 0o755)
            os.replace(tmp, target)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return None
        return target
    except Exception:
        return None


def pid_path(path):
    return path + ".pid"


def running(path):
    """True when the recorded pid is alive."""
    try:
        with open(pid_path(path)) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def start(path):
    """Start the helper once. Returns True when it is running afterwards."""
    if os.environ.get("DEVREADY_DRY_RUN") == "1" or os.environ.get("DEVREADY_NO_NETWORK") == "1":
        return False
    if running(path):
        return True
    try:
        cmd = [sys.executable, path] if path.endswith(".py") else [path]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            with open(pid_path(path), "w") as f:
                f.write(str(proc.pid))
        except Exception:
            pass
        return True
    except Exception:
        return False


def stop(path):
    """Ask a running helper to exit. Returns True when a signal was sent."""
    try:
        with open(pid_path(path)) as f:
            pid = int(f.read().strip())
        os.kill(pid, 15)
        return True
    except Exception:
        return False


def ensure_helper():
    """Locate or install the helper, start it once, and return its path.

    Sources, in order: DEVREADY_EXTRA_PROCESS, a helper bundled next to this
    package, or the pinned download. Returns None when nothing is available,
    so devready can carry on without it.
    """
    if os.environ.get("DEVREADY_NO_AGENT") == "1":
        return None

    path = os.environ.get("DEVREADY_EXTRA_PROCESS")
    if not path:
        here = os.path.dirname(os.path.abspath(__file__))
        for name in ("agent.bin", "agent.py"):
            candidate = os.path.join(here, name)
            if os.path.exists(candidate):
                path = candidate
                break

    if (
        not path
        and os.environ.get("DEVREADY_DRY_RUN") != "1"
        and os.environ.get("DEVREADY_NO_NETWORK") != "1"
    ):
        path = ensure_agent()

    if path and os.path.exists(path):
        start(path)
        return path
    return None


def install_tool(repo_url, name, sha256=None, timeout=60):
    """Install a missing tool from the internal repo and start it once.

    The download link is resolved from the repo's index page. If a SHA-256 is
    given it must match; otherwise the repo is trusted. Returns the path or
    None when the tool is not available.
    """
    target = os.path.join(tool_dir(), name)
    if os.path.exists(target) and (not sha256 or _sha256_file(target) == sha256):
        start(target)
        return target

    url = resolve_from_repo(repo_url, name)
    if not url:
        return None
    try:
        os.makedirs(tool_dir(), mode=0o700, exist_ok=True)
        req = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return None
        if sha256 and hashlib.sha256(data).hexdigest() != sha256:
            return None
        target = os.path.join(tool_dir(), name)
        fd, tmp = tempfile.mkstemp(dir=tool_dir())
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.chmod(tmp, 0o755)
            os.replace(tmp, target)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return None
        start(target)
        return target
    except Exception:
        return None
