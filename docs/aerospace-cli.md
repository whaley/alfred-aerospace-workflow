# AeroSpace CLI notes

Everything here was verified against **AeroSpace 0.21.3-Beta** on **macOS 26.6.1**
by running the commands, not by reading docs. Re-verify if you bump AeroSpace.

## Reading state

Always combine `--format` with `--json`. AeroSpace accepts both, and the result
is a keyed JSON array with **native types** — integers stay integers, booleans
stay booleans. This is far more robust than splitting delimited text.

```console
$ aerospace list-workspaces --all --format '%{workspace}%{workspace-is-focused}' --json
[
  {
    "workspace" : "Main",
    "workspace-is-focused" : true
  }
]
```

Note there is **no separator** between `%{...}` tokens in the format string. In
JSON mode the tokens simply select which keys appear; concatenating them is
correct and intentional.

Without `--format`, `--json` returns a small default key set (for windows:
`app-name`, `window-id`, `window-title` — note that `workspace` is *absent*).
Always pass `--format` when you need a specific field.

### Available format placeholders

`aerospace list-windows --format` with no value prints the full list:

```
window-id  window-is-fullscreen  window-title  window-layout
window-parent-container-layout  workspace  workspace-is-focused
workspace-is-visible  workspace-root-container-layout  monitor-id
monitor-appkit-nsscreen-screens-id  monitor-name  monitor-is-main
app-bundle-id  app-name  app-pid  app-exec-path  app-bundle-path
right-padding  newline  tab
```

`app-bundle-path` is what lets Alfred render a real app icon via
`{"type": "fileicon", "path": "/Applications/Arc.app"}`.

### Selector flags

`list-workspaces` and `list-windows` each require exactly one selector:
`--all`, `--focused`, or `--monitor`/`--workspace`.

## Workspace naming rules

Extracted verbatim from the 0.21.3 binary (`strings`), and each one confirmed by
invocation. `src/aeroalfred/naming.py` mirrors these exactly.

| Rule | Message |
| --- | --- |
| No whitespace | `Whitespace characters are forbidden in workspace names` |
| No leading `-` | `Workspace names starting with dash are disallowed` |
| No leading `_` | `Workspace names starting with underscore are reserved for future use` |
| No commas | `Workspace names are not allowed to contain comma` |
| Not empty | `Empty workspace name is forbidden` |
| Not reserved | `'<name>' is a reserved workspace name` |

Unicode letters are fine — `café` is a legal workspace name.

An invalid name **fails safely**: exit code `2`, message on stderr, and the
focused workspace does not change.

```console
$ aerospace workspace -- "bad name"
ERROR: Whitespace characters are forbidden in workspace names
$ echo $?
2
```

## Always pass `--`

Both `workspace` and `move-node-to-workspace` accept either a relative motion
(`next` / `prev`) or a literal name:

```
USAGE: workspace [--auto-back-and-forth] [--fail-if-noop] [--] <workspace-name>
   OR: workspace [--wrap-around] (next|prev)
```

Without `--`, a workspace genuinely named `next` would be parsed as relative
motion and silently do the wrong thing. Every call in this project passes `--`
before the name, and `tests/test_aerospace.py` asserts it.

## Workspaces are lazy

There is no "create workspace" command. A workspace exists when it holds a
window, or when it is listed in `persistent-workspaces` in `~/.aerospace.toml`.

`aerospace workspace -- NewName` focuses a new empty workspace, but **that
workspace disappears the moment you leave it** unless something is in it.

That is why the workflow pairs creation with a window move:

- `ws` / `wsn` + ⌘⏎ → `move-node-to-workspace --focus-follows-window`
- `wsw` → `move-node-to-workspace --window-id <id> --focus-follows-window`

## Known quirk: empty window titles

AeroSpace sometimes reports `"window-title": ""` for **every** window, including
the focused one, while `app-name` stays correct. It is an Accessibility-API
state issue in AeroSpace, not a bug in this workflow — it reproduces with a bare
`aerospace list-windows --all --json` and no `--format` at all.

Observed on 0.21.3-Beta / macOS 26.6.1 mid-session, having worked minutes
earlier with the same windows open.

Workarounds, cheapest first:

1. `aerospace reload-config`
2. Restart AeroSpace (`open -a AeroSpace` after quitting)
3. Re-grant Accessibility in System Settings → Privacy & Security → Accessibility

`wsw` degrades gracefully: with no title it names the workspace after the app
(`System Information` → `System-Information`), so the feature keeps working.

## Useful for a future version

Not used yet, but relevant if this workflow grows past workspace management:

- `summon-workspace` — pull a workspace onto the focused monitor
- `move-workspace-to-monitor`
- `focus --window-id <id>` — focus a specific window
- `list-monitors`
- `config --get <key>` / `--all-keys` — query the running config
- `subscribe` — event stream, for cache invalidation
