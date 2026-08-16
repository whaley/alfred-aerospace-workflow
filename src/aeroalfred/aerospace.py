"""Thin, typed wrapper around the `aerospace` CLI.

Design notes
------------
* Every read uses ``--format ... --json``. AeroSpace honours both flags at once
  and returns a keyed JSON array with native types (ints stay ints, booleans
  stay booleans), which is far more robust than parsing delimited text.
* Every command that accepts a workspace name passes ``--`` first. Without it a
  workspace literally named ``next`` or ``prev`` would be parsed as the
  relative-motion subcommand instead of a name.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from . import config
from .errors import AerospaceCommandError, AerospaceNotFound

# Fields requested when listing workspaces / windows.
_WORKSPACE_FIELDS = (
    "%{workspace}"
    "%{workspace-is-focused}"
    "%{workspace-is-visible}"
    "%{monitor-id}"
    "%{monitor-name}"
)

_WINDOW_FIELDS = (
    "%{window-id}"
    "%{window-title}"
    "%{workspace}"
    "%{app-name}"
    "%{app-bundle-path}"
)


class Workspace(object):
    """A single AeroSpace workspace plus the windows currently on it."""

    __slots__ = ("name", "is_focused", "is_visible", "monitor_id",
                 "monitor_name", "window_count")

    def __init__(self, name, is_focused=False, is_visible=False,
                 monitor_id=None, monitor_name="", window_count=0):
        self.name = name
        self.is_focused = bool(is_focused)
        self.is_visible = bool(is_visible)
        self.monitor_id = monitor_id
        self.monitor_name = monitor_name or ""
        self.window_count = int(window_count)

    @classmethod
    def from_json(cls, payload):
        return cls(
            name=payload.get("workspace", ""),
            is_focused=payload.get("workspace-is-focused", False),
            is_visible=payload.get("workspace-is-visible", False),
            monitor_id=payload.get("monitor-id"),
            monitor_name=payload.get("monitor-name", ""),
        )

    def __repr__(self):  # pragma: no cover - debugging helper
        return "<Workspace {0!r} focused={1} windows={2}>".format(
            self.name, self.is_focused, self.window_count
        )


class Window(object):
    """A single managed window."""

    __slots__ = ("window_id", "title", "workspace", "app_name", "app_bundle_path")

    def __init__(self, window_id, title="", workspace="", app_name="",
                 app_bundle_path=""):
        self.window_id = int(window_id)
        self.title = title or ""
        self.workspace = workspace or ""
        self.app_name = app_name or ""
        self.app_bundle_path = app_bundle_path or ""

    @classmethod
    def from_json(cls, payload):
        return cls(
            window_id=payload.get("window-id", 0),
            title=payload.get("window-title", ""),
            workspace=payload.get("workspace", ""),
            app_name=payload.get("app-name", ""),
            app_bundle_path=payload.get("app-bundle-path", ""),
        )

    @property
    def display_title(self):
        """Window title, falling back to the app name for untitled windows."""
        return self.title.strip() or self.app_name

    def __repr__(self):  # pragma: no cover - debugging helper
        return "<Window {0} {1!r} ({2})>".format(
            self.window_id, self.title, self.app_name
        )


class Aerospace(object):
    """Command runner. Instantiate once per process."""

    def __init__(self, binary=None, runner=None):
        self._binary = binary
        # Injectable for tests; must mirror subprocess.run's signature enough
        # to return an object with .returncode/.stdout/.stderr.
        self._runner = runner or _default_runner

    # ---------------------------------------------------------------- binary

    @property
    def binary(self):
        if self._binary is None:
            self._binary = find_binary()
        return self._binary

    # ------------------------------------------------------------------ core

    def run(self, args):
        """Run `aerospace <args>` and return stdout. Raises on non-zero exit."""
        argv = [self.binary] + list(args)
        result = self._runner(argv)
        if result.returncode != 0:
            raise AerospaceCommandError(args, result.returncode, result.stderr)
        return result.stdout

    def run_json(self, args):
        raw = self.run(list(args) + ["--json"])
        raw = raw.strip()
        if not raw:
            return []
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise AerospaceCommandError(
                args, 0, "could not parse JSON output: {0}".format(exc)
            )

    # ------------------------------------------------------------------ read

    def list_workspaces(self, with_window_counts=True):
        payload = self.run_json(
            ["list-workspaces", "--all", "--format", _WORKSPACE_FIELDS]
        )
        workspaces = [Workspace.from_json(item) for item in payload]
        if with_window_counts:
            counts = {}
            for window in self.list_windows():
                counts[window.workspace] = counts.get(window.workspace, 0) + 1
            for workspace in workspaces:
                workspace.window_count = counts.get(workspace.name, 0)
        return workspaces

    def list_windows(self):
        payload = self.run_json(
            ["list-windows", "--all", "--format", _WINDOW_FIELDS]
        )
        return [Window.from_json(item) for item in payload]

    def focused_workspace(self):
        payload = self.run_json(
            ["list-workspaces", "--focused", "--format", "%{workspace}"]
        )
        if not payload:
            return ""
        return payload[0].get("workspace", "")

    def focused_window(self):
        payload = self.run_json(
            ["list-windows", "--focused", "--format", _WINDOW_FIELDS]
        )
        if not payload:
            return None
        return Window.from_json(payload[0])

    def workspace_names(self):
        return [w.name for w in self.list_workspaces(with_window_counts=False)]

    # ----------------------------------------------------------------- write

    def focus_workspace(self, name):
        """Focus `name`, creating it implicitly if it does not exist yet."""
        self.run(["workspace", "--", name])

    def move_window_to_workspace(self, window_id, name, follow=True):
        args = ["move-node-to-workspace", "--window-id", str(window_id)]
        if follow:
            args.append("--focus-follows-window")
        args += ["--", name]
        self.run(args)

    def move_focused_window_to_workspace(self, name, follow=True):
        args = ["move-node-to-workspace"]
        if follow:
            args.append("--focus-follows-window")
        args += ["--", name]
        self.run(args)


# --------------------------------------------------------------------- utils


class _Result(object):
    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _default_runner(argv):
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    stdout, stderr = proc.communicate()
    return _Result(proc.returncode, stdout, stderr)


def find_binary(extra_paths=(), which=None, isfile=None):
    """Locate the `aerospace` executable.

    Alfred launches workflow scripts with a minimal PATH that typically lacks
    /opt/homebrew/bin, so PATH lookup alone is not enough.
    """
    which = which or shutil.which
    isfile = isfile or (lambda p: os.path.isfile(p) and os.access(p, os.X_OK))

    override = config.aerospace_binary_override()
    if override:
        if isfile(override):
            return override
        raise AerospaceNotFound(
            "AEROSPACE_BIN is set to {0!r} but that is not an executable "
            "file.".format(override)
        )

    found = which("aerospace")
    if found:
        return found

    for candidate in tuple(extra_paths) + config.FALLBACK_BINARY_PATHS:
        if candidate and isfile(candidate):
            return candidate

    raise AerospaceNotFound(
        "Could not find the 'aerospace' binary. Install AeroSpace, or set the "
        "AEROSPACE_BIN workflow variable to its full path."
    )
