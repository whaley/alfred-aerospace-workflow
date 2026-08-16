"""Shared test helpers: a fake `aerospace` process runner and env isolation."""

from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if path not in sys.path:
        sys.path.insert(0, path)

from aeroalfred.aerospace import Aerospace  # noqa: E402

#: Every AEROALFRED_*/AEROSPACE_* variable, cleared before each test so a
#: developer's own shell settings cannot change the outcome.
MANAGED_ENV = (
    "AEROSPACE_BIN",
    "AEROALFRED_PYTHON",
    "AEROALFRED_MAX_NAME_LENGTH",
    "AEROALFRED_TITLE_STRATEGY",
    "AEROALFRED_FOLLOW_WINDOW",
    "AEROALFRED_SHOW_EMPTY",
)

DEFAULT_WORKSPACES = [
    {"workspace": "Main", "workspace-is-focused": True,
     "workspace-is-visible": True, "monitor-id": 1,
     "monitor-name": "LS32D80xU"},
    {"workspace": "code", "workspace-is-focused": False,
     "workspace-is-visible": False, "monitor-id": 1,
     "monitor-name": "LS32D80xU"},
    {"workspace": "chat", "workspace-is-focused": False,
     "workspace-is-visible": False, "monitor-id": 1,
     "monitor-name": "LS32D80xU"},
]

DEFAULT_WINDOWS = [
    {"window-id": 1966, "window-title": "claude /create-agent - Kagi Search",
     "workspace": "Main", "app-name": "Arc",
     "app-bundle-path": "/Applications/Arc.app"},
    {"window-id": 2474, "window-title": "Welcome — alfred-aerospace-workflow",
     "workspace": "code", "app-name": "Code",
     "app-bundle-path": "/Applications/Visual Studio Code.app"},
    {"window-id": 2496, "window-title": "", "workspace": "Main",
     "app-name": "System Information",
     "app-bundle-path": "/System/Applications/Utilities/System Information.app"},
    {"window-id": 2323, "window-title": "weechat", "workspace": "chat",
     "app-name": "kitty", "app-bundle-path": "/Applications/kitty.app"},
]


class Result(object):
    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRunner(object):
    """Stands in for subprocess execution of the `aerospace` binary.

    Records every argv it is handed so tests can assert on the exact flags
    passed -- notably the `--` separator that protects workspace names such as
    "next" from being parsed as a subcommand.
    """

    def __init__(self, workspaces=None, windows=None, fail_with=None):
        self.workspaces = (DEFAULT_WORKSPACES if workspaces is None
                           else list(workspaces))
        self.windows = DEFAULT_WINDOWS if windows is None else list(windows)
        self.fail_with = fail_with  # (returncode, stderr) applied to mutations
        self.calls = []

    # -- helpers ----------------------------------------------------------

    @property
    def mutations(self):
        """Calls that changed state, minus the binary path."""
        return [call[1:] for call in self.calls
                if call[1] in ("workspace", "move-node-to-workspace")]

    def _project(self, rows, fmt):
        """Mimic AeroSpace's `--format ... --json`: only requested keys appear."""
        wanted = [token[2:-1] for token in _format_tokens(fmt)]
        return [{key: row[key] for key in wanted if key in row} for row in rows]

    # -- runner -----------------------------------------------------------

    def __call__(self, argv):
        self.calls.append(list(argv))
        args = list(argv[1:])
        command = args[0] if args else ""
        fmt = _value_after(args, "--format")

        if command == "list-workspaces":
            rows = self.workspaces
            if "--focused" in args:
                rows = [r for r in rows if r.get("workspace-is-focused")]
            return Result(stdout=json.dumps(self._project(rows, fmt)))

        if command == "list-windows":
            rows = self.windows
            if "--focused" in args:
                rows = rows[:1]
            return Result(stdout=json.dumps(self._project(rows, fmt)))

        if command in ("workspace", "move-node-to-workspace"):
            if self.fail_with:
                code, message = self.fail_with
                return Result(returncode=code, stderr=message)
            return Result()

        return Result(returncode=2, stderr="unknown command: {0}".format(command))


def _format_tokens(fmt):
    tokens = []
    index = 0
    while index < len(fmt):
        start = fmt.find("%{", index)
        if start == -1:
            break
        end = fmt.find("}", start)
        if end == -1:
            break
        tokens.append(fmt[start:end + 1])
        index = end + 1
    return tokens


def _value_after(args, flag):
    if flag in args:
        position = args.index(flag)
        if position + 1 < len(args):
            return args[position + 1]
    return ""


def make_client(runner=None, **kwargs):
    """An Aerospace client wired to a FakeRunner with a stub binary path."""
    runner = runner or FakeRunner(**kwargs)
    return Aerospace(binary="/fake/bin/aerospace", runner=runner), runner


class EnvIsolatedTestCase(unittest.TestCase):
    """Base class that restores AEROALFRED_*/AEROSPACE_* around each test."""

    def setUp(self):
        self._saved = {name: os.environ.get(name) for name in MANAGED_ENV}
        for name in MANAGED_ENV:
            os.environ.pop(name, None)
        self.addCleanup(self._restore)

    def _restore(self):
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def set_env(self, name, value):
        os.environ[name] = value
