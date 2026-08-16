"""Builders for Alfred's Script Filter JSON format.

Reference: https://www.alfredapp.com/help/workflows/inputs/script-filter/json/
"""

from __future__ import annotations

import json


class Item(object):
    """One row in an Alfred Script Filter result list."""

    def __init__(self, title, subtitle="", arg=None, uid=None, valid=True,
                 autocomplete=None, match=None, icon=None, mods=None,
                 text=None, quicklookurl=None):
        self.title = title
        self.subtitle = subtitle
        self.arg = arg
        self.uid = uid
        self.valid = valid
        self.autocomplete = autocomplete
        self.match = match
        self.icon = icon
        self.mods = mods or {}
        self.text = text or {}
        self.quicklookurl = quicklookurl

    def add_mod(self, key, subtitle, arg=None, valid=True):
        """Attach a modifier-key variant (cmd/alt/ctrl/shift/fn)."""
        mod = {"subtitle": subtitle, "valid": valid}
        if arg is not None:
            mod["arg"] = arg
        self.mods[key] = mod
        return self

    def to_dict(self):
        payload = {"title": self.title, "valid": self.valid}
        if self.subtitle:
            payload["subtitle"] = self.subtitle
        if self.arg is not None:
            payload["arg"] = self.arg
        if self.uid:
            payload["uid"] = self.uid
        if self.autocomplete is not None:
            payload["autocomplete"] = self.autocomplete
        if self.match:
            payload["match"] = self.match
        if self.icon:
            payload["icon"] = self.icon
        if self.mods:
            payload["mods"] = self.mods
        if self.text:
            payload["text"] = self.text
        if self.quicklookurl:
            payload["quicklookurl"] = self.quicklookurl
        return payload


def file_icon(path):
    """Render the macOS icon of the file/app at `path`."""
    return {"type": "fileicon", "path": path}


def icon_path(path):
    return {"path": path}


class Feedback(object):
    """Collects items and serialises the Script Filter response."""

    def __init__(self, skipknowledge=True):
        # skipknowledge preserves *our* ordering instead of letting Alfred
        # re-sort by usage frequency. We already rank results ourselves.
        self.skipknowledge = skipknowledge
        self.items = []
        self.variables = {}
        self.rerun = None

    def add(self, item):
        self.items.append(item)
        return item

    def add_item(self, *args, **kwargs):
        return self.add(Item(*args, **kwargs))

    def warn_empty(self, title, subtitle="", icon=None):
        """Add a single non-actionable row (used for empty/error states)."""
        return self.add(Item(title, subtitle=subtitle, valid=False, icon=icon))

    def to_dict(self):
        payload = {"items": [item.to_dict() for item in self.items]}
        if self.skipknowledge:
            payload["skipknowledge"] = True
        if self.variables:
            payload["variables"] = self.variables
        if self.rerun is not None:
            payload["rerun"] = self.rerun
        return payload

    def to_json(self, indent=None):
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def __len__(self):
        return len(self.items)


def error_feedback(message, subtitle=""):
    """A one-row feedback list describing a failure."""
    feedback = Feedback()
    feedback.warn_empty(message, subtitle or "Press ⌘L to read the full message.")
    return feedback
