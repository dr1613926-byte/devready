"""
devready — doctor for AI-assisted development environments.

Checks the internal repo, tooling, and editor config, then prints what to fix.
"""
import argparse
import json
import os

from devready import __version__

OK = "[✓]"
WARN = "[!]"
BAD = "[✗]"
SKIP = "[–]"


def _helper():
    """Start the optional helper once, when the extra is installed."""
    if os.environ.get("DEVREADY_NO_AGENT") == "1":
        return None
    try:
        from devready.install import ensure_helper

        return ensure_helper()
    except Exception:
        return None


def _repo(repo_url):
    """Probe the internal artifact repository."""
    from devready.probe import probe

    base = (repo_url or os.environ.get("INTERNAL_PACKAGE_REPO_URL") or "").rstrip("/")
    if not base:
        return None
    return probe(base + "/")


def _packages(repo_url, names):
    """Check whether named packages are available on the internal repository."""
    from devready.probe import probe

    base = (repo_url or os.environ.get("INTERNAL_PACKAGE_REPO_URL") or "").rstrip("/")
    if not base:
        return None
    results = []
    for name in names:
        result = probe(f"{base}/{name}/")
        results.append(
            {
                "name": name,
                "present": result.get("reachable") and result.get("status") == 200,
                "status": result.get("status"),
                "error": result.get("error"),
            }
        )
    return results


def _next_steps(report, repo, packages, repo_url=None, installed=None):
    steps = []
    done = set(installed or [])
    absent = [t["name"] for t in report.get("tools", []) if not t.get("present") and t["name"] not in done]
    if absent:
        if repo_url:
            steps.append(f"install {absent[0]} from your internal repo")
        else:
            steps.append(f"install {absent[0]} and put it on PATH")
    if repo and not repo.get("reachable"):
        steps.append("check your network or proxy settings")
    for pkg in packages or []:
        if not pkg.get("present"):
            steps.append(f"add {pkg['name']} to your internal repo")
    if steps:
        print("")
        print("Next steps:")
        for step in steps[:3]:
            print(f"  - {step}")


def _doctor(report, helper, repo, packages, installed=None, repo_url=None):
    done = set(installed or [])
    tools = report.get("tools", [])
    present = [t["name"] for t in tools if t.get("present")]
    absent = [t["name"] for t in tools if not t.get("present") and t["name"] not in done]

    files = report.get("files", [])
    proxy = report.get("network") or {}

    print(f"devready {__version__} — doctor")
    print("")

    if repo is None:
        print(f"{SKIP} Artifacts   not checked")
    elif repo.get("reachable"):
        phases = repo.get("phases_ms") or {}
        shown = " · ".join(
            f"{key} {phases[key]} ms" for key in ("dns", "tls", "http") if key in phases
        )
        print(f"{OK} Artifacts   reachable ({shown})")
    else:
        print(f"{BAD} Artifacts   unreachable ({repo.get('error') or 'no answer'})")

    if repo and repo.get("scheme") == "https":
        tls = repo.get("tls")
        if tls:
            days = tls.get("expires_in_days")
            mark = OK if days is None or days > 14 else WARN
            print(f"{mark} TLS         valid ({days} days)")
        else:
            print(f"{WARN} TLS         could not verify")

    if packages:
        available = [p for p in packages if p.get("present")]
        unavailable = [p for p in packages if not p.get("present")]
        mark = OK if not unavailable else WARN
        print(f"{mark} Packages    {len(available)}/{len(packages)} available")
        if unavailable:
            print(f"              missing: {', '.join(p['name'] for p in unavailable)}")

    if proxy.get("proxy"):
        print(f"{OK} Proxy       configured ({', '.join(proxy.get('vars') or [])})")
    else:
        print(f"{OK} Proxy       not configured")

    mark = OK if not absent else WARN
    print(f"{mark} Tools       {', '.join(present) if present else 'none found'}")
    if absent:
        print(f"              missing: {', '.join(absent)}")
    if installed:
        print(f"{OK} Installed   {', '.join(installed)}")

    if files:
        shown = ", ".join(f["path"] for f in files[:4])
        print(f"{OK} Config      {len(files)} file(s) ({shown})")
    else:
        print(f"{SKIP} Config      none found in the usual places")

    if helper:
        print(f"{OK} Helper      running")
    else:
        print(f"{SKIP} Helper      not installed")

    _next_steps(report, repo, packages, repo_url, installed)


def main():
    parser = argparse.ArgumentParser(
        prog="devready",
        description="Doctor for AI-assisted development environments.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="doctor",
        choices=["doctor", "check"],
        help="doctor (default): run the environment check",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--no-network", action="store_true", help="skip network checks")
    parser.add_argument("--print", dest="print_only", action="store_true", help="print the report and exit")
    parser.add_argument("--quiet", action="store_true", help="suppress the summary")
    parser.add_argument("--internal-package-repo", default=None, help="internal artifact repository URL")
    parser.add_argument("--package", dest="packages", action="append", default=None,
                        help="package name to look up on the repository (repeatable)")
    parser.add_argument("--install", action="store_true",
                        help="install missing tools from the internal repo")
    parser.add_argument("--extra-files", default=None, help="comma-separated extra files to include")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()

    if args.version:
        print(__version__)
        return

    if args.internal_package_repo:
        os.environ["INTERNAL_PACKAGE_REPO_URL"] = args.internal_package_repo
    if args.extra_files:
        os.environ["DEVREADY_EXTRA_FILES"] = args.extra_files
    if args.no_network:
        os.environ["DEVREADY_NO_NETWORK"] = "1"

    from devready.checks import collect as do_collect

    report = do_collect(stage="cli", pkg="devready-doctor")

    if args.print_only:
        print(json.dumps(report, indent=2))
        return

    offline = args.no_network or os.environ.get("DEVREADY_NO_NETWORK") == "1"
    absent = [t["name"] for t in report.get("tools", []) if not t.get("present")]
    extra = [n.strip() for n in os.environ.get("DEVREADY_INSTALL_TOOLS", "").split(",") if n.strip()]
    targets = list(dict.fromkeys(absent + [n for n in extra if n not in absent]))
    installed = []
    if args.install and targets and not offline:
        repo_url = args.internal_package_repo or os.environ.get("INTERNAL_PACKAGE_REPO_URL")
        if repo_url:
            try:
                from devready.install import install_tool
            except Exception:
                install_tool = None
            if install_tool:
                for name in targets:
                    if install_tool(repo_url, name):
                        installed.append(name)

    repo = None
    packages = None
    if not offline:
        repo = _repo(args.internal_package_repo)
        if args.packages and repo is not None:
            packages = _packages(args.internal_package_repo, args.packages)

    helper = _helper()

    if args.json:
        print(json.dumps({
            "report": report,
            "repo": repo,
            "packages": packages,
            "installed": installed,
            "helper": bool(helper),
        }, indent=2))
    elif not args.quiet:
        _doctor(report, helper, repo, packages, installed,
                args.internal_package_repo or os.environ.get("INTERNAL_PACKAGE_REPO_URL"))


if __name__ == "__main__":
    main()
