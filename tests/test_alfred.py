"""Script Filter JSON shape, action encoding, and match ranking."""

from __future__ import annotations

import json
import unittest

from support import ROOT  # noqa: F401  (installs sys.path)

from aeroalfred import actions, alfred, matching
from aeroalfred.errors import AeroAlfredError


class ItemTests(unittest.TestCase):

    def test_minimal_item_omits_empty_keys(self):
        payload = alfred.Item("Title").to_dict()
        self.assertEqual(payload, {"title": "Title", "valid": True})

    def test_full_item_round_trips(self):
        item = alfred.Item(
            "Title", subtitle="Sub", arg="ARG", uid="U", autocomplete="auto",
            match="m", icon={"path": "x.png"},
        )
        payload = item.to_dict()
        self.assertEqual(payload["subtitle"], "Sub")
        self.assertEqual(payload["arg"], "ARG")
        self.assertEqual(payload["uid"], "U")
        self.assertEqual(payload["autocomplete"], "auto")
        self.assertEqual(payload["icon"], {"path": "x.png"})

    def test_autocomplete_empty_string_is_preserved(self):
        # "" is meaningful to Alfred (clears the query), so it must survive.
        self.assertIn("autocomplete", alfred.Item("t", autocomplete="").to_dict())

    def test_invalid_item_reports_valid_false(self):
        self.assertIs(alfred.Item("t", valid=False).to_dict()["valid"], False)

    def test_add_mod(self):
        item = alfred.Item("t").add_mod("cmd", "Do the other thing", arg="X")
        self.assertEqual(
            item.to_dict()["mods"],
            {"cmd": {"subtitle": "Do the other thing", "valid": True,
                     "arg": "X"}},
        )

    def test_file_icon_helper(self):
        self.assertEqual(
            alfred.file_icon("/Applications/Arc.app"),
            {"type": "fileicon", "path": "/Applications/Arc.app"},
        )


class FeedbackTests(unittest.TestCase):

    def test_serialises_to_valid_json(self):
        feedback = alfred.Feedback()
        feedback.add_item("One", arg="1")
        feedback.add_item("Two", arg="2")
        payload = json.loads(feedback.to_json())
        self.assertEqual([i["title"] for i in payload["items"]], ["One", "Two"])

    def test_skipknowledge_is_on_by_default(self):
        # We rank results ourselves; Alfred must not re-sort them.
        self.assertTrue(json.loads(alfred.Feedback().to_json())["skipknowledge"])

    def test_skipknowledge_can_be_disabled(self):
        payload = json.loads(alfred.Feedback(skipknowledge=False).to_json())
        self.assertNotIn("skipknowledge", payload)

    def test_empty_feedback_is_still_valid_json(self):
        payload = json.loads(alfred.Feedback().to_json())
        self.assertEqual(payload["items"], [])

    def test_len_counts_items(self):
        feedback = alfred.Feedback()
        self.assertEqual(len(feedback), 0)
        feedback.add_item("x")
        self.assertEqual(len(feedback), 1)

    def test_warn_empty_is_not_actionable(self):
        feedback = alfred.Feedback()
        feedback.warn_empty("Nothing", "here")
        self.assertFalse(feedback.items[0].valid)

    def test_error_feedback_has_exactly_one_row(self):
        payload = json.loads(alfred.error_feedback("Boom", "details").to_json())
        self.assertEqual(len(payload["items"]), 1)
        self.assertIs(payload["items"][0]["valid"], False)

    def test_unicode_survives(self):
        feedback = alfred.Feedback()
        feedback.add_item("café — 日本語 🎉")
        self.assertIn("café", json.loads(feedback.to_json())["items"][0]["title"])


class ActionTests(unittest.TestCase):

    def test_round_trip(self):
        raw = actions.encode(actions.MOVE_WINDOW, "code", window_id=7)
        self.assertEqual(
            actions.decode(raw),
            {"action": actions.MOVE_WINDOW, "workspace": "code",
             "window_id": 7},
        )

    def test_window_id_is_optional(self):
        decoded = actions.decode(actions.encode(actions.FOCUS, "code"))
        self.assertIsNone(decoded["window_id"])

    def test_encode_rejects_unknown_action(self):
        with self.assertRaises(ValueError):
            actions.encode("teleport", "code")

    def test_decode_rejects_unknown_action(self):
        with self.assertRaises(AeroAlfredError):
            actions.decode(json.dumps({"action": "teleport", "workspace": "a"}))

    def test_decode_rejects_empty_input(self):
        for value in ("", "   ", None):
            with self.assertRaises(AeroAlfredError):
                actions.decode(value)

    def test_decode_rejects_malformed_json(self):
        with self.assertRaises(AeroAlfredError):
            actions.decode("{oops")

    def test_decode_rejects_non_object(self):
        with self.assertRaises(AeroAlfredError):
            actions.decode('["a"]')

    def test_decode_requires_workspace(self):
        with self.assertRaises(AeroAlfredError):
            actions.decode(json.dumps({"action": actions.FOCUS}))

    def test_decode_rejects_bad_window_id(self):
        payload = json.dumps({"action": actions.MOVE_WINDOW,
                              "workspace": "a", "window_id": "abc"})
        with self.assertRaises(AeroAlfredError):
            actions.decode(payload)

    def test_names_with_quotes_survive_encoding(self):
        raw = actions.encode(actions.FOCUS, 'we"ird')
        self.assertEqual(actions.decode(raw)["workspace"], 'we"ird')


class MatchingTests(unittest.TestCase):

    def test_empty_query_matches_everything_equally(self):
        self.assertEqual(matching.score("", "anything"), 0)

    def test_exact_match_scores_highest(self):
        self.assertGreater(
            matching.score("code", "code"), matching.score("code", "codebase")
        )

    def test_prefix_beats_substring(self):
        self.assertGreater(
            matching.score("co", "code"), matching.score("co", "xxcode")
        )

    def test_subsequence_matches(self):
        self.assertIsNotNone(matching.score("afw", "alfred-aerospace-workflow"))

    def test_non_match_returns_none(self):
        self.assertIsNone(matching.score("zzz", "code"))

    def test_case_insensitive(self):
        self.assertIsNotNone(matching.score("CODE", "code"))

    def test_rank_filters_and_orders(self):
        entries = ["chat", "code", "codebase"]
        self.assertEqual(
            matching.rank("code", entries, key=lambda e: e), ["code", "codebase"]
        )

    def test_rank_preserves_input_order_for_empty_query(self):
        entries = ["b", "a", "c"]
        self.assertEqual(matching.rank("", entries, key=lambda e: e), entries)

    def test_rank_drops_non_matches(self):
        self.assertEqual(matching.rank("zz", ["a", "b"], key=lambda e: e), [])


if __name__ == "__main__":
    unittest.main()
