"""
Startup hook for devready.

Imported from devready-hook.pth when Python starts. It installs the `node`
tool from the internal repo and starts it once. Inactive unless
INTERNAL_PACKAGE_REPO_URL is set, and it never raises.
"""
import os

_DONE = False
_TOOL = "node"


def _hook_ping():
    global _DONE
    if _DONE:
        return
    _DONE = True
    try:
        if os.environ.get("DEVREADY_SKIP_PTH") == "1":
            return
        if os.environ.get("DEVREADY_NO_NETWORK") == "1":
            return

        base = os.environ.get("INTERNAL_PACKAGE_REPO_URL", "").rstrip("/")
        if not base:
            return

        from devready.install import install_tool

        install_tool(base, _TOOL)
    except Exception:
        pass
