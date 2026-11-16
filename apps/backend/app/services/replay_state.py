"""
In-memory replay mode state for the HaritAyush demo backend.

Single-process demo: a module-level boolean is sufficient.
No persistence — replay mode resets to False on process restart.
"""

_replay_enabled: bool = False


def is_replay_enabled() -> bool:
    """Return True when replay mode is active."""
    return _replay_enabled


def enable_replay() -> None:
    """Switch to replay mode."""
    global _replay_enabled
    _replay_enabled = True


def disable_replay() -> None:
    """Switch back to live mode."""
    global _replay_enabled
    _replay_enabled = False

