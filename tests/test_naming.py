"""Workspace name validation and derivation."""

from __future__ import annotations

import unittest

from support import EnvIsolatedTestCase

from aeroalfred import naming
from aeroalfred.errors import InvalidWorkspaceName


class ValidateTests(EnvIsolatedTestCase):
    """Mirrors the rules embedded in the AeroSpace 0.21.3 binary."""

    def test_accepts_ordinary_names(self):
        for name in ("Main", "code", "1", "web-dev", "a.b", "ws_2", "café"):
            self.assertEqual(naming.validate(name), name)

    def test_rejects_empty(self):
        for value in ("", None):
            with self.assertRaises(InvalidWorkspaceName):
                naming.validate(value)

    def test_rejects_whitespace(self):
        for name in ("has space", "tab\there", "new\nline", " leading"):
            with self.assertRaises(InvalidWorkspaceName):
                naming.validate(name)

    def test_rejects_comma(self):
        with self.assertRaises(InvalidWorkspaceName):
            naming.validate("a,b")

    def test_rejects_leading_dash_and_underscore(self):
        for name in ("-nope", "_reserved"):
            with self.assertRaises(InvalidWorkspaceName):
                naming.validate(name)

    def test_rejects_reserved_words_case_insensitively(self):
        for name in ("next", "prev", "NEXT", "Prev"):
            with self.assertRaises(InvalidWorkspaceName):
                naming.validate(name)

    def test_dash_is_fine_when_not_leading(self):
        self.assertEqual(naming.validate("a-b"), "a-b")

    def test_validation_error_reports_reason(self):
        self.assertIn("Whitespace", naming.validation_error("a b"))
        self.assertIsNone(naming.validation_error("fine"))

    def test_is_valid(self):
        self.assertTrue(naming.is_valid("ok"))
        self.assertFalse(naming.is_valid("not ok"))


class SanitizeTests(EnvIsolatedTestCase):

    def test_spaces_become_dashes(self):
        self.assertEqual(naming.sanitize("hello world"), "hello-world")

    def test_collapses_separator_runs(self):
        self.assertEqual(naming.sanitize("a   ---   b"), "a-b")

    def test_strips_leading_and_trailing_separators(self):
        self.assertEqual(naming.sanitize("  -- hi -- "), "hi")

    def test_removes_commas(self):
        self.assertNotIn(",", naming.sanitize("a,b,c"))

    def test_result_is_always_valid(self):
        titles = [
            "claude /create-agent - Kagi Search",
            "Welcome — alfred-aerospace-workflow",
            "~/workspace/alfred-aerospace-workflow",
            "!!!",
            "  ",
            "日本語のタイトル",
            "emoji 🎉 party",
            "-leading-dash",
            "_leading_underscore",
        ]
        for title in titles:
            result = naming.sanitize(title)
            if result:
                self.assertTrue(
                    naming.is_valid(result),
                    "sanitize({0!r}) -> {1!r} is not valid".format(title, result),
                )

    def test_returns_empty_when_nothing_survives(self):
        self.assertEqual(naming.sanitize("   "), "")
        self.assertEqual(naming.sanitize(""), "")
        self.assertEqual(naming.sanitize(None), "")

    def test_truncates_to_max_length(self):
        result = naming.sanitize("a" * 100, max_length=10)
        self.assertLessEqual(len(result), 10)

    def test_truncation_prefers_word_boundary(self):
        result = naming.sanitize("alpha bravo charlie delta", max_length=14)
        self.assertEqual(result, "alpha-bravo")

    def test_truncation_ignores_useless_boundary(self):
        # The only dash sits too early to be a sensible cut point.
        result = naming.sanitize("a-bcdefghijklmnop", max_length=8)
        self.assertEqual(result, "a-bcdefg")

    def test_honours_max_name_length_env(self):
        self.set_env("AEROALFRED_MAX_NAME_LENGTH", "6")
        self.assertLessEqual(len(naming.sanitize("abcdefghijklmnop")), 6)


class SegmentTests(EnvIsolatedTestCase):

    def test_full_strategy_keeps_everything(self):
        title = "claude /create-agent - Kagi Search"
        self.assertEqual(naming.select_segment(title, "full"), title)

    def test_first_segment(self):
        self.assertEqual(
            naming.select_segment("claude /create-agent - Kagi Search",
                                  "first-segment"),
            "claude /create-agent",
        )

    def test_last_segment(self):
        self.assertEqual(
            naming.select_segment("Welcome — alfred-aerospace-workflow",
                                  "last-segment"),
            "alfred-aerospace-workflow",
        )

    def test_segment_split_needs_surrounding_spaces(self):
        # A hyphenated word must not be split.
        self.assertEqual(
            naming.select_segment("alfred-aerospace-workflow", "first-segment"),
            "alfred-aerospace-workflow",
        )

    def test_unknown_strategy_falls_back_to_full(self):
        self.assertEqual(naming.select_segment("a - b", "nonsense"), "a - b")


class DeriveTests(EnvIsolatedTestCase):

    def test_derives_from_title(self):
        self.assertEqual(
            naming.derive_workspace_name("weechat", app_name="kitty"),
            "weechat",
        )

    def test_falls_back_to_app_name_for_untitled_windows(self):
        self.assertEqual(
            naming.derive_workspace_name("", app_name="System Information"),
            "System-Information",
        )

    def test_falls_back_to_placeholder_when_all_else_fails(self):
        self.assertEqual(naming.derive_workspace_name("!!!", app_name="***"),
                         "workspace")

    def test_deduplicates_against_existing(self):
        self.assertEqual(
            naming.derive_workspace_name("code", existing=["code"]),
            "code-2",
        )
        self.assertEqual(
            naming.derive_workspace_name("code", existing=["code", "code-2"]),
            "code-3",
        )

    def test_deduplication_is_case_insensitive(self):
        self.assertEqual(
            naming.derive_workspace_name("Code", existing=["code"]),
            "Code-2",
        )

    def test_unique_false_allows_collision(self):
        self.assertEqual(
            naming.derive_workspace_name("code", existing=["code"],
                                         unique=False),
            "code",
        )

    def test_reserved_word_titles_are_escaped(self):
        result = naming.derive_workspace_name("next", app_name="Arc")
        self.assertTrue(naming.is_valid(result))
        self.assertEqual(result, "next-ws")

    def test_respects_title_strategy_env(self):
        self.set_env("AEROALFRED_TITLE_STRATEGY", "last-segment")
        self.assertEqual(
            naming.derive_workspace_name("Welcome — alfred-aerospace-workflow"),
            "alfred-aerospace-workflow",
        )

    def test_never_raises_for_arbitrary_titles(self):
        for title in ("", "   ", ",,,", "---", "___", "🎉", "a" * 500):
            result = naming.derive_workspace_name(title, app_name="App")
            self.assertTrue(naming.is_valid(result))


class DeduplicateTests(unittest.TestCase):

    def test_no_collision_returns_original(self):
        self.assertEqual(naming.deduplicate("a", ["b", "c"]), "a")

    def test_handles_empty_existing(self):
        self.assertEqual(naming.deduplicate("a", []), "a")
        self.assertEqual(naming.deduplicate("a", None), "a")


if __name__ == "__main__":
    unittest.main()
