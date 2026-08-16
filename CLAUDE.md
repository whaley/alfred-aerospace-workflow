# Working on this project

An Alfred 5 workflow for managing [AeroSpace](https://nikitabobko.github.io/AeroSpace/)
workspaces. Read this first; it will save you from re-deriving things the hard way.

## The two rules that matter most

1. **Standard library only.** This runs on macOS's stock `/usr/bin/python3`,
   which is **Python 3.9.6** on macOS 26. No pip, no venv, no third-party
   imports — in the workflow *or* in the tests. `tests/test_build.py` enforces it.

   Python 3.9 means: no `match`, no `int | None` at runtime, no `tomllib`.
   Every module starts with `from __future__ import annotations` so modern
   annotation syntax is still available.

2. **A Script Filter must always print valid JSON.** If it doesn't, Alfred shows
   an opaque parse error and the user learns nothing. `cli.py` catches
   *everything* — including bare `Exception` — and renders the failure as a
   normal result row. Do not add an early-return path that skips that handler.

## Layout

```
src/run.py               Entry point; Alfred calls this. Copied to the bundle root.
src/aeroalfred/
  aerospace.py           Subprocess wrapper. The ONLY module that shells out.
  commands.py            One function per Alfred entry point. Pure-ish: takes a
                         client, returns Feedback. Only perform() mutates.
  naming.py              Window title -> legal workspace name.
  alfred.py              Script Filter JSON builders.
  matching.py            Subsequence match + ranking.
  actions.py             The JSON payload passed filter -> Perform step.
  config.py              Env-var reads (Alfred workflow variables).
  cli.py                 argv dispatch + the always-emit-JSON guarantee.
tools/spec.py            Declarative workflow graph -> info.plist.
tools/build.py           Stage, generate plist, zip.
tools/icons.py           PNG generation, pure stdlib.
tests/                   unittest. `import support` for fakes.
docs/                    Verified notes on both external formats.
```

Dependency direction is one-way: `cli → commands → {aerospace, naming, alfred,
matching, actions} → config/errors`. Keep it that way.

## Commands

```bash
./build.sh              # test, then build
./build.sh test         # tests only
./build.sh test -v      # per-test names
./build.sh install      # test, build, hand to Alfred to import
./build.sh doctor       # check this machine's setup
./build.sh clean
```

Run a single test file: `/usr/bin/python3 -m unittest discover -s tests -t tests -p test_naming.py`

## Testing

`tests/support.py` provides `FakeRunner`, which stands in for the `aerospace`
subprocess and **records every argv**. Use `make_client()`:

```python
from support import make_client
client, runner = make_client()
feedback = commands.workspaces_filter(client, "code")
assert runner.mutations == []          # filters must never mutate
```

Guidelines:

- **Tests never invoke the real `aerospace`.** Always inject a runner.
- Derive from `EnvIsolatedTestCase` when touching config — it clears every
  `AEROALFRED_*`/`AEROSPACE_*` var so a developer's shell can't change results.
- `FakeRunner` mimics `--format ... --json` by projecting only the requested
  keys, so a test fails if production code forgets to request a field.
- Assert on **argv**, not just outcomes. The `--` separator is load-bearing
  (see below) and invisible in behavioural assertions.

## Traps, each of which has already bitten

**Always pass `--` before a workspace name.** `aerospace workspace next` means
"go to the next workspace"; `aerospace workspace -- next` means "go to the
workspace named `next`". Same for `move-node-to-workspace`.

**Alfred's PATH does not include `/opt/homebrew/bin`.** `aerospace` is not on
PATH when Alfred runs a script. `aerospace.find_binary()` probes `$AEROSPACE_BIN`,
then `which`, then known install locations. Verify changes with a bare env:

```bash
cd build/workflow && env -i HOME="$HOME" PATH=/usr/bin:/bin /usr/bin/python3 run.py doctor
```

**AeroSpace has no "create workspace" command.** Workspaces are lazy: one exists
when it holds a window or is in `persistent-workspaces`. Focusing a new empty
workspace works, but it vanishes when you leave. That is why every "create"
path offers to move a window along.

**Window titles are sometimes empty for every window.** An AeroSpace
Accessibility quirk, not our bug — it reproduces with plain
`aerospace list-windows --all --json`. `wsw` falls back to the app name. See
`docs/aerospace-cli.md`.

**`info.plist` is generated.** Edit `tools/spec.py`, never the installed
workflow — Alfred GUI edits are overwritten on the next build.

**Don't restart AeroSpace to test something.** It is the user's live window
manager. Read-only commands are fine; mutations belong in tests with a fake.

## Adding a new command

1. Add a `*_filter(client, query) -> Feedback` in `commands.py`.
2. Register it in `cli.FILTERS`.
3. Add a `_script_filter(...)` entry to `spec.OBJECTS`, a `spec.CONNECTIONS`
   pair to `action.perform`, and a `spec.POSITIONS` coordinate.
4. Add tests: one for the filter, one asserting it emits no mutations.

`tests/test_build.py` will fail if the plist references a command `cli.py`
doesn't implement, if a connection dangles, or if an object lacks canvas
coordinates. Let it guide you.

## Adding a new mutation

Add the verb to `actions.ALL_ACTIONS`, handle it in `commands.perform`, and add
a method to `Aerospace`. `perform` validates the workspace name *before*
shelling out — keep it that way so a bad name never reaches the CLI.

## Style

Match what's there: `from __future__ import annotations`, `"""docstrings"""` that
say *why*, `.format()` over f-strings for consistency with the 3.9 target, and
comments reserved for non-obvious decisions rather than narration.
