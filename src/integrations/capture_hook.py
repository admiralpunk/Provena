"""Portable capture hook entry point for agent hosts."""

import argparse
import os
import sys

from .connection_config import SUPPORTED_CONNECTION_HOSTS, load_host_connection, setup_hint
from .hooks import capture_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture a host conversation turn in Provena.")
    parser.add_argument("--config", help="Protected Provena connection JSON file")
    parser.add_argument("--host", choices=SUPPORTED_CONNECTION_HOSTS, help="Use the connection file that onboarding wrote for this host")
    args = parser.parse_args()
    environment = load_host_connection(os.environ, args.config, args.host)
    if environment is None:
        # Fail open: a plugin can be enabled before onboarding finishes.
        sys.stderr.write(setup_hint(args.host) + "\n")
        raise SystemExit(0)
    raise SystemExit(capture_run(sys.stdin, sys.stderr, environment))


if __name__ == "__main__":
    main()
