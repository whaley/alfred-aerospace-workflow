"""The four user-facing behaviours, driven through a fake AeroSpace."""

from __future__ import annotations

import json
import unittest

from support import EnvIsolatedTestCase, FakeRunner, make_client

from aeroalfred import actions, commands
from aeroalfred.errors import AeroAlfredError, InvalidWorkspaceName


def titles(feedback):
    return [item.title for item in feedback.items]


def args_of(feedback):
    return [json.loads(item.arg) for item in feedback.items if item.arg]


class WorkspacesFilterTests(EnvIsolatedTestCase):
    """`ws` -- requirements 1 and 2: list all, switch to one."""

    def test_lists_every_workspace(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "")
        self.assertEqual(titles(feedback), ["Main", "chat", "code"])

    def test_focused_workspace_sorts_first(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "")
        self.assertEqual(feedback.items[0].title, "Main")
        self.assertIn("focused", feedback.items[0].subtitle)

    def test_subtitle_reports_window_count_and_monitor(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "")
        main = feedback.items[0]
        self.assertIn("2 windows", main.subtitle)
        self.assertIn("LS32D80xU", main.subtitle)

    def test_singular_window_count(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "chat")
        self.assertIn("1 window ", feedback.items[0].subtitle + " ")

    def test_enter_emits_a_focus_action(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "code")
        payload = json.loads(feedback.items[0].arg)
        self.assertEqual(payload,
                         {"action": actions.FOCUS, "workspace": "code"})

    def test_cmd_modifier_moves_the_focused_window(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "code")
        mod = feedback.items[0].mods["cmd"]
        self.assertEqual(json.loads(mod["arg"]),
                         {"action": actions.MOVE_FOCUSED, "workspace": "code"})

    def test_query_filters_the_list(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "ch")
        self.assertEqual(feedback.items[0].title, "chat")

    def test_subsequence_matching(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "cd")
        self.assertIn("code", titles(feedback))

    def test_unmatched_query_offers_creation(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "brandnew")
        self.assertEqual(len(feedback), 1)
        self.assertIn("Create workspace", feedback.items[0].title)
        self.assertEqual(
            json.loads(feedback.items[0].arg),
            {"action": actions.FOCUS, "workspace": "brandnew"},
        )

    def test_existing_name_does_not_offer_creation(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "code")
        self.assertEqual(
            [t for t in titles(feedback) if t.startswith("Create")], []
        )

    def test_invalid_name_does_not_offer_creation(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "has space")
        self.assertEqual(
            [t for t in titles(feedback) if t.startswith("Create")], []
        )

    def test_partial_match_still_offers_creation(self):
        # "cod" matches "code" but is itself a legal new name.
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "cod")
        self.assertIn("code", titles(feedback))
        self.assertTrue(any(t.startswith("Create") for t in titles(feedback)))

    def test_show_empty_disabled_hides_empty_workspaces(self):
        runner = FakeRunner(windows=[])
        client, _ = make_client(runner=runner)
        self.set_env("AEROALFRED_SHOW_EMPTY", "0")
        feedback = commands.workspaces_filter(client, "")
        # Only the focused workspace survives when everything is empty.
        self.assertEqual(titles(feedback), ["Main"])

    def test_no_workspaces_reports_clearly(self):
        runner = FakeRunner(workspaces=[], windows=[])
        client, _ = make_client(runner=runner)
        feedback = commands.workspaces_filter(client, "")
        self.assertEqual(len(feedback), 1)
        self.assertFalse(feedback.items[0].valid)
        self.assertIn("No workspaces", feedback.items[0].title)

    def test_unmatched_invalid_query_does_not_blame_aerospace(self):
        # Workspaces exist; the query is just not a legal name. Reporting
        # "is AeroSpace running?" here would send the user down a rabbit hole.
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "has space")
        self.assertEqual(len(feedback), 1)
        self.assertFalse(feedback.items[0].valid)
        self.assertIn("No workspace matches", feedback.items[0].title)
        self.assertIn("whitespace", feedback.items[0].subtitle.lower())
        self.assertNotIn("Is it running", feedback.items[0].subtitle)

    def test_unmatched_valid_query_offers_creation_instead_of_warning(self):
        client, _ = make_client()
        feedback = commands.workspaces_filter(client, "zzz")
        self.assertTrue(feedback.items[0].valid)
        self.assertIn("Create workspace", feedback.items[0].title)

    def test_filter_performs_no_mutations(self):
        client, runner = make_client()
        commands.workspaces_filter(client, "code")
        self.assertEqual(runner.mutations, [])


class NewWorkspaceFilterTests(EnvIsolatedTestCase):
    """`wsn` -- requirement 3: create a workspace with a custom name."""

    def test_empty_query_prompts(self):
        client, _ = make_client()
        feedback = commands.new_workspace_filter(client, "")
        self.assertEqual(len(feedback), 1)
        self.assertFalse(feedback.items[0].valid)

    def test_valid_new_name_offers_creation(self):
        client, _ = make_client()
        feedback = commands.new_workspace_filter(client, "scratch")
        self.assertTrue(feedback.items[0].valid)
        self.assertEqual(
            json.loads(feedback.items[0].arg),
            {"action": actions.FOCUS, "workspace": "scratch"},
        )

    def test_cmd_modifier_brings_the_focused_window(self):
        client, _ = make_client()
        feedback = commands.new_workspace_filter(client, "scratch")
        mod = feedback.items[0].mods["cmd"]
        self.assertEqual(json.loads(mod["arg"])["action"], actions.MOVE_FOCUSED)

    def test_invalid_name_is_rejected_with_a_reason(self):
        client, _ = make_client()
        feedback = commands.new_workspace_filter(client, "has space")
        self.assertFalse(feedback.items[0].valid)
        self.assertIn("Whitespace", feedback.items[0].subtitle)

    def test_invalid_name_offers_a_sanitised_alternative(self):
        client, _ = make_client()
        feedback = commands.new_workspace_filter(client, "has space")
        self.assertEqual(len(feedback), 2)
        self.assertTrue(feedback.items[1].valid)
        self.assertEqual(
            json.loads(feedback.items[1].arg)["workspace"], "has-space"
        )

    def test_reserved_name_is_rejected(self):
        client, _ = make_client()
        feedback = commands.new_workspace_filter(client, "next")
        self.assertFalse(feedback.items[0].valid)
        self.assertIn("reserved", feedback.items[0].subtitle)

    def test_existing_name_switches_instead_of_creating(self):
        client, _ = make_client()
        feedback = commands.new_workspace_filter(client, "code")
        self.assertIn("already exists", feedback.items[0].subtitle)
        self.assertEqual(
            json.loads(feedback.items[0].arg),
            {"action": actions.FOCUS, "workspace": "code"},
        )

    def test_existing_match_is_case_insensitive_and_uses_real_name(self):
        client, _ = make_client()
        feedback = commands.new_workspace_filter(client, "CODE")
        self.assertEqual(
            json.loads(feedback.items[0].arg)["workspace"], "code"
        )

    def test_filter_performs_no_mutations(self):
        client, runner = make_client()
        commands.new_workspace_filter(client, "scratch")
        self.assertEqual(runner.mutations, [])


class WindowWorkspaceFilterTests(EnvIsolatedTestCase):
    """`wsw` -- requirement 4: name a workspace after a window title."""

    def test_lists_every_window(self):
        client, _ = make_client()
        feedback = commands.window_workspace_filter(client, "")
        self.assertEqual(len(feedback), 4)

    def test_untitled_window_shows_app_name(self):
        client, _ = make_client()
        feedback = commands.window_workspace_filter(client, "System")
        self.assertEqual(feedback.items[0].title, "System Information")

    def test_action_moves_that_window_to_the_derived_name(self):
        client, _ = make_client()
        feedback = commands.window_workspace_filter(client, "weechat")
        payload = json.loads(feedback.items[0].arg)
        self.assertEqual(payload["action"], actions.MOVE_WINDOW)
        self.assertEqual(payload["window_id"], 2323)
        self.assertEqual(payload["workspace"], "weechat")

    def test_derived_name_is_sanitised(self):
        client, _ = make_client()
        feedback = commands.window_workspace_filter(client, "Kagi")
        payload = json.loads(feedback.items[0].arg)
        self.assertNotIn(" ", payload["workspace"])
        self.assertEqual(payload["workspace"], "claude-create-agent-Kagi-Search")

    def test_every_derived_name_is_legal(self):
        client, _ = make_client()
        feedback = commands.window_workspace_filter(client, "")
        for payload in args_of(feedback):
            self.assertNotIn(" ", payload["workspace"])
            self.assertNotIn(",", payload["workspace"])
            self.assertFalse(payload["workspace"].startswith("-"))

    def test_uses_the_app_icon(self):
        client, _ = make_client()
        feedback = commands.window_workspace_filter(client, "Arc")
        self.assertEqual(
            feedback.items[0].icon,
            {"type": "fileicon", "path": "/Applications/Arc.app"},
        )

    def test_subtitle_distinguishes_new_from_existing(self):
        client, _ = make_client()
        feedback = commands.window_workspace_filter(client, "Kagi")
        self.assertIn("Create workspace", feedback.items[0].subtitle)

    def test_existing_workspace_is_reported_as_a_move(self):
        # A window titled "code" collides with the existing "code" workspace.
        runner = FakeRunner(windows=[{
            "window-id": 9, "window-title": "code", "workspace": "Main",
            "app-name": "Term", "app-bundle-path": "/Applications/Term.app",
        }])
        client, _ = make_client(runner=runner)
        feedback = commands.window_workspace_filter(client, "")
        self.assertIn("existing workspace", feedback.items[0].subtitle)
        self.assertEqual(
            json.loads(feedback.items[0].arg)["workspace"], "code"
        )

    def test_query_matches_app_name(self):
        client, _ = make_client()
        feedback = commands.window_workspace_filter(client, "kitty")
        self.assertEqual(len(feedback), 1)
        self.assertEqual(feedback.items[0].title, "weechat")

    def test_no_windows_reports_clearly(self):
        runner = FakeRunner(windows=[])
        client, _ = make_client(runner=runner)
        feedback = commands.window_workspace_filter(client, "")
        self.assertFalse(feedback.items[0].valid)
        self.assertIn("No managed windows", feedback.items[0].title)

    def test_no_matching_windows_reports_clearly(self):
        client, _ = make_client()
        feedback = commands.window_workspace_filter(client, "zzzzz")
        self.assertFalse(feedback.items[0].valid)
        self.assertIn("No matching windows", feedback.items[0].title)

    def test_title_strategy_env_changes_derived_names(self):
        self.set_env("AEROALFRED_TITLE_STRATEGY", "first-segment")
        client, _ = make_client()
        feedback = commands.window_workspace_filter(client, "Kagi")
        self.assertEqual(
            json.loads(feedback.items[0].arg)["workspace"],
            "claude-create-agent",
        )

    def test_filter_performs_no_mutations(self):
        client, runner = make_client()
        commands.window_workspace_filter(client, "")
        self.assertEqual(runner.mutations, [])


class PullWindowFilterTests(EnvIsolatedTestCase):
    """`wsp` -- move a window from another workspace into the focused one."""

    def test_lists_only_windows_outside_the_focused_workspace(self):
        # Two of the four default windows live on "Main", the focused one.
        client, _ = make_client()
        feedback = commands.pull_window_filter(client, "")
        self.assertEqual(len(feedback), 2)
        self.assertEqual(
            sorted(titles(feedback)),
            ["Welcome — alfred-aerospace-workflow", "weechat"],
        )

    def test_action_moves_that_window_to_the_focused_workspace(self):
        client, _ = make_client()
        feedback = commands.pull_window_filter(client, "weechat")
        payload = json.loads(feedback.items[0].arg)
        self.assertEqual(payload, {"action": actions.MOVE_WINDOW,
                                   "workspace": "Main", "window_id": 2323})

    def test_subtitle_names_the_source_workspace(self):
        client, _ = make_client()
        feedback = commands.pull_window_filter(client, "weechat")
        self.assertIn("chat", feedback.items[0].subtitle)
        self.assertIn("kitty", feedback.items[0].subtitle)

    def test_cmd_modifier_goes_to_the_window_instead(self):
        client, _ = make_client()
        feedback = commands.pull_window_filter(client, "weechat")
        mod = feedback.items[0].mods["cmd"]
        self.assertEqual(json.loads(mod["arg"]),
                         {"action": actions.FOCUS, "workspace": "chat"})

    def test_query_matches_the_source_workspace_name(self):
        client, _ = make_client()
        feedback = commands.pull_window_filter(client, "chat")
        self.assertEqual(titles(feedback), ["weechat"])

    def test_query_matches_app_name(self):
        client, _ = make_client()
        feedback = commands.pull_window_filter(client, "Code")
        self.assertEqual(titles(feedback),
                         ["Welcome — alfred-aerospace-workflow"])

    def test_untitled_window_shows_app_name(self):
        runner = FakeRunner(windows=[{
            "window-id": 7, "window-title": "", "workspace": "code",
            "app-name": "System Information", "app-bundle-path": "",
        }])
        client, _ = make_client(runner=runner)
        feedback = commands.pull_window_filter(client, "")
        self.assertEqual(feedback.items[0].title, "System Information")

    def test_window_without_a_bundle_path_falls_back_to_our_icon(self):
        runner = FakeRunner(windows=[{
            "window-id": 7, "window-title": "ghost", "workspace": "code",
            "app-name": "Ghost", "app-bundle-path": "",
        }])
        client, _ = make_client(runner=runner)
        feedback = commands.pull_window_filter(client, "")
        self.assertEqual(feedback.items[0].icon,
                         {"path": commands._WORKSPACE_ICON})

    def test_uses_the_app_icon(self):
        client, _ = make_client()
        feedback = commands.pull_window_filter(client, "weechat")
        self.assertEqual(feedback.items[0].icon,
                         {"type": "fileicon", "path": "/Applications/kitty.app"})

    def test_everything_already_here_is_reported_distinctly(self):
        runner = FakeRunner(windows=[{
            "window-id": 1, "window-title": "here", "workspace": "Main",
            "app-name": "Term", "app-bundle-path": "/Applications/Term.app",
        }])
        client, _ = make_client(runner=runner)
        feedback = commands.pull_window_filter(client, "")
        self.assertEqual(len(feedback), 1)
        self.assertFalse(feedback.items[0].valid)
        self.assertIn("already here", feedback.items[0].title)
        self.assertIn("Main", feedback.items[0].subtitle)

    def test_no_windows_reports_clearly(self):
        runner = FakeRunner(windows=[])
        client, _ = make_client(runner=runner)
        feedback = commands.pull_window_filter(client, "")
        self.assertFalse(feedback.items[0].valid)
        self.assertIn("No managed windows", feedback.items[0].title)

    def test_no_matching_windows_reports_clearly(self):
        client, _ = make_client()
        feedback = commands.pull_window_filter(client, "zzzzz")
        self.assertEqual(len(feedback), 1)
        self.assertFalse(feedback.items[0].valid)
        self.assertIn("No matching windows", feedback.items[0].title)

    def test_no_focused_workspace_reports_clearly(self):
        # AeroSpace not running, or reporting nothing focused: emitting a move
        # action with an empty workspace name would fail later and confusingly.
        runner = FakeRunner(workspaces=[
            {"workspace": "Main", "workspace-is-focused": False,
             "workspace-is-visible": True, "monitor-id": 1,
             "monitor-name": "LS32D80xU"},
        ])
        client, _ = make_client(runner=runner)
        feedback = commands.pull_window_filter(client, "")
        self.assertEqual(len(feedback), 1)
        self.assertFalse(feedback.items[0].valid)
        self.assertIn("No focused workspace", feedback.items[0].title)

    def test_filter_performs_no_mutations(self):
        client, runner = make_client()
        commands.pull_window_filter(client, "")
        self.assertEqual(runner.mutations, [])


class PerformTests(EnvIsolatedTestCase):

    def test_focus_calls_workspace(self):
        client, runner = make_client()
        result = commands.perform(client, actions.encode(actions.FOCUS, "code"))
        self.assertEqual(result, "")
        self.assertEqual(runner.mutations, [["workspace", "--", "code"]])

    def test_move_focused_calls_move_node(self):
        client, runner = make_client()
        commands.perform(client, actions.encode(actions.MOVE_FOCUSED, "code"))
        self.assertEqual(
            runner.mutations,
            [["move-node-to-workspace", "--focus-follows-window", "--", "code"]],
        )

    def test_move_window_includes_window_id(self):
        client, runner = make_client()
        commands.perform(
            client, actions.encode(actions.MOVE_WINDOW, "code", window_id=42)
        )
        self.assertEqual(
            runner.mutations,
            [["move-node-to-workspace", "--window-id", "42",
              "--focus-follows-window", "--", "code"]],
        )

    def test_follow_can_be_disabled(self):
        self.set_env("AEROALFRED_FOLLOW_WINDOW", "0")
        client, runner = make_client()
        commands.perform(client, actions.encode(actions.MOVE_FOCUSED, "code"))
        self.assertNotIn("--focus-follows-window", runner.mutations[0])

    def test_invalid_workspace_name_is_caught_before_shelling_out(self):
        client, runner = make_client()
        payload = json.dumps({"action": actions.FOCUS, "workspace": "bad name"})
        with self.assertRaises(InvalidWorkspaceName):
            commands.perform(client, payload)
        self.assertEqual(runner.mutations, [])

    def test_missing_window_id_is_rejected(self):
        client, _ = make_client()
        payload = json.dumps({"action": actions.MOVE_WINDOW, "workspace": "a"})
        with self.assertRaises(AeroAlfredError):
            commands.perform(client, payload)

    def test_garbage_payload_is_rejected(self):
        client, _ = make_client()
        with self.assertRaises(AeroAlfredError):
            commands.perform(client, "not json at all")


if __name__ == "__main__":
    unittest.main()
