"""CLI dispatch.

The load-bearing guarantee here: a Script Filter must ALWAYS print valid JSON.
If it doesn't, Alfred replaces the result list with an opaque parse error and
the user learns nothing about what actually went wrong.
"""

from __future__ import annotations

import io
import json
import unittest

from support import EnvIsolatedTestCase, FakeRunner, make_client

from aeroalfred import actions, cli
from aeroalfred.aerospace import Aerospace


class Explodes(object):
    """A client whose every method raises, to exercise error paths."""

    def __init__(self, exception):
        self.exception = exception

    def __getattr__(self, _name):
        def raiser(*args, **kwargs):
            raise self.exception
        return raiser


def run(argv, client=None):
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(argv, client=client, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


class DispatchTests(EnvIsolatedTestCase):

    def test_workspaces_emits_json(self):
        client, _ = make_client()
        code, out, _ = run(["workspaces", ""], client)
        self.assertEqual(code, 0)
        self.assertIn("Main", [i["title"] for i in json.loads(out)["items"]])

    def test_new_emits_json(self):
        client, _ = make_client()
        code, out, _ = run(["new", "scratch"], client)
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["items"])

    def test_windows_emits_json(self):
        client, _ = make_client()
        code, out, _ = run(["windows", ""], client)
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["items"]), 4)

    def test_query_argument_is_optional(self):
        client, _ = make_client()
        code, out, _ = run(["workspaces"], client)
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["items"])

    def test_no_arguments_prints_usage(self):
        code, _, err = run([])
        self.assertEqual(code, 2)
        self.assertIn("Usage", err)

    def test_help(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Usage", out)

    def test_unknown_command(self):
        code, _, err = run(["nonsense"])
        self.assertEqual(code, 2)
        self.assertIn("Unknown command", err)


class FilterErrorTests(EnvIsolatedTestCase):
    """Every failure must still leave Alfred with a parseable result list."""

    def test_missing_binary_becomes_a_readable_row(self):
        from aeroalfred.errors import AerospaceNotFound

        client = Explodes(AerospaceNotFound("no aerospace here"))
        code, out, _ = run(["workspaces", ""], client)
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["items"][0]["title"], "AeroSpace not found")
        self.assertIs(payload["items"][0]["valid"], False)

    def test_command_failure_becomes_a_readable_row(self):
        from aeroalfred.errors import AerospaceCommandError

        client = Explodes(AerospaceCommandError(["list-workspaces"], 2, "boom"))
        _, out, _ = run(["workspaces", ""], client)
        payload = json.loads(out)
        self.assertEqual(payload["items"][0]["title"], "AeroSpace command failed")
        self.assertIn("boom", payload["items"][0]["subtitle"])

    def test_unexpected_exception_still_yields_json(self):
        client = Explodes(RuntimeError("kaboom"))
        code, out, _ = run(["windows", ""], client)
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["items"][0]["title"], "Unexpected error")
        self.assertIn("kaboom", payload["items"][0]["subtitle"])

    def test_every_filter_survives_a_broken_client(self):
        client = Explodes(RuntimeError("nope"))
        for command in ("workspaces", "new", "windows"):
            code, out, _ = run([command, "q"], client)
            self.assertEqual(code, 0, command)
            json.loads(out)  # must not raise


class PerformTests(EnvIsolatedTestCase):

    def test_success_is_silent(self):
        client, runner = make_client()
        code, out, err = run(["perform", actions.encode(actions.FOCUS, "code")],
                             client)
        self.assertEqual(code, 0)
        # Empty stdout keeps Alfred's notification suppressed.
        self.assertEqual(out, "")
        self.assertEqual(err, "")
        self.assertEqual(runner.mutations, [["workspace", "--", "code"]])

    def test_aerospace_failure_reports_on_both_streams(self):
        runner = FakeRunner(fail_with=(2, "ERROR: something went wrong"))
        client = Aerospace(binary="/fake/aerospace", runner=runner)
        code, out, err = run(["perform", actions.encode(actions.FOCUS, "x")],
                             client)
        self.assertEqual(code, 1)
        self.assertIn("something went wrong", out)   # -> notification
        self.assertIn("something went wrong", err)   # -> Alfred debugger

    def test_malformed_payload_is_reported(self):
        client, runner = make_client()
        code, out, _ = run(["perform", "garbage"], client)
        self.assertEqual(code, 1)
        self.assertIn("Malformed", out)
        self.assertEqual(runner.mutations, [])

    def test_missing_payload_is_reported(self):
        client, _ = make_client()
        code, out, _ = run(["perform"], client)
        self.assertEqual(code, 1)
        self.assertTrue(out)


class DoctorTests(EnvIsolatedTestCase):

    def test_reports_environment(self):
        self.set_env("AEROSPACE_BIN", "/bin/sh")  # any real executable
        client, _ = make_client()
        code, out, _ = run(["doctor"], client)
        self.assertEqual(code, 0)
        self.assertIn("workspaces  : 3", out)
        self.assertIn("focused ws  : Main", out)
        self.assertIn("status      : ok", out)

    def test_reports_missing_binary(self):
        self.set_env("AEROSPACE_BIN", "/definitely/not/here")
        code, out, err = run(["doctor"])
        self.assertEqual(code, 1)
        self.assertIn("NOT FOUND", out)
        self.assertIn("AEROSPACE_BIN", err)


if __name__ == "__main__":
    unittest.main()
