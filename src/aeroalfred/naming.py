"""Turn arbitrary window titles into legal AeroSpace workspace names.

AeroSpace's own validation rules (lifted verbatim from the 0.21.3 binary):

    "Whitespace characters are forbidden in workspace names"
    "Workspace names starting with dash are disallowed"
    "Workspace names starting with underscore are reserved for future use"
    "Workspace names are not allowed to contain comma"
    "Empty workspace name is forbidden"
    "<name> is a reserved workspace name"

`validate()` mirrors those rules so the UI can reject a bad name *before*
shelling out. `derive_workspace_name()` coerces any string into a name that
passes them.
"""

from __future__ import annotations

import re
import unicodedata

from . import config
from .errors import InvalidWorkspaceName

#: Names AeroSpace treats as relative-motion keywords rather than workspaces.
RESERVED_NAMES = frozenset({"next", "prev"})

#: Substituted for any run of forbidden characters.
SEPARATOR = "-"

_SEGMENT_SPLIT_RE = re.compile(r"\s+[-–—|:·]\s+")
_FORBIDDEN_RUN_RE = re.compile(r"[\s,]+")
_SEPARATOR_RUN_RE = re.compile(r"-{2,}")
# Characters that survive sanitising: letters, digits, and a small safe set.
_UNSAFE_RE = re.compile(r"[^\w.+#@()\[\]-]", re.UNICODE)


def validate(name):
    """Raise :class:`InvalidWorkspaceName` if `name` breaks an AeroSpace rule."""
    if name is None or name == "":
        raise InvalidWorkspaceName("Empty workspace name is forbidden")
    if any(ch.isspace() for ch in name):
        raise InvalidWorkspaceName(
            "Whitespace characters are forbidden in workspace names"
        )
    if "," in name:
        raise InvalidWorkspaceName(
            "Workspace names are not allowed to contain comma"
        )
    if name.startswith("-"):
        raise InvalidWorkspaceName(
            "Workspace names starting with dash are disallowed"
        )
    if name.startswith("_"):
        raise InvalidWorkspaceName(
            "Workspace names starting with underscore are reserved"
        )
    if name.lower() in RESERVED_NAMES:
        raise InvalidWorkspaceName(
            "'{0}' is a reserved workspace name".format(name)
        )
    return name


def is_valid(name):
    """Boolean form of :func:`validate`."""
    try:
        validate(name)
    except InvalidWorkspaceName:
        return False
    return True


def validation_error(name):
    """Return the reason `name` is invalid, or ``None`` when it is fine."""
    try:
        validate(name)
    except InvalidWorkspaceName as exc:
        return str(exc)
    return None


def select_segment(title, strategy):
    """Pick the meaningful part of a title according to `strategy`."""
    title = (title or "").strip()
    if not title or strategy == "full":
        return title
    segments = [s.strip() for s in _SEGMENT_SPLIT_RE.split(title) if s.strip()]
    if not segments:
        return title
    if strategy == "first-segment":
        return segments[0]
    if strategy == "last-segment":
        return segments[-1]
    return title


def sanitize(text, max_length=None):
    """Coerce `text` into a string that satisfies AeroSpace's naming rules.

    Returns an empty string when nothing usable survives; callers decide the
    fallback.
    """
    max_length = max_length or config.max_name_length()
    text = unicodedata.normalize("NFKC", text or "").strip()
    if not text:
        return ""

    # Forbidden characters first, then anything else outside the safe set.
    text = _FORBIDDEN_RUN_RE.sub(SEPARATOR, text)
    text = _UNSAFE_RE.sub(SEPARATOR, text)
    text = _SEPARATOR_RUN_RE.sub(SEPARATOR, text)
    text = text.strip("-_")

    if not text:
        return ""

    if len(text) > max_length:
        text = _truncate_on_boundary(text, max_length)

    return text.strip("-_")


def _truncate_on_boundary(text, max_length):
    """Cut to `max_length`, preferring the last separator in the tail."""
    clipped = text[:max_length]
    pivot = clipped.rfind(SEPARATOR)
    # Only honour the boundary if it keeps a reasonable amount of the name.
    if pivot >= max_length // 2:
        return clipped[:pivot]
    return clipped


def deduplicate(name, existing):
    """Append -2, -3, ... until `name` no longer collides with `existing`."""
    taken = {str(item).lower() for item in existing or ()}
    if name.lower() not in taken:
        return name
    index = 2
    while "{0}-{1}".format(name, index).lower() in taken:
        index += 1
    return "{0}-{1}".format(name, index)


def derive_workspace_name(title, app_name="", existing=(), strategy=None,
                          max_length=None, unique=True):
    """Build a legal, non-colliding workspace name from a window title.

    Falls back to the app name, then to ``"workspace"``, so this never raises.
    """
    strategy = strategy or config.title_strategy()
    max_length = max_length or config.max_name_length()

    candidate = sanitize(select_segment(title, strategy), max_length)
    if not candidate:
        candidate = sanitize(app_name, max_length)
    if not candidate:
        candidate = "workspace"

    # A sanitised title could still land on a reserved word.
    if candidate.lower() in RESERVED_NAMES:
        candidate = "{0}{1}ws".format(candidate, SEPARATOR)

    if unique:
        candidate = deduplicate(candidate, existing)

    return validate(candidate)
