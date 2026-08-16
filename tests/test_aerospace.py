"""The `aerospace` CLI wrapper: argv construction, JSON parsing, discovery."""

from __future__ import annotations

import unittest

from support import EnvIsolatedTestCase, FakeRunner, Result, make_client

from aeroalfred import aerospace
from aeroalfred.errors import AerospaceCommandError, AerospaceNotFound


class ListingTests(EnvIsolatedTestCase):

    def test_list_workspaces_parses_all_fields(self):
        client, _ = make_client()
        workspaces = client.list_workspaces()

        self.assertEqual([w.name for w in workspaces], ["Main", "code", "chat"])
        main = workspaces[0]
        self.assertTrue(main.is_focused)
        self.assertTrue(main.is_visible)
        self.assertEqual(main.monitor_name, "LS32D80xU")
        self.assertEqual(main.monitor_id, 1)

    def test_list_workspaces_counts_windows(self):
        client, _ = make_client()
        counts = {w.name: w.window_count for w in client.list_workspaces()}
        self.assertEqual(counts, {"Main": 2, "code": 1, "chat": 1})

    def test_window_counts_can_be_skipped(self):
        client, runner = make_client()
        client.list_workspaces(with_window_counts=False)
        self.assertNotIn("list-windows", [call[1] for call in runner.calls])

    def test_list_windows_parses_fields(self):
        client, _ = make_client()
        windows = client.list_windows()
        self.assertEqual(len(windows), 4)
        self.assertEqual(windows[0].window_id, 1966)
        self.assertEqual(windows[0].app_name, "Arc")
        self.assertEqual(windows[0].app_bundle_path, "/Applications/Arc.app")

    def test_focused_workspace(self):
        client, _ = make_client()
        self.assertEqual(client.focused_workspace(), "Main")

    def test_workspace_names(self):
        client, _ = make_client()
        self.assertEqual(client.workspace_names(), ["Main", "code", "chat"])

    def test_empty_output_is_not_an_error(self):
        client, _ = make_client(runner=lambda argv: Result(stdout="  "))
        self.assertEqual(client.list_workspaces(with_window_counts=False), [])

    def test_focused_workspace_with_no_result(self):
        client, _ = make_client(runner=lambda argv: Result(stdout="[]"))
        self.assertEqual(client.focused_workspace(), "")

    def test_display_title_falls_back_to_app_name(self):
        client, _ = make_client()
        untitled = [w for w in client.list_windows() if not w.title][0]
        self.assertEqual(untitled.display_title, "System Information")


class ArgvTests(EnvIsolatedTestCase):
    """Guards the flags that are easy to get subtly wrong."""

    def test_reads_request_json(self):
        client, runner = make_client()
        client.list_workspaces(with_window_counts=False)
        self.assertIn("--json", runner.calls[0])

    def test_focus_workspace_uses_double_dash(self):
        client, runner = make_client()
        client.focus_workspace("next")
        # Without `--`, AeroSpace would treat "next" as relative motion.
        self.assertEqual(runner.calls[0][1:], ["workspace", "--", "next"])

    def test_move_window_uses_double_dash_and_window_id(self):
        client, runner = make_client()
        client.move_window_to_workspace(2474, "prev", follow=True)
        self.assertEqual(
            runner.calls[0][1:],
            ["move-node-to-workspace", "--window-id", "2474",
             "--focus-follows-window", "--", "prev"],
        )

    def test_move_window_without_follow(self):
        client, runner = make_client()
        client.move_window_to_workspace(1, "code", follow=False)
        self.assertNotIn("--focus-follows-window", runner.calls[0])

    def test_move_focused_window(self):
        client, runner = make_client()
        client.move_focused_window_to_workspace("code", follow=True)
        self.assertEqual(
            runner.calls[0][1:],
            ["move-node-to-workspace", "--focus-follows-window", "--", "code"],
        )

    def test_binary_is_argv_zero(self):
        client, runner = make_client()
        client.focus_workspace("code")
        self.assertEqual(runner.calls[0][0], "/fake/bin/aerospace")


class FailureTests(EnvIsolatedTestCase):

    def test_non_zero_exit_raises_with_stderr(self):
        runner = FakeRunner(
            fail_with=(2, "ERROR: Whitespace characters are forbidden")
        )
        client, _ = make_client(runner=runner)
        with self.assertRaises(AerospaceCommandError) as caught:
            client.focus_workspace("bad")
        self.assertIn("Whitespace", str(caught.exception))
        self.assertEqual(caught.exception.returncode, 2)

    def test_missing_stderr_still_produces_a_message(self):
        runner = FakeRunner(fail_with=(1, ""))
        client, _ = make_client(runner=runner)
        with self.assertRaises(AerospaceCommandError) as caught:
            client.focus_workspace("x")
        self.assertIn("no output on stderr", str(caught.exception))

    def test_malformed_json_raises(self):
        client, _ = make_client(runner=lambda argv: Result(stdout="{not json"))
        with self.assertRaises(AerospaceCommandError):
            client.list_windows()


class FindBinaryTests(EnvIsolatedTestCase):

    def test_prefers_explicit_override(self):
        self.set_env("AEROSPACE_BIN", "/custom/aerospace")
        found = aerospace.find_binary(
            which=lambda _: "/opt/homebrew/bin/aerospace",
            isfile=lambda p: p == "/custom/aerospace",
        )
        self.assertEqual(found, "/custom/aerospace")

    def test_bad_override_raises_clear_error(self):
        self.set_env("AEROSPACE_BIN", "/missing/aerospace")
        with self.assertRaises(AerospaceNotFound) as caught:
            aerospace.find_binary(which=lambda _: None, isfile=lambda p: False)
        self.assertIn("AEROSPACE_BIN", str(caught.exception))

    def test_uses_path_when_available(self):
        found = aerospace.find_binary(
            which=lambda _: "/somewhere/aerospace",
            isfile=lambda p: True,
        )
        self.assertEqual(found, "/somewhere/aerospace")

    def test_falls_back_to_homebrew_when_path_is_bare(self):
        # This is the real Alfred case: a minimal PATH without /opt/homebrew.
        found = aerospace.find_binary(
            which=lambda _: None,
            isfile=lambda p: p == "/opt/homebrew/bin/aerospace",
        )
        self.assertEqual(found, "/opt/homebrew/bin/aerospace")

    def test_extra_paths_win_over_defaults(self):
        found = aerospace.find_binary(
            extra_paths=["/first/aerospace"],
            which=lambda _: None,
            isfile=lambda p: True,
        )
        self.assertEqual(found, "/first/aerospace")

    def test_raises_actionable_error_when_absent(self):
        with self.assertRaises(AerospaceNotFound) as caught:
            aerospace.find_binary(which=lambda _: None, isfile=lambda p: False)
        self.assertIn("AEROSPACE_BIN", str(caught.exception))

    def test_binary_is_resolved_lazily(self):
        # Constructing a client must not touch the filesystem.
        aerospace.Aerospace(runner=lambda argv: Result())


if __name__ == "__main__":
    unittest.main()
