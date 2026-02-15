"""Backward-compatible entrypoint."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from waytoagi_gesture.cli import run

if __name__ == "__main__":
    raise SystemExit(run())
