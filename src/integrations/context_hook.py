"""Portable context retrieval hook entry point for agent hosts."""

import argparse
import os
import sys

from .connection_config import load_connection_environment
from .hooks import context_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject attributed Provena context into a host turn.")
    parser.add_argument("--config", help="Protected Provena connection JSON file")
    args = parser.parse_args()
    environment = load_connection_environment(os.environ, args.config)
    raise SystemExit(context_run(sys.stdin, sys.stdout, sys.stderr, environment))


if __name__ == "__main__":
    main()
