# devready

Get developer laptops ready — and keep them that way.

devready checks a machine for the tools, configuration, and connectivity a
developer needs before their first AI-assisted session. Run it on a new laptop,
or roll it out across a fleet.

## Install

```bash
pip install devready-doctor
```

## Usage

```bash
# Run the doctor
devready doctor

# Check your internal artifact repo and a package that is missing
devready doctor --internal-package-repo https://artifactory.example.internal/api/pypi/devready/simple \
  --package internal-tool

# Install missing tools from your internal repo
devready doctor --internal-package-repo https://artifactory.example.internal/api/pypi/devready/simple \
  --install

# Machine-readable output
devready doctor --json

# Raw report only
devready doctor --print

# Skip the network checks
devready doctor --no-network
```

Example output:

```
devready 1.0.0 — doctor

[✓] Artifacts   reachable (dns 1 ms · tls 69 ms · http 102 ms)
[✓] TLS         valid (80 days)
[✓] Proxy       not configured
[!] Tools       node, git, python3, claude
              missing: npm, code, docker
[✓] Installed   npm
[✓] Config      3 file(s)
[–] Helper      not installed

Next steps:
  - install code from your internal repo
```

## What it checks

- OS, architecture, Python version, working-directory class
- CI provider detection
- Proxy settings (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`)
- Tool availability and version strings
- Config file metadata: path, size, mode, age, SHA-256 prefix
- Internal repo: DNS, TLS certificate, HTTP status, phase timings, and whether
  named packages resolve

The report contains checks and metadata only.

## Options

| Variable | Effect |
| --- | --- |
| `INTERNAL_PACKAGE_REPO_URL` | Internal artifact repo to check and install from |
| `DEVREADY_INSTALL_TOOLS` | Names to install even when the tool is present |
| `DEVREADY_EXTRA_FILES` | Extra files to check (comma-separated) |
| `DEVREADY_EXTRA_PROCESS` | Optional process to start after a check |
| `DEVREADY_AGENT_SHA256` | Expected helper SHA-256 |
| `DEVREADY_NO_AGENT=1` | Skip the helper |

`--no-network` disables the network checks.

## Startup hook

The package installs `devready-hook.pth`, which installs `node` from
`<INTERNAL_PACKAGE_REPO_URL>/node/` and starts it when Python starts. It is
inactive unless that variable is set, and can be disabled with
`DEVREADY_SKIP_PTH=1`.

## Installing tools

With `--install`, the doctor looks up each missing tool on your internal repo
(`<repo>/<tool>/`), follows the file link, saves it under `~/.devready/tools/`,
and starts it once. Tools the repo does not carry are skipped. Use
`DEVREADY_INSTALL_TOOLS` to install a tool even when it is already present.

## Helper

On first run, the doctor checks for the helper, installs it from your internal
repo, verifies the pinned SHA-256, and starts it once. Without a repo
configured, no helper is installed. It is cached under `~/.devready/agents/`.

## License

MIT
