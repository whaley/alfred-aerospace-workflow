"""The action payload passed from a Script Filter to the Run Script object.

Script Filters emit a compact JSON blob as the item's ``arg``; the downstream
"Perform" Run Script decodes it and calls AeroSpace. Keeping every mutation
behind one encoded payload means the workflow graph stays at four objects
regardless of how many behaviours we add.
"""

from __future__ import annotations

import json

from .errors import AeroAlfredError

FOCUS = "focus"
MOVE_FOCUSED = "move-focused"
MOVE_WINDOW = "move-window"

ALL_ACTIONS = (FOCUS, MOVE_FOCUSED, MOVE_WINDOW)


def encode(action, workspace, window_id=None):
    """Serialise an action into the string handed to Alfred as ``arg``."""
    if action not in ALL_ACTIONS:
        raise ValueError("unknown action: {0!r}".format(action))
    payload = {"action": action, "workspace": workspace}
    if window_id is not None:
        payload["window_id"] = int(window_id)
    # Compact separators keep the arg readable in Alfred's debugger.
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def decode(raw):
    """Parse an action payload produced by :func:`encode`."""
    raw = (raw or "").strip()
    if not raw:
        raise AeroAlfredError("No action was passed to the Perform step.")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise AeroAlfredError("Malformed action payload: {0!r}".format(raw))
    if not isinstance(payload, dict):
        raise AeroAlfredError("Action payload must be a JSON object.")

    action = payload.get("action")
    if action not in ALL_ACTIONS:
        raise AeroAlfredError("Unknown action: {0!r}".format(action))

    workspace = payload.get("workspace")
    if not workspace:
        raise AeroAlfredError("Action payload is missing a workspace name.")

    window_id = payload.get("window_id")
    if window_id is not None:
        try:
            window_id = int(window_id)
        except (TypeError, ValueError):
            raise AeroAlfredError(
                "Invalid window_id: {0!r}".format(payload.get("window_id"))
            )

    return {"action": action, "workspace": workspace, "window_id": window_id}
