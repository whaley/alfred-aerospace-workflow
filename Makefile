# Thin wrapper around build.sh so `make` works out of habit.
# Everything runs on macOS's stock /usr/bin/python3 — nothing to install.

PYTHON ?= /usr/bin/python3

.DEFAULT_GOAL := all
.PHONY: all test build install clean doctor watch

all:      ## Run tests, then build the workflow
	@./build.sh all

test:     ## Run the test suite
	@./build.sh test

build:    ## Build dist/*.alfredworkflow without testing
	@./build.sh build

install:  ## Test, build, and open the bundle so Alfred imports it
	@./build.sh install

clean:    ## Remove build/, dist/, and __pycache__
	@./build.sh clean

doctor:   ## Check AeroSpace, Alfred, and Python on this machine
	@./build.sh doctor

verbose:  ## Run the test suite with per-test output
	@./build.sh test -v

help:     ## List targets
	@grep -E '^[a-z]+:.*?##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'
