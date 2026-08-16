#!/usr/bin/python3
"""Entry point that Alfred invokes. Lives at the root of the built workflow.

Alfred sets the working directory to the workflow folder, so `run.py` and the
`aeroalfred` package sit side by side at runtime.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aeroalfred.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
