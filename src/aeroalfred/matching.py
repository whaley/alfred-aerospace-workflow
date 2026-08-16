"""Subsequence matching + ranking used by the Script Filters.

We filter in Python rather than letting Alfred do it (``alfredfiltersresults``
is off) because we need to append synthesized rows -- "Create workspace X" --
that depend on whether anything matched.
"""

from __future__ import annotations


def score(query, candidate):
    """Return a match score for `candidate`, or ``None`` when it doesn't match.

    Higher is better. Matching is case-insensitive and subsequence-based, so
    "afw" matches "alfred-aerospace-workflow".
    """
    if not query:
        return 0
    query_l = query.lower()
    candidate_l = candidate.lower()

    if candidate_l == query_l:
        return 1000
    if candidate_l.startswith(query_l):
        return 900 - len(candidate_l)
    index = candidate_l.find(query_l)
    if index != -1:
        # Prefer matches that begin at a word boundary.
        boundary = index == 0 or candidate_l[index - 1] in "-_.() []"
        return (800 if boundary else 700) - index - len(candidate_l) * 0.01

    return _subsequence_score(query_l, candidate_l)


def _subsequence_score(query, candidate):
    position = 0
    gaps = 0
    first = None
    for char in query:
        found = candidate.find(char, position)
        if found == -1:
            return None
        if first is None:
            first = found
        if position and found > position:
            gaps += found - position
        position = found + 1
    return 600 - gaps - (first or 0) - len(candidate) * 0.01


def rank(query, entries, key):
    """Filter and sort `entries` by match quality against `query`.

    `key` extracts the searchable text. Ties keep the original order, so a
    caller's own preferred ordering survives an empty query.
    """
    scored = []
    for index, entry in enumerate(entries):
        value = score(query, key(entry))
        if value is None:
            continue
        scored.append((-value, index, entry))
    scored.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored]
