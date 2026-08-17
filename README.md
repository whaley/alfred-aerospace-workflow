# AeroSpace Workspaces for Alfred

Manage [AeroSpace](https://nikitabobko.github.io/AeroSpace/) workspaces from
Alfred: list them, switch between them, create new ones — including naming a new
workspace after a window you already have open — and pull a window from another
workspace into the one you're on.

Written in Python against macOS's stock `/usr/bin/python3`. **No JavaScript, no
pip install, no dependencies.**

![Alfred showing the ws keyword: rows for creating a workspace from a window or
from a typed name, followed by the existing workspaces aeroalfred, Main and
Projects-(Focus-5-Cottage-Rental), each with its window count and
monitor](screenshot.png)

## Install

```bash
git clone <this repo> && cd alfred-aerospace-workflow
./build.sh install
```

That runs the tests, builds `dist/AeroSpace Workspaces.alfredworkflow`, and opens
it so Alfred imports it. To build without installing, use `./build.sh`.

Requires Alfred 5 with the Powerpack, AeroSpace, and macOS 12+.

## Keywords

### `ws` — list and switch

Lists every workspace, focused one first, with its window count and monitor.

```
ws              →  Main       ● focused · 5 windows · LS32D80xU
                   chat       1 window · LS32D80xU
                   code       3 windows · LS32D80xU
ws co           →  code       3 windows · LS32D80xU
```

- <kbd>⏎</kbd> switch to the workspace
- <kbd>⌘⏎</kbd> move the focused window there and follow it

Matching is subsequence-based, so `afw` finds `alfred-aerospace-workflow`.

If what you type isn't an existing workspace and is a legal name, a
**Create workspace “…”** row is appended — so `ws` alone covers listing,
switching, and creating.

### `wsn <name>` — create with a name you type

Validates the name against AeroSpace's rules as you type and tells you exactly
what's wrong when it isn't legal:

```
wsn my project  →  Invalid workspace name
                   Whitespace characters are forbidden · Try "my-project"
                   Create workspace "my-project"
```

If the name already exists it offers to switch instead of creating a duplicate.

- <kbd>⏎</kbd> create and switch
- <kbd>⌘⏎</kbd> create and move the focused window into it

### `wsw <filter>` — name a workspace after a window

Lists your open windows with their real app icons. Picking one derives a legal
workspace name from its title, creates that workspace, and moves the window in.

```
wsw             →  weechat                             kitty · Create workspace "weechat" and move this window in
                   claude /create-agent - Kagi Search  Arc · Create workspace "claude-create-agent-Kagi-Search" …
```

Filter by app name or window title. If the derived name matches a workspace that
already exists, the subtitle says so and the window moves there instead.

### `wsp <filter>` — pull a window to where you are

The inverse of `wsw`. Lists only the windows that are **not** on the focused
workspace, and moves the one you pick here — no name to type or derive, since
the destination is wherever you already are.

```
wsp             →  weechat                             kitty · from “chat” · ⌘ to go there instead
                   Welcome — alfred-aerospace-workflow  Code · from “code” · ⌘ to go there instead
wsp chat        →  weechat                             kitty · from “chat” · ⌘ to go there instead
```

- <kbd>⏎</kbd> move that window into the focused workspace
- <kbd>⌘⏎</kbd> switch to the window's workspace instead, leaving it in place

The filter matches app name, window title, *and* the source workspace name, so
`wsp code` pulls everything sitting on `code`. With *Follow moved windows* on,
the window you pulled ends up focused.

## How names are derived

AeroSpace rejects whitespace, commas, leading `-` or `_`, empty names, and the
reserved words `next`/`prev`. Titles are coerced to fit:

| Window title | Workspace name |
| --- | --- |
| `weechat` | `weechat` |
| `claude /create-agent - Kagi Search` | `claude-create-agent-Kagi-Search` |
| `~/workspace/alfred-aerospace-workflow` | `workspace-alfred-aerospace-workflow` |
| *(untitled, app is System Information)* | `System-Information` |

Names are truncated on a word boundary (default 40 chars). Untitled windows fall
back to the app name, so this never fails.

## Configuration

Alfred → *Configure Workflow*:

| Setting | Default | What it does |
| --- | --- | --- |
| AeroSpace binary | *(auto)* | Set only if AeroSpace lives somewhere unusual |
| Name new workspaces after | Whole title | Or the text before/after the first/last ` - ` separator |
| Maximum name length | 40 | Derived names are truncated on a word boundary |
| Follow moved windows | on | Switch to the destination after moving a window |
| Show empty workspaces | on | Include workspaces holding no windows |

## A note on empty workspaces

AeroSpace has no "create workspace" command — workspaces are lazy. One exists
when it holds a window, or when it's listed in `persistent-workspaces` in your
`~/.aerospace.toml`.

So `ws`/`wsn` with plain <kbd>⏎</kbd> takes you to a new empty workspace that
**disappears as soon as you leave it**. To make one stick, put a window in it:
use <kbd>⌘⏎</kbd>, or use `wsw`. For a workspace that should always exist, add it
to `persistent-workspaces`.

## Troubleshooting

```bash
./build.sh doctor
```

Reports the Python version, where `aerospace` was found, and what AeroSpace
currently reports. You can also run it inside the installed workflow folder:

```bash
cd ~/Library/Application\ Support/Alfred/Alfred.alfredpreferences/workflows/*/
/usr/bin/python3 run.py doctor
```

**Nothing shows up in Alfred.** Usually AeroSpace isn't on the minimal PATH
Alfred uses. The workflow probes the usual Homebrew locations automatically; if
yours is elsewhere, set *AeroSpace binary* in Configure Workflow.

**`wsw` shows app names instead of window titles.** AeroSpace occasionally
reports empty titles for every window — an Accessibility-API quirk on its side,
reproducible with a plain `aerospace list-windows --all --json`. Try
`aerospace reload-config`, then restarting AeroSpace, then re-granting
Accessibility permission. `wsw` keeps working meanwhile using app names.

## Development

```bash
./build.sh test      # 206 tests, stdlib unittest
./build.sh test -v
./build.sh clean
```

See [CLAUDE.md](CLAUDE.md) for architecture and the traps worth knowing, plus
verified notes on the [AeroSpace CLI](docs/aerospace-cli.md) and the
[Alfred workflow format](docs/alfred-workflow-format.md).

`info.plist` is generated from [tools/spec.py](tools/spec.py) — edit that, not
the workflow in Alfred's GUI, or your changes will be overwritten on the next
build.
