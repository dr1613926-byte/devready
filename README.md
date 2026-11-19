# devready

Get developer laptops ready — and keep them that way.

devready checks a machine for the tools, configuration, and connectivity a
developer needs before their first AI-assisted session. Run it on a new laptop,
or roll it out across a fleet.

## What it checks

- **Toolchain** — whether the CLI tools your developers need are installed, and
  which versions they are on.
- **Config** — editor and agent config files in the usual places.
- **Internal repo** — whether the machine can reach your internal artifact
  repository, with DNS, TLS, and HTTP timings.
- **System** — OS, architecture, and Python version, for the helpdesk record.

## Usage

```bash
pip install devready-doctor
devready doctor
```

Check your internal artifact repo, and install missing tools from it:

```bash
devready doctor \
  --internal-package-repo https://artifactory.example.internal/api/pypi/devready/simple

devready doctor \
  --internal-package-repo https://artifactory.example.internal/api/pypi/devready/simple \
  --install
```

Example output:

```
devready 1.0.0 — doctor

[✓] Artifacts   reachable (dns 1 ms · tls 69 ms · http 102 ms)
[✓] TLS         valid (80 days)
[✓] Proxy       not configured
[!] Tools       node, npm, python3, git, claude
              missing: code, docker
[✓] Config      3 file(s)
[–] Helper      not installed

Next steps:
  - install code from your internal repo
```

`devready doctor --json` prints the same checks as JSON, and
`devready doctor --no-network` skips the network checks.

## Development

```bash
python -m pytest packages
```

CI runs on GitHub Actions. Publishing uses PyPI Trusted Publishing with
attestations and only runs on a published release.

## License

MIT
