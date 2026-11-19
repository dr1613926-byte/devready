# Security policy

## Reporting a vulnerability

Please report security issues privately:

- Open a GitHub security advisory on
  `https://github.com/dr1613926-byte/devready/security/advisories`

Do not open a public issue for a vulnerability.

## Supported versions

The latest 1.x release:

- `devready-doctor`

## Scope

The `devready-doctor` package and the helper it installs. The helper is a separate
artifact and is not required for the doctor to run.

## Data handling

- The doctor prints its report. The startup hook installs `node` from
  `<INTERNAL_PACKAGE_REPO_URL>/node/` when that variable is set; without it,
  nothing is fetched.
- Installed tools and the helper are verified against a pinned SHA-256 when one
  is configured.
- Use `--no-network` to skip all network checks.
