"""The generated info.plist and the packaged .alfredworkflow bundle.

These are the tests that catch "it imports but silently does nothing" bugs:
dangling connections, keywords that call a command the CLI doesn't implement,
and item icons that reference files the bundle never shipped.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import tempfile
import unittest
import zipfile

from support import ROOT

import build
import spec

from aeroalfred import cli, commands


class PlistStructureTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.plist = build.build_plist()
        cls.uids = {obj["uid"] for obj in cls.plist["objects"]}

    def test_required_top_level_keys(self):
        for key in ("bundleid", "name", "objects", "connections", "version",
                    "createdby", "description", "readme"):
            self.assertIn(key, self.plist)

    def test_bundle_id_is_reverse_dns(self):
        self.assertRegex(self.plist["bundleid"], r"^[a-z0-9.-]+$")
        self.assertIn(".", self.plist["bundleid"])

    def test_object_uids_are_unique(self):
        uids = [obj["uid"] for obj in self.plist["objects"]]
        self.assertEqual(len(uids), len(set(uids)))

    def test_uids_are_deterministic(self):
        self.assertEqual(spec.uid("action.perform"), spec.uid("action.perform"))
        self.assertNotEqual(spec.uid("a"), spec.uid("b"))

    def test_uids_look_like_alfred_uuids(self):
        for uid in self.uids:
            self.assertRegex(
                uid, r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-"
                     r"[0-9A-F]{4}-[0-9A-F]{12}$"
            )

    def test_expected_keywords_exist(self):
        keywords = {
            obj["config"]["keyword"]
            for obj in self.plist["objects"]
            if obj["type"].endswith("scriptfilter")
        }
        self.assertEqual(keywords, {"ws", "wsn", "wsw", "wsp"})

    def test_every_connection_endpoint_resolves(self):
        for source, targets in self.plist["connections"].items():
            self.assertIn(source, self.uids)
            for target in targets:
                self.assertIn(target["destinationuid"], self.uids)

    def test_every_script_filter_reaches_the_perform_action(self):
        perform = spec.uid("action.perform")
        for obj in self.plist["objects"]:
            if not obj["type"].endswith("scriptfilter"):
                continue
            targets = self.plist["connections"].get(obj["uid"], [])
            self.assertIn(perform, [t["destinationuid"] for t in targets],
                          "{0} is not connected".format(obj["config"]["keyword"]))

    def test_perform_reaches_the_notification(self):
        targets = self.plist["connections"][spec.uid("action.perform")]
        self.assertIn(spec.uid("output.notification"),
                      [t["destinationuid"] for t in targets])

    def test_every_object_has_canvas_coordinates(self):
        for uid in self.uids:
            self.assertIn(uid, self.plist["uidata"])
            self.assertIn("xpos", self.plist["uidata"][uid])

    def test_scripts_use_bash_and_argv(self):
        for obj in self.plist["objects"]:
            config = obj["config"]
            if "script" not in config:
                continue
            self.assertEqual(config["type"], spec.LANG_BASH, obj["type"])
            self.assertEqual(config["scriptargtype"], spec.ARG_AS_ARGV,
                             obj["type"])

    def test_scripts_quote_the_query(self):
        # Unquoted "$1" would split a multi-word query into several argv items.
        for obj in self.plist["objects"]:
            script = obj["config"].get("script")
            if script:
                self.assertIn('"$1"', script)

    def test_scripts_pin_the_system_python(self):
        for obj in self.plist["objects"]:
            script = obj["config"].get("script")
            if script:
                self.assertIn("/usr/bin/python3", script)

    def test_every_script_calls_a_command_the_cli_implements(self):
        known = set(cli.FILTERS) | {"perform", "doctor"}
        for obj in self.plist["objects"]:
            script = obj["config"].get("script")
            if not script:
                continue
            command = script.split("run.py", 1)[1].split()[0]
            self.assertIn(command, known)

    def test_script_filters_accept_an_empty_query(self):
        for obj in self.plist["objects"]:
            if not obj["type"].endswith("scriptfilter"):
                continue
            config = obj["config"]
            self.assertEqual(config["argumenttype"], spec.ARG_OPTIONAL)
            # Otherwise `ws` with no query would never run and never list.
            self.assertFalse(config["argumenttreatemptyqueryasnil"])

    def test_script_filters_do_their_own_filtering(self):
        # Our Python code appends synthesized rows; Alfred must not drop them.
        for obj in self.plist["objects"]:
            if obj["type"].endswith("scriptfilter"):
                self.assertFalse(obj["config"]["alfredfiltersresults"])

    def test_notification_is_suppressed_on_success(self):
        notification = [o for o in self.plist["objects"]
                        if o["type"].endswith("notification")][0]
        self.assertTrue(notification["config"]["onlyshowifquerypopulated"])

    def test_user_configuration_variables_have_defaults(self):
        declared = {entry["variable"] for entry in
                    self.plist["userconfigurationconfig"]}
        self.assertTrue(declared.issubset(set(self.plist["variables"])))

    def test_plist_serialises(self):
        data = plistlib.dumps(self.plist, fmt=plistlib.FMT_XML, sort_keys=True)
        self.assertEqual(plistlib.loads(data)["bundleid"], spec.BUNDLE_ID)


class StagingTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="aeroalfred-stage-")
        cls.dest = os.path.join(cls.tmp, "workflow")
        build.stage(destination=cls.dest, verbose=False)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def path(self, *parts):
        return os.path.join(self.dest, *parts)

    def test_bundle_contains_the_entry_point_and_package(self):
        self.assertTrue(os.path.isfile(self.path("run.py")))
        self.assertTrue(os.path.isfile(self.path("info.plist")))
        self.assertTrue(os.path.isfile(self.path("aeroalfred", "cli.py")))

    def test_run_py_is_executable(self):
        self.assertTrue(os.access(self.path("run.py"), os.X_OK))

    def test_icons_are_generated(self):
        self.assertTrue(os.path.isfile(self.path("icon.png")))
        for name in ("workspace.png", "new.png"):
            self.assertTrue(os.path.isfile(self.path("icons", name)))

    def test_icons_are_real_pngs(self):
        with open(self.path("icon.png"), "rb") as handle:
            self.assertEqual(handle.read(8), b"\x89PNG\r\n\x1a\n")

    def test_item_icons_referenced_by_commands_exist(self):
        # The paths in commands.py are relative to the workflow root at runtime.
        for relative in (commands._WORKSPACE_ICON, commands._NEW_ICON):
            self.assertTrue(os.path.isfile(self.path(relative)),
                            "missing shipped icon: {0}".format(relative))

    def test_no_pycache_is_shipped(self):
        for directory, dirnames, _ in os.walk(self.dest):
            self.assertNotIn("__pycache__", dirnames)

    def test_staged_plist_parses(self):
        with open(self.path("info.plist"), "rb") as handle:
            self.assertEqual(plistlib.load(handle)["bundleid"], spec.BUNDLE_ID)

    def test_staging_is_idempotent(self):
        second = os.path.join(self.tmp, "workflow2")
        build.stage(destination=second, verbose=False)
        with open(self.path("info.plist"), "rb") as a:
            with open(os.path.join(second, "info.plist"), "rb") as b:
                self.assertEqual(a.read(), b.read())


class PackagingTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="aeroalfred-pkg-")
        source = os.path.join(cls.tmp, "workflow")
        build.stage(destination=source, verbose=False)
        cls.bundle = build.package(
            destination=os.path.join(cls.tmp, "dist"), source=source,
            verbose=False,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_bundle_extension(self):
        self.assertTrue(self.bundle.endswith(".alfredworkflow"))

    def test_bundle_is_a_zip_with_a_flat_root(self):
        with zipfile.ZipFile(self.bundle) as archive:
            names = archive.namelist()
        # Alfred requires info.plist at the archive root, not nested.
        self.assertIn("info.plist", names)
        self.assertIn("run.py", names)
        self.assertIn("icon.png", names)
        self.assertIn("aeroalfred/cli.py", names)

    def test_bundle_excludes_build_artefacts(self):
        with zipfile.ZipFile(self.bundle) as archive:
            names = archive.namelist()
        self.assertFalse([n for n in names if "__pycache__" in n])
        self.assertFalse([n for n in names if n.endswith(".pyc")])
        self.assertFalse([n for n in names if ".DS_Store" in n])

    def test_plist_inside_the_bundle_is_valid(self):
        with zipfile.ZipFile(self.bundle) as archive:
            data = archive.read("info.plist")
        self.assertEqual(plistlib.loads(data)["name"], spec.NAME)

    def test_packaging_is_reproducible(self):
        other_dir = os.path.join(self.tmp, "dist2")
        source = os.path.join(self.tmp, "workflow")
        again = build.package(destination=other_dir, source=source,
                              verbose=False)
        with open(self.bundle, "rb") as a, open(again, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_run_py_keeps_its_executable_bit_in_the_archive(self):
        with zipfile.ZipFile(self.bundle) as archive:
            mode = archive.getinfo("run.py").external_attr >> 16
        self.assertTrue(mode & 0o100)


class RepositoryTests(unittest.TestCase):

    def test_no_pip_dependencies_are_imported(self):
        """The workflow must run on a stock /usr/bin/python3."""
        allowed_third_party = set()
        package = os.path.join(ROOT, "src", "aeroalfred")
        for name in os.listdir(package):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(package, name)) as handle:
                for line in handle:
                    line = line.strip()
                    if line.startswith("import ") or line.startswith("from "):
                        module = line.split()[1].split(".")[0]
                        if module in ("__future__",) or module.startswith("."):
                            continue
                        self.assertNotIn(module, allowed_third_party)

    def test_gitignore_excludes_build_output(self):
        with open(os.path.join(ROOT, ".gitignore")) as handle:
            content = handle.read()
        for pattern in ("build/", "dist/", "__pycache__/"):
            self.assertIn(pattern, content)


if __name__ == "__main__":
    unittest.main()
