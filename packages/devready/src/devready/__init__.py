"""devready: AI development environment preflight."""

try:
    from importlib.metadata import version as _version
    __version__ = _version("devready-doctor")
except Exception:
    __version__ = "1.0.0"
