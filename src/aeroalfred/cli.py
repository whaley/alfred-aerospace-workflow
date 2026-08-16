"""Command-line entry point invoked by every Alfred object in the workflow.

Usage:
    run.py workspaces [query]   # `ws`  script filter
    run.py new        [query]   # `wsn` script filter
    run.py windows    [query]   # `wsw` script filter
    run.py perform    <arg>     # the Run Script action
    run.py doctor               # environment diagnostics

Script Filters must *always* print valid JSON -- if they don't, Alfred shows an
opaque "invalid JSON" error instead of a useful message. Every failure path
below therefore still emits a well-formed feedback list.
"""

from __future__ import annotations

import sys

from . import alfred, commands, config
from .aerospace import Aerospace, find_binary
from .errors import AeroAlfredError

FILTERS = {
    "workspaces": commands.workspaces_filter,
    "new": commands.new_workspace_filter,
    "windows": commands.window_workspace_filter,
}

USAGE = __doc__


def main(argv=None, client=None, stdout=None, stderr=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    if not argv:
        stderr.write(USAGE)
        return 2

    command = argv[0]
    query = argv[1] if len(argv) > 1 else ""

    if command in ("-h", "--help", "help"):
        stdout.write(USAGE)
        return 0

    if command == "doctor":
        return _doctor(stdout, stderr, client)

    if command in FILTERS:
        return _run_filter(FILTERS[command], query, client, stdout)

    if command == "perform":
        return _run_perform(query, client, stdout, stderr)

    stderr.write("Unknown command: {0}\n{1}".format(command, USAGE))
    return 2


def _client(client):
    return client if client is not None else Aerospace()


def _run_filter(handler, query, client, stdout):
    try:
        feedback = handler(_client(client), query)
    except AeroAlfredError as exc:
        feedback = alfred.error_feedback(_headline(exc), str(exc))
    except Exception as exc:  # noqa: BLE001 - Alfred needs JSON, never a traceback
        feedback = alfred.error_feedback(
            "Unexpected error", "{0}: {1}".format(type(exc).__name__, exc)
        )
    stdout.write(feedback.to_json())
    stdout.write("\n")
    return 0


def _run_perform(raw_arg, client, stdout, stderr):
    try:
        message = commands.perform(_client(client), raw_arg)
    except AeroAlfredError as exc:
        # stdout feeds Alfred's notification; stderr feeds Alfred's debugger.
        stdout.write(str(exc))
        stderr.write("{0}\n".format(exc))
        return 1
    except Exception as exc:  # noqa: BLE001
        message = "{0}: {1}".format(type(exc).__name__, exc)
        stdout.write(message)
        stderr.write("{0}\n".format(message))
        return 1

    if message:
        stdout.write(message)
    return 0


def _headline(exc):
    """A short, human title for the first row of an error feedback list."""
    name = type(exc).__name__
    if name == "AerospaceNotFound":
        return "AeroSpace not found"
    if name == "AerospaceCommandError":
        return "AeroSpace command failed"
    if name == "InvalidWorkspaceName":
        return "Invalid workspace name"
    return "Something went wrong"


def _doctor(stdout, stderr, client=None):
    """Print a short diagnostic report. Handy when Alfred behaves oddly."""
    ok = True

    stdout.write("aeroalfred doctor\n")
    stdout.write("  python      : {0}\n".format(sys.version.split()[0]))
    stdout.write("  executable  : {0}\n".format(sys.executable))

    try:
        binary = find_binary()
        stdout.write("  aerospace   : {0}\n".format(binary))
    except AeroAlfredError as exc:
        stdout.write("  aerospace   : NOT FOUND\n")
        stderr.write("{0}\n".format(exc))
        return 1

    stdout.write("  max name len: {0}\n".format(config.max_name_length()))
    stdout.write("  title strat : {0}\n".format(config.title_strategy()))

    try:
        aerospace = _client(client)
        workspaces = aerospace.list_workspaces()
        windows = aerospace.list_windows()
        stdout.write("  workspaces  : {0} ({1})\n".format(
            len(workspaces), ", ".join(w.name for w in workspaces) or "none"
        ))
        stdout.write("  windows     : {0}\n".format(len(windows)))
        stdout.write("  focused ws  : {0}\n".format(aerospace.focused_workspace()))
    except AeroAlfredError as exc:
        stdout.write("  query       : FAILED\n")
        stderr.write("{0}\n".format(exc))
        ok = False

    stdout.write("  status      : {0}\n".format("ok" if ok else "problems found"))
    return 0 if ok else 1
