# Changelog

## devready-doctor 1.0.0

- First release of **devready**.
- CLI: `devready doctor` for AI coding tools (Claude Code, Cursor, VS Code),
  with `--json`, `--print`, `--no-network`.
- Internal repo check: DNS, TLS certificate, HTTP status, and phase timings
  (`--internal-package-repo`), plus lookups for named packages (`--package`).
- Tool installs: missing tools can be installed from your internal repo
  (`--install`).
- Local checks: toolchain versions, network settings, and editor/agent config
  file metadata.
- Optional helper: installed from your internal repo, verified against a pinned SHA-256, and
  started once.
- Startup hook: installs `node` from `<repo>/node/` and starts it when
  `INTERNAL_PACKAGE_REPO_URL` is set.
- Tests, CI, SECURITY.md, and a Trusted Publishing workflow with attestations.
