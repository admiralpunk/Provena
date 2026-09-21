"""Portable context retrieval hook entry point for agent hosts."""

import os
import sys

from .hooks import context_run


def main() -> None:
    raise SystemExit(context_run(sys.stdin, sys.stdout, sys.stderr, os.environ))


if __name__ == "__main__":
    main()
