#!/usr/bin/env bash
#
# Build, test, and install the AeroSpace Workspaces Alfred workflow.
#
#   ./build.sh              test, then build dist/*.alfredworkflow
#   ./build.sh test         run the test suite only
#   ./build.sh build        build only, skipping tests
#   ./build.sh install      test, build, and hand the bundle to Alfred
#   ./build.sh doctor       check this machine's AeroSpace/Python setup
#   ./build.sh clean        remove build/ and dist/
#
# Everything runs on the Python that ships with macOS. There is nothing to
# pip install.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# The workflow itself always runs under /usr/bin/python3, so the tests do too.
PYTHON="${AEROALFRED_PYTHON:-/usr/bin/python3}"

if [[ -t 1 ]]; then
    BOLD=$'\033[1m'; GREEN=$'\033[32m'; RED=$'\033[31m'
    YELLOW=$'\033[33m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
    BOLD=""; GREEN=""; RED=""; YELLOW=""; DIM=""; RESET=""
fi

step() { printf '%s==>%s %s%s%s\n' "$GREEN" "$RESET" "$BOLD" "$1" "$RESET"; }
info() { printf '    %s%s%s\n' "$DIM" "$1" "$RESET"; }
warn() { printf '%s !! %s%s\n' "$YELLOW" "$1" "$RESET" >&2; }
die()  { printf '%serror:%s %s\n' "$RED" "$RESET" "$1" >&2; exit 1; }

require_python() {
    [[ -x "$PYTHON" ]] || die "Python interpreter not found at $PYTHON"
    local version
    version="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    info "python $version at $PYTHON"
    "$PYTHON" - <<'PY' || die "Python 3.9 or newer is required"
import sys
sys.exit(0 if sys.version_info >= (3, 9) else 1)
PY
}

cmd_test() {
    step "Running tests"
    require_python
    # -t tests puts the tests directory on sys.path so `import support` works.
    "$PYTHON" -m unittest discover --start-directory tests --top-level-directory tests "$@"
}

cmd_build() {
    step "Building workflow"
    require_python
    "$PYTHON" tools/build.py
}

cmd_install() {
    step "Installing workflow"
    require_python
    "$PYTHON" tools/build.py --install
    info "Alfred should now be showing its import sheet"
}

cmd_clean() {
    step "Cleaning"
    rm -rf build dist
    find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
    find . -name '*.pyc' -delete 2>/dev/null || true
    info "removed build/, dist/, and __pycache__"
}

cmd_doctor() {
    step "Checking this machine"
    require_python

    if command -v aerospace >/dev/null 2>&1; then
        info "aerospace on PATH: $(command -v aerospace)"
    else
        warn "aerospace is not on PATH (fine — the workflow also probes Homebrew paths)"
    fi

    if [[ -d "/Applications/Alfred 5.app" ]]; then
        info "Alfred 5 is installed"
    else
        warn "Alfred 5 was not found in /Applications"
    fi

    step "Workflow self-check"
    ( cd src && "$PYTHON" run.py doctor )
}

main() {
    local command="${1:-all}"
    shift || true

    case "$command" in
        test)    cmd_test "$@" ;;
        build)   cmd_build ;;
        install) cmd_test && cmd_install ;;
        clean)   cmd_clean ;;
        doctor)  cmd_doctor ;;
        all)     cmd_test && cmd_build ;;
        -h|--help|help)
            # Print the header comment block, stopping at the first line of code.
            awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' \
                "${BASH_SOURCE[0]}"
            ;;
        *) die "unknown command: $command (try: test build install clean doctor)" ;;
    esac
}

main "$@"
