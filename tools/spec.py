"""Declarative definition of the Alfred workflow graph.

`info.plist` is *generated* from this module rather than hand-edited, so the
repository holds a readable, diffable source of truth instead of a 400-line
XML blob. Object UIDs are derived deterministically from stable names via
uuid5, which keeps rebuilds byte-identical.

Magic numbers below were confirmed by reading the plists of working workflows
already installed on this machine -- see docs/alfred-workflow-format.md.
"""

from __future__ import annotations

import uuid

BUNDLE_ID = "com.morninghacks.aerospace-workspaces"
NAME = "AeroSpace Workspaces"
VERSION = "1.0.0"
CREATED_BY = "whaley"
WEB_ADDRESS = "https://github.com/whaley/alfred-aerospace-workflow"
DESCRIPTION = "List, switch to, and create AeroSpace workspaces from Alfred."

#: Stable namespace so object UIDs never drift between builds.
_UID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, BUNDLE_ID)

# --- Alfred plist enums (verified against installed workflows) --------------
LANG_BASH = 0            # config.type -> /bin/bash
ARG_AS_ARGV = 1          # config.scriptargtype -> input arrives as "$1"
ARG_OPTIONAL = 1         # config.argumenttype -> keyword works with no query
ESCAPING_DEFAULT = 102   # backquotes/quotes/backslashes/dollars

#: Every script runs through the same shim. AEROALFRED_PYTHON lets a user pin a
#: different interpreter; the default is macOS's own python3.
SHIM = '"${{AEROALFRED_PYTHON:-/usr/bin/python3}}" run.py {command} "$1"'


def uid(name):
    """Deterministic, Alfred-style uppercase UUID for a stable object name."""
    return str(uuid.uuid5(_UID_NAMESPACE, name)).upper()


def _script_filter(name, keyword, title, subtext, command, running):
    return {
        "uid": uid(name),
        "type": "alfred.workflow.input.scriptfilter",
        "version": 3,
        "config": {
            # We rank and filter in Python because the result list contains
            # synthesized rows (e.g. "Create workspace X") that depend on
            # whether anything matched.
            "alfredfiltersresults": False,
            "alfredfiltersresultsmatchmode": 0,
            "argumenttreatemptyqueryasnil": False,
            "argumenttrimmode": 0,
            "argumenttype": ARG_OPTIONAL,
            "escaping": ESCAPING_DEFAULT,
            "keyword": keyword,
            "queuedelaycustom": 3,
            "queuedelayimmediatelyinitially": True,
            "queuedelaymode": 0,
            "queuemode": 1,
            "runningsubtext": running,
            "script": SHIM.format(command=command),
            "scriptargtype": ARG_AS_ARGV,
            "scriptfile": "",
            "subtext": subtext,
            "title": title,
            "type": LANG_BASH,
            "withspace": True,
        },
    }


OBJECTS = [
    _script_filter(
        name="scriptfilter.workspaces",
        keyword="ws",
        title="AeroSpace Workspaces",
        subtext="Switch to a workspace, or create one by typing a new name",
        command="workspaces",
        running="Asking AeroSpace…",
    ),
    _script_filter(
        name="scriptfilter.new",
        keyword="wsn",
        title="New AeroSpace Workspace",
        subtext="Create a workspace with a name you type",
        command="new",
        running="Checking that name…",
    ),
    _script_filter(
        name="scriptfilter.windows",
        keyword="wsw",
        title="New Workspace From Window",
        subtext="Name a new workspace after an open window, and move it there",
        command="windows",
        running="Listing windows…",
    ),
    _script_filter(
        name="scriptfilter.pull",
        keyword="wsp",
        title="Pull Window To This Workspace",
        subtext="Move a window from another workspace into the focused one",
        command="pull",
        running="Listing windows…",
    ),
    {
        "uid": uid("action.perform"),
        "type": "alfred.workflow.action.script",
        "version": 2,
        "config": {
            "concurrently": False,
            "escaping": ESCAPING_DEFAULT,
            "script": SHIM.format(command="perform"),
            "scriptargtype": ARG_AS_ARGV,
            "scriptfile": "",
            "type": LANG_BASH,
        },
    },
    {
        "uid": uid("output.notification"),
        "type": "alfred.workflow.output.notification",
        "version": 1,
        "config": {
            "lastpathcomponent": False,
            # The Perform step stays silent on success and prints a message on
            # failure, so this only ever fires when something went wrong.
            "onlyshowifquerypopulated": True,
            "removeextension": False,
            "text": "{query}",
            "title": "AeroSpace",
        },
    },
]

#: source object name -> destination object name
CONNECTIONS = [
    ("scriptfilter.workspaces", "action.perform"),
    ("scriptfilter.new", "action.perform"),
    ("scriptfilter.windows", "action.perform"),
    ("scriptfilter.pull", "action.perform"),
    ("action.perform", "output.notification"),
]

#: Canvas layout so the workflow is readable when opened in Alfred.
POSITIONS = {
    "scriptfilter.workspaces": (35, 40),
    "scriptfilter.new": (35, 170),
    "scriptfilter.windows": (35, 300),
    "scriptfilter.pull": (35, 430),
    # Vertically centred against the four script filters above.
    "action.perform": (330, 235),
    "output.notification": (555, 235),
}

NOTES = {
    "scriptfilter.workspaces":
        "Lists every workspace. Enter switches; ⌘Enter drags the focused "
        "window along. Typing an unused name offers to create it.",
    "scriptfilter.windows":
        "Derives a legal workspace name from the window title, then moves "
        "that window into it.",
    "scriptfilter.pull":
        "Lists windows that are NOT on the focused workspace. Enter moves the "
        "chosen one here; ⌘Enter goes to it instead.",
    "action.perform":
        "Decodes the JSON action emitted by the script filters and calls "
        "AeroSpace. Prints nothing on success.",
}

#: Defaults for the variables exposed in Alfred's Configure Workflow sheet.
VARIABLES = {
    "AEROSPACE_BIN": "",
    "AEROALFRED_TITLE_STRATEGY": "full",
    "AEROALFRED_MAX_NAME_LENGTH": "40",
    "AEROALFRED_FOLLOW_WINDOW": "1",
    "AEROALFRED_SHOW_EMPTY": "1",
}

USER_CONFIGURATION = [
    {
        "type": "textfield",
        "variable": "AEROSPACE_BIN",
        "label": "AeroSpace binary",
        "description": "Leave blank to search PATH and the usual Homebrew "
                       "locations. Set this if AeroSpace lives somewhere "
                       "unusual.",
        "config": {
            "default": "",
            "placeholder": "/opt/homebrew/bin/aerospace",
            "required": False,
            "trim": True,
        },
    },
    {
        "type": "popupbutton",
        "variable": "AEROALFRED_TITLE_STRATEGY",
        "label": "Name new workspaces after",
        "description": "How much of a window title to use when creating a "
                       "workspace from a window.",
        "config": {
            "default": "full",
            "pairs": [
                ["The whole title", "full"],
                ["Text before the first – | : separator", "first-segment"],
                ["Text after the last – | : separator", "last-segment"],
            ],
        },
    },
    {
        "type": "textfield",
        "variable": "AEROALFRED_MAX_NAME_LENGTH",
        "label": "Maximum name length",
        "description": "Derived names are truncated on a word boundary.",
        "config": {
            "default": "40",
            "placeholder": "40",
            "required": False,
            "trim": True,
        },
    },
    {
        "type": "checkbox",
        "variable": "AEROALFRED_FOLLOW_WINDOW",
        "label": "Follow moved windows",
        "description": "Switch to the destination workspace after moving a "
                       "window into it.",
        "config": {"default": True, "text": "Focus follows the moved window"},
    },
    {
        "type": "checkbox",
        "variable": "AEROALFRED_SHOW_EMPTY",
        "label": "Show empty workspaces",
        "description": "Include workspaces that currently hold no windows.",
        "config": {"default": True, "text": "List empty workspaces"},
    },
]

README = """\
# AeroSpace Workspaces

Workspace management for [AeroSpace](https://nikitabobko.github.io/AeroSpace/)
from Alfred.

## Keywords

- `ws` — list every workspace and switch to one.
  Type a name that does not exist yet to create it.
  ⌘⏎ moves the focused window to the workspace and follows it.
- `wsn <name>` — create a workspace with a name you type.
  The name is validated against AeroSpace's rules as you type.
- `wsw <filter>` — pick an open window; a new workspace is named after its
  title and the window is moved into it.
- `wsp <filter>` — pull a window from another workspace into the focused one.
  Only windows that are not already here are listed.
  ⌘⏎ switches to the window's workspace instead of moving it.

## Notes

AeroSpace creates workspaces lazily: an empty workspace disappears as soon as
you leave it. To make a new workspace stick, put a window in it — use ⌘⏎ from
`ws`/`wsn`, or use `wsw`.

Run `./run.py doctor` inside the workflow folder if something misbehaves.

## Configuration

Use *Configure Workflow* to set the AeroSpace binary path, how window titles
become workspace names, and whether focus follows moved windows.
"""
