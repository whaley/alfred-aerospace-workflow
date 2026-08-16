"""Runtime configuration.

Every value is read from the environment so that Alfred *Workflow Variables*
(which Alfred exports as environment variables before running a script) can
override defaults without touching code.
"""

from __future__ import annotations

import os

# Alfred runs scripts with a minimal PATH that usually does NOT include
# /opt/homebrew/bin, so we cannot rely on `aerospace` being on PATH.
# These are searched in order after $AEROSPACE_BIN and shutil.which().
FALLBACK_BINARY_PATHS = (
    "/opt/homebrew/bin/aerospace",
    "/usr/local/bin/aerospace",
    "/run/current-system/sw/bin/aerospace",
    os.path.expanduser("~/.local/bin/aerospace"),
    "/Applications/AeroSpace.app/Contents/Resources/aerospace",
)

# Workspace names derived from window titles are truncated to this many
# characters (on a word boundary where possible).
DEFAULT_MAX_NAME_LENGTH = 40

# How to turn a window title into a workspace name.
#   full          -> use the whole title            (default, most predictable)
#   first-segment -> text before the first  - / — / | / :  separator
#   last-segment  -> text after  the last   - / — / | / :  separator
DEFAULT_TITLE_STRATEGY = "full"

VALID_TITLE_STRATEGIES = ("full", "first-segment", "last-segment")


def _env(name, default=""):
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_bool(name, default=False):
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _env_int(name, default):
    raw = _env(name)
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def aerospace_binary_override():
    """Explicit binary path from the AEROSPACE_BIN workflow variable."""
    return _env("AEROSPACE_BIN")


def max_name_length():
    return _env_int("AEROALFRED_MAX_NAME_LENGTH", DEFAULT_MAX_NAME_LENGTH)


def title_strategy():
    value = _env("AEROALFRED_TITLE_STRATEGY", DEFAULT_TITLE_STRATEGY).lower()
    return value if value in VALID_TITLE_STRATEGIES else DEFAULT_TITLE_STRATEGY


def follow_window_on_create():
    """When creating a workspace from a window, also focus that workspace."""
    return _env_bool("AEROALFRED_FOLLOW_WINDOW", True)


def show_empty_workspaces():
    """Include configured-but-empty workspaces in the `ws` list."""
    return _env_bool("AEROALFRED_SHOW_EMPTY", True)
