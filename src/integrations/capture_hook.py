"""Portable capture hook entry point for agent hosts."""

import argparse
import os
import sys

from .connection_config import load_connection_environment
from .hooks import capture_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture a host conversation turn in Provena.")
    parser.add_argument("--config", help="Protected Provena connection JSON file")
    args = parser.parse_args()
    environment = load_connection_environment(os.environ, args.config)
    raise SystemExit(capture_run(sys.stdin, sys.stderr, environment))


if __name__ == "__main__":
    main()
