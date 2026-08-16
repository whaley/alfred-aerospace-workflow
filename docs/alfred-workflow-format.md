# Alfred workflow format notes

Alfred's `info.plist` schema is not officially documented. Everything below was
confirmed by reading the plists of **working workflows already installed** on
this machine, then reproduced here. When in doubt, do the same:

```bash
/usr/bin/python3 -c '
import plistlib, sys
print(plistlib.load(open(sys.argv[1], "rb")))
' "$HOME/Library/Application Support/Alfred/Alfred.alfredpreferences/workflows/<id>/info.plist"
```

## What a workflow is

A directory containing `info.plist`, an `icon.png`, and any scripts/assets,
zipped with **`info.plist` at the archive root** (not nested in a folder) and
given the `.alfredworkflow` extension. Opening that file makes Alfred import it.

## The magic integers

These are the values that are easy to get wrong and hard to debug.

### `config.type` — script language

| Value | Language |
| --- | --- |
| `0` | `/bin/bash` |
| `7` | `/usr/bin/osascript` (JavaScript) |

Verified: Menu Bar Search uses `type: 0` with an inline `./menu …` command;
Vitor's Shortcuts workflow uses `type: 7` with JXA source.

**This project always uses `0`.** A one-line bash shim invokes Python
explicitly, which sidesteps the rest of the enum entirely and pins the
interpreter:

```bash
"${AEROALFRED_PYTHON:-/usr/bin/python3}" run.py workspaces "$1"
```

### `config.scriptargtype` — how the query arrives

| Value | Behaviour |
| --- | --- |
| `0` | Textual `{query}` substitution into the script body |
| `1` | Passed as `argv`, i.e. `"$1"` |

**Use `1`.** With `0`, a query containing a quote or backtick is interpolated
straight into the shell command. Argv passing removes that whole class of bug.

### `config.argumenttype` — keyword argument requirement

| Value | Behaviour |
| --- | --- |
| `0` | Argument required |
| `1` | Argument optional |
| `2` | No argument |

`ws` needs `1` so that a bare keyword lists everything. Pair it with
`argumenttreatemptyqueryasnil: false`, or the empty query never reaches the
script.

### `config.escaping`

`102` is the common default (backquotes, quotes, backslashes, dollars). Only
meaningful when `scriptargtype` is `0`; harmless otherwise.

## Working directory

Alfred runs scripts with the **workflow folder as the working directory**. That
is why `./run.py` and relative icon paths like `icons/workspace.png` resolve.

## PATH is minimal

Alfred does **not** inherit your shell's PATH. `/opt/homebrew/bin` is typically
absent, so `aerospace` is not on PATH. `src/aeroalfred/aerospace.py:find_binary`
handles this by checking, in order:

1. `$AEROSPACE_BIN` (a workflow variable)
2. `shutil.which("aerospace")`
3. Known install locations (Homebrew ARM/Intel, `~/.local/bin`, the app bundle)

`tests/test_aerospace.py` covers each branch.

## Script Filter JSON

Printed on stdout. [Official docs.](https://www.alfredapp.com/help/workflows/inputs/script-filter/json/)

```json
{
  "items": [
    {
      "uid": "workspace/Main",
      "title": "Main",
      "subtitle": "● focused · 5 windows",
      "arg": "{\"action\":\"focus\",\"workspace\":\"Main\"}",
      "valid": true,
      "autocomplete": "Main",
      "icon": { "path": "icons/workspace.png" },
      "mods": {
        "cmd": { "subtitle": "Move the focused window here", "arg": "…" }
      }
    }
  ],
  "skipknowledge": true
}
```

Things worth knowing:

- **A Script Filter must always print valid JSON.** On any uncaught exception
  Alfred shows an opaque parse error and the user learns nothing. `cli.py`
  therefore catches *everything* and renders the failure as a normal result row.
- `"skipknowledge": true` keeps *your* ordering. Without it Alfred re-sorts by
  personal usage frequency, which fights any ranking you compute yourself.
- `"valid": false` makes a row non-actionable — ideal for hints and errors.
- `"icon": {"type": "fileicon", "path": "/Applications/Arc.app"}` renders the
  real macOS app icon.
- `"mods"` supply per-modifier `arg`/`subtitle` overrides (`cmd`, `alt`, `ctrl`,
  `shift`, `fn`).

## Object types used here

| Type | Purpose |
| --- | --- |
| `alfred.workflow.input.scriptfilter` | The `ws` / `wsn` / `wsw` keywords |
| `alfred.workflow.action.script` | The single "Perform" step |
| `alfred.workflow.output.notification` | Error surfacing |

`onlyshowifquerypopulated: true` on the notification means it fires **only when
the Perform step printed something**. Perform stays silent on success, so a
successful switch is silent and a failure notifies. That avoids needing a
conditional object in the graph.

## Connections and uidata

```python
connections = {
    "<source uid>": [
        {"destinationuid": "<uid>", "modifiers": 0,
         "modifiersubtext": "", "vitoclose": False},
    ]
}
uidata = {"<uid>": {"xpos": 35.0, "ypos": 40.0, "note": "…"}}
```

`modifiers: 0` means the connection fires for a plain Return. `uidata` positions
objects on the Alfred canvas and holds the sticky notes.

## Workflow configuration UI

`userconfigurationconfig` populates Alfred's *Configure Workflow* sheet, and
each entry writes an environment variable the scripts can read.

```python
{
  "type": "textfield",          # or checkbox, popupbutton, slider, filepicker
  "variable": "AEROSPACE_BIN",
  "label": "AeroSpace binary",
  "description": "…",
  "config": {"default": "", "placeholder": "/opt/homebrew/bin/aerospace",
             "required": False, "trim": True},
}
```

`popupbutton` takes `config.pairs` as `[[label, value], …]`; `checkbox` takes
`config.default` (bool) and `config.text`.

Give every configured variable a default in the top-level `variables` dict too —
`tests/test_build.py` enforces that.

## Why generate the plist

`info.plist` is generated from `tools/spec.py` rather than hand-edited, so the
repo holds readable, diffable Python instead of 400 lines of XML. Object UIDs
come from `uuid5(namespace, stable_name)`, so rebuilds are byte-identical and
git diffs stay empty when nothing changed.

**The trade-off:** edits made in Alfred's GUI are overwritten on the next build.
Change `tools/spec.py`, not the installed workflow.
