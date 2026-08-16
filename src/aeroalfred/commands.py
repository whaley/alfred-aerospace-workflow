"""The user-facing behaviours, one function per Alfred entry point.

Each ``*_filter`` function returns an :class:`alfred.Feedback` and performs no
mutations. :func:`perform` is the only function that changes AeroSpace state.
"""

from __future__ import annotations

from . import actions, alfred, config, matching, naming
from .errors import AeroAlfredError

_WORKSPACE_ICON = "icons/workspace.png"
_NEW_ICON = "icons/new.png"


# --------------------------------------------------------------- ws (list +
#                                                                  switch)

def workspaces_filter(client, query=""):
    """`ws` -- list every workspace, switch on Enter, offer to create on miss."""
    query = (query or "").strip()
    workspaces = client.list_workspaces()

    # Focused first, then visible, then by name -- a stable, useful default
    # ordering for the empty query.
    workspaces.sort(
        key=lambda w: (not w.is_focused, not w.is_visible, w.name.lower())
    )

    if not config.show_empty_workspaces():
        workspaces = [w for w in workspaces if w.window_count or w.is_focused]

    matches = matching.rank(query, workspaces, key=lambda w: w.name)

    feedback = alfred.Feedback()
    for workspace in matches:
        feedback.add(_workspace_item(workspace))

    _maybe_offer_creation(feedback, query, workspaces)

    if not len(feedback):
        feedback.add(_nothing_matched(query, workspaces))
    return feedback


def _nothing_matched(query, workspaces):
    """Explain an empty result list without guessing at the wrong cause."""
    if not workspaces:
        return alfred.Item(
            "No workspaces found",
            subtitle="AeroSpace reported no workspaces. Is it running?",
            valid=False,
        )
    # Workspaces exist, so the query simply matched nothing -- and since no
    # "Create" row was offered, the query is not a legal name either.
    problem = naming.validation_error(query)
    return alfred.Item(
        "No workspace matches “{0}”".format(query),
        subtitle=("Cannot create it either: {0}".format(problem[0].lower()
                                                        + problem[1:])
                  if problem else "Try a different search."),
        valid=False,
    )


def _workspace_item(workspace):
    badge = []
    if workspace.is_focused:
        badge.append("● focused")
    elif workspace.is_visible:
        badge.append("○ visible")

    if workspace.window_count == 1:
        badge.append("1 window")
    else:
        badge.append("{0} windows".format(workspace.window_count))

    if workspace.monitor_name:
        badge.append(workspace.monitor_name)

    item = alfred.Item(
        title=workspace.name,
        subtitle=" · ".join(badge),
        arg=actions.encode(actions.FOCUS, workspace.name),
        uid="workspace/{0}".format(workspace.name),
        autocomplete=workspace.name,
        icon=alfred.icon_path(_WORKSPACE_ICON),
    )
    item.add_mod(
        "cmd",
        "Move the focused window to {0} and follow it".format(workspace.name),
        arg=actions.encode(actions.MOVE_FOCUSED, workspace.name),
    )
    return item


def _maybe_offer_creation(feedback, query, workspaces):
    """Append a 'Create workspace X' row when the query is a fresh, legal name."""
    if not query:
        return
    existing = {w.name.lower() for w in workspaces}
    if query.lower() in existing:
        return
    if not naming.is_valid(query):
        return
    feedback.add(_create_item(query))


def _create_item(name):
    item = alfred.Item(
        title="Create workspace “{0}”".format(name),
        subtitle="Switch to a new empty workspace · ⌘ to bring the focused "
                 "window along",
        arg=actions.encode(actions.FOCUS, name),
        uid="create/{0}".format(name),
        icon=alfred.icon_path(_NEW_ICON),
    )
    item.add_mod(
        "cmd",
        "Create {0} and move the focused window into it".format(name),
        arg=actions.encode(actions.MOVE_FOCUSED, name),
    )
    return item


# -------------------------------------------------------- wsn (create named)

def new_workspace_filter(client, query=""):
    """`wsn` -- create a workspace with a name typed by hand."""
    query = (query or "").strip()
    feedback = alfred.Feedback()

    if not query:
        feedback.warn_empty(
            "Type a name for the new workspace",
            "Letters, digits and dashes. No spaces or commas.",
            icon=alfred.icon_path(_NEW_ICON),
        )
        return feedback

    problem = naming.validation_error(query)
    if problem:
        suggestion = naming.sanitize(query)
        subtitle = problem
        if suggestion and naming.is_valid(suggestion):
            subtitle += " · Try “{0}”".format(suggestion)
        feedback.warn_empty("Invalid workspace name", subtitle)
        if suggestion and naming.is_valid(suggestion):
            feedback.add(_create_item(suggestion))
        return feedback

    existing = {name.lower(): name for name in client.workspace_names()}
    if query.lower() in existing:
        actual = existing[query.lower()]
        item = alfred.Item(
            title="Switch to “{0}”".format(actual),
            subtitle="That workspace already exists",
            arg=actions.encode(actions.FOCUS, actual),
            uid="workspace/{0}".format(actual),
            icon=alfred.icon_path(_WORKSPACE_ICON),
        )
        item.add_mod(
            "cmd",
            "Move the focused window to {0} and follow it".format(actual),
            arg=actions.encode(actions.MOVE_FOCUSED, actual),
        )
        feedback.add(item)
        return feedback

    feedback.add(_create_item(query))
    return feedback


# --------------------------------------------- wsw (create from window title)

def window_workspace_filter(client, query=""):
    """`wsw` -- name a new workspace after an existing window's title."""
    query = (query or "").strip()
    windows = client.list_windows()
    existing = client.workspace_names()

    matches = matching.rank(
        query,
        windows,
        key=lambda w: "{0} {1}".format(w.app_name, w.title),
    )

    feedback = alfred.Feedback()
    existing_lower = {name.lower() for name in existing}

    for window in matches:
        target = naming.derive_workspace_name(
            window.title,
            app_name=window.app_name,
            existing=existing,
            unique=False,
        )
        if target.lower() in existing_lower:
            subtitle = "Move to existing workspace “{0}”".format(target)
        else:
            subtitle = "Create workspace “{0}” and move this window in".format(
                target
            )

        item = alfred.Item(
            title=window.display_title,
            subtitle="{0} · {1}".format(window.app_name, subtitle),
            arg=actions.encode(
                actions.MOVE_WINDOW, target, window_id=window.window_id
            ),
            uid="window/{0}".format(window.window_id),
            match="{0} {1} {2}".format(window.app_name, window.title, target),
            icon=(
                alfred.file_icon(window.app_bundle_path)
                if window.app_bundle_path
                else alfred.icon_path(_NEW_ICON)
            ),
            text={"copy": target, "largetype": window.display_title},
        )
        feedback.add(item)

    if not len(feedback):
        feedback.warn_empty(
            "No matching windows" if query else "No managed windows",
            "AeroSpace is not tracking any window that matches."
            if query
            else "Open a window first, then try again.",
        )
    return feedback


# ------------------------------------------------------------------ perform

def perform(client, raw_arg):
    """Execute an encoded action. Returns a status string, or ``""`` on success.

    A non-empty return travels to Alfred's notification output; an empty one
    keeps the workflow silent.
    """
    payload = actions.decode(raw_arg)
    workspace = payload["workspace"]
    naming.validate(workspace)

    action = payload["action"]
    if action == actions.FOCUS:
        client.focus_workspace(workspace)
    elif action == actions.MOVE_FOCUSED:
        client.move_focused_window_to_workspace(
            workspace, follow=config.follow_window_on_create()
        )
    elif action == actions.MOVE_WINDOW:
        window_id = payload["window_id"]
        if window_id is None:
            raise AeroAlfredError("This action needs a window_id.")
        client.move_window_to_workspace(
            window_id, workspace, follow=config.follow_window_on_create()
        )
    else:  # pragma: no cover - decode() already rejects unknown actions
        raise AeroAlfredError("Unknown action: {0!r}".format(action))

    return ""
