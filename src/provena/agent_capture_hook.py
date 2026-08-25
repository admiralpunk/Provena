"""Portable capture hook entry point for agent hosts."""

import os
import sys

from .agent_hooks import capture_run


def main() -> None:
    raise SystemExit(capture_run(sys.stdin, sys.stderr, os.environ))


if __name__ == "__main__":
    main()
