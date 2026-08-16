"""Exception types shared across the workflow."""

from __future__ import annotations


class AeroAlfredError(Exception):
    """Base class for every error this workflow raises deliberately."""


class AerospaceNotFound(AeroAlfredError):
    """The `aerospace` binary could not be located on this machine."""


class AerospaceCommandError(AeroAlfredError):
    """An `aerospace` invocation exited non-zero."""

    def __init__(self, args, returncode, stderr=""):
        self.args = list(args)
        self.returncode = returncode
        self.stderr = (stderr or "").strip()
        detail = self.stderr or "no output on stderr"
        super().__init__(
            "aerospace {0} failed (exit {1}): {2}".format(
                " ".join(self.args), returncode, detail
            )
        )


class InvalidWorkspaceName(AeroAlfredError):
    """A proposed workspace name violates AeroSpace's naming rules."""
