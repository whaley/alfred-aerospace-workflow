"""Build the .alfredworkflow bundle.

    python3 tools/build.py            # build into dist/
    python3 tools/build.py --install  # build, then hand it to Alfred to import

The output is byte-for-byte reproducible: object UIDs come from uuid5, and every
zip entry gets a fixed timestamp.
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import stat
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import icons  # noqa: E402
import spec  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
BUILD_DIR = os.path.join(ROOT, "build", "workflow")
DIST_DIR = os.path.join(ROOT, "dist")
BUNDLE_NAME = "{0}.alfredworkflow".format(spec.NAME)

#: Fixed zip timestamp (the earliest the format allows) for reproducibility.
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


# ------------------------------------------------------------------- plist

def build_plist():
    """Assemble the info.plist dictionary from tools/spec.py."""
    objects = []
    uidata = {}
    by_name = {}

    for name, position in spec.POSITIONS.items():
        by_name[name] = spec.uid(name)

    for obj in spec.OBJECTS:
        objects.append(
            {
                "config": obj["config"],
                "type": obj["type"],
                "uid": obj["uid"],
                "version": obj["version"],
            }
        )

    for name, (xpos, ypos) in spec.POSITIONS.items():
        entry = {"xpos": float(xpos), "ypos": float(ypos)}
        note = spec.NOTES.get(name)
        if note:
            entry["note"] = note
        uidata[spec.uid(name)] = entry

    connections = {}
    for source, destination in spec.CONNECTIONS:
        connections.setdefault(spec.uid(source), []).append(
            {
                "destinationuid": spec.uid(destination),
                "modifiers": 0,
                "modifiersubtext": "",
                "vitoclose": False,
            }
        )

    return {
        "bundleid": spec.BUNDLE_ID,
        "connections": connections,
        "createdby": spec.CREATED_BY,
        "description": spec.DESCRIPTION,
        "disabled": False,
        "name": spec.NAME,
        "objects": objects,
        "readme": spec.README,
        "uidata": uidata,
        "userconfigurationconfig": spec.USER_CONFIGURATION,
        "variables": spec.VARIABLES,
        "variablesdontexport": [],
        "version": spec.VERSION,
        "webaddress": spec.WEB_ADDRESS,
    }


def write_plist(destination):
    path = os.path.join(destination, "info.plist")
    with open(path, "wb") as handle:
        plistlib.dump(build_plist(), handle, fmt=plistlib.FMT_XML,
                      sort_keys=True)
    return path


# ------------------------------------------------------------------- stage

def stage(destination=BUILD_DIR, verbose=True):
    """Assemble the complete workflow folder. Returns its path."""
    if os.path.exists(destination):
        shutil.rmtree(destination)
    os.makedirs(destination)

    shutil.copytree(
        os.path.join(SRC, "aeroalfred"),
        os.path.join(destination, "aeroalfred"),
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    run_py = os.path.join(destination, "run.py")
    shutil.copy2(os.path.join(SRC, "run.py"), run_py)
    os.chmod(run_py, os.stat(run_py).st_mode | stat.S_IXUSR | stat.S_IXGRP
             | stat.S_IXOTH)

    icons.generate_all(destination)
    write_plist(destination)

    if verbose:
        print("staged workflow -> {0}".format(_relative(destination)))
    return destination


# ------------------------------------------------------------------- package

def package(destination=DIST_DIR, source=BUILD_DIR, verbose=True):
    """Zip a staged folder into dist/<name>.alfredworkflow."""
    os.makedirs(destination, exist_ok=True)
    bundle = os.path.join(destination, BUNDLE_NAME)
    if os.path.exists(bundle):
        os.remove(bundle)

    entries = []
    for directory, dirnames, filenames in os.walk(source):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for filename in sorted(filenames):
            if filename.endswith(".pyc") or filename == ".DS_Store":
                continue
            absolute = os.path.join(directory, filename)
            entries.append((absolute, os.path.relpath(absolute, source)))

    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for absolute, relative in sorted(entries, key=lambda pair: pair[1]):
            info = zipfile.ZipInfo(relative, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = os.stat(absolute).st_mode
            info.external_attr = (mode & 0xFFFF) << 16
            with open(absolute, "rb") as handle:
                archive.writestr(info, handle.read())

    if verbose:
        size = os.path.getsize(bundle) / 1024.0
        print("packaged {0} files -> {1} ({2:.1f} KB)".format(
            len(entries), _relative(bundle), size))
    return bundle


def build(install=False, verbose=True):
    stage(verbose=verbose)
    bundle = package(verbose=verbose)
    if install:
        subprocess.check_call(["open", bundle])
        if verbose:
            print("handed to Alfred for import")
    return bundle


def _relative(path):
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:  # pragma: no cover - different volume
        return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install",
        action="store_true",
        help="open the built bundle so Alfred imports it",
    )
    parser.add_argument(
        "--stage-only",
        action="store_true",
        help="assemble build/workflow without zipping",
    )
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    verbose = not args.quiet
    if args.stage_only:
        stage(verbose=verbose)
        return 0
    build(install=args.install, verbose=verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
