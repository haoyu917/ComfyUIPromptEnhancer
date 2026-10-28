"""Developer test runner for BUFF AI Director V3.

Runtime use of the ComfyUI node does not require pytest. To run this developer
suite, install pytest and execute: python run_tests.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    try:
        import pytest  # noqa: F401
    except ImportError:
        print("pytest is required only for developer tests.")
        print("Install it with: python -m pip install -r requirements-dev.txt")
        return 2
    return subprocess.call([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
