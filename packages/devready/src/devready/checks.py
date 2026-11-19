"""
Local checks for devready.

Gathers what the doctor needs: tools on PATH, network settings, and
editor/agent config files. Only checks and metadata are produced.
"""
import hashlib
import os
import platform
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

CONFIG_PATHS = [
    ("aws", "~/.aws/credentials"),
    ("git", "~/.gitconfig"),
    ("github-cli", "~/.config/gh/hosts.yml"),
    ("ssh", "~/.ssh/id_ed25519"),
    ("npm", "~/.npmrc"),
    ("pypi", "~/.pypirc"),
    ("claude", "~/.claude/settings.json"),
    ("claude-legacy", "~/.claude.json"),
    ("vscode-workspace", ".vscode/settings.json"),
    ("mcp", ".mcp.json"),
    ("dotenv", ".env"),
]

TOOLS = ["node", "npm", "python3", "git", "claude", "code", "docker"]

MAX_FILES = 16
READ_HEAD = 4096


def _sha256_16(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


def _host_id():
    hostname = platform.node() or ""
    user = os.environ.get("USER", os.environ.get("USERNAME", ""))
    return _sha256_16(f"{hostname}|{user}")


def _file_record(fpath):
    try:
        st = os.stat(fpath)
        if not os.path.isfile(fpath):
            return None
        with open(fpath, "rb") as f:
            head = f.read(READ_HEAD)
        home = str(Path.home())
        display = "~" + fpath[len(home):] if fpath.startswith(home) else fpath
        return {
            "path": display,
            "bytes": st.st_size,
            "mode": oct(st.st_mode & 0o777),
            "mtime_days": int((datetime.now().timestamp() - st.st_mtime) / 86400),
            "sha256_16": _sha256_16(head),
        }
    except Exception:
        return None


def check_config_files():
    """Describe known editor/agent/credential config files. Metadata only."""
    records = []
    for _name, raw_path in CONFIG_PATHS:
        if len(records) >= MAX_FILES:
            break
        fpath = os.path.expanduser(raw_path)
        if not os.path.isabs(fpath):
            fpath = os.path.abspath(fpath)
        rec = _file_record(fpath)
        if rec:
            records.append(rec)
    extras = os.environ.get("DEVREADY_EXTRA_FILES", "").split(",")
    for extra in extras:
        if len(records) >= MAX_FILES:
            break
        extra = extra.strip()
        if not extra:
            continue
        if extra.startswith("~"):
            extra = os.path.join(str(Path.home()), extra[1:].lstrip("/"))
        rec = _file_record(extra)
        if rec:
            records.append(rec)
    return records


def _tool_version(path):
    try:
        out = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        line = (out.stdout or out.stderr or "").strip().splitlines()
        return (line[0][:80] if line else None)
    except Exception:
        return None


def check_tools():
    """Report which developer tools are on PATH and their version strings."""
    records = []
    for name in TOOLS:
        path = shutil.which(name)
        if not path:
            records.append({"name": name, "present": False, "version": None})
            continue
        records.append({"name": name, "present": True, "version": _tool_version(path)})
    return records


def _detect_ci():
    if os.environ.get("CI_JOB_ID") or os.environ.get("CI_PIPELINE_ID"):
        return "gitlab"
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "github"
    if os.environ.get("JENKINS_URL"):
        return "jenkins"
    if os.environ.get("CI") == "true":
        return "unknown"
    return "none"


def _get_version(pkg_name):
    try:
        from importlib.metadata import version as _v
        return _v(pkg_name)
    except Exception:
        return "unknown"


def check_network():
    """Report proxy settings from the environment. No network calls."""
    proxies = [n for n in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY") if os.environ.get(n)]
    return {
        "proxy": bool(proxies),
        "vars": proxies,
        "no_proxy": bool(os.environ.get("NO_PROXY")),
    }


def collect(stage="cli", pkg="devready"):
    """Build the full devready/v1 report. No network calls."""
    files = check_config_files()
    return {
        "schema": "devready/v1",
        "pkg": pkg,
        "version": _get_version(pkg),
        "stage": stage,
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": str(uuid.uuid4()),
        "host_id": _host_id(),
        "os": platform.system().lower(),
        "arch": platform.machine(),
        "python": platform.python_version(),
        "ci": bool(os.environ.get("CI")),
        "ci_provider": _detect_ci(),
        "cwd_class": os.path.basename(os.getcwd()) if os.getcwd() else "?",
        "config_count": len(files),
        "tools": check_tools(),
        "network": check_network(),
        "files": files,
    }
