"""Load a connector credential file without adding a dotenv dependency."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


ENVIRONMENT_KEYS = {
    "api_url": "PROVENA_API_URL",
    "api_key": "PROVENA_API_KEY",
    "scope_id": "PROVENA_SCOPE_ID",
    "agent_host": "PROVENA_AGENT_HOST",
}


def load_connection_environment(
    environ: Mapping[str, str],
    config_path: str | Path | None = None,
) -> dict[str, str]:
    """Return connection settings from a protected JSON file plus env overrides."""

    resolved: dict[str, str] = {}
    selected = config_path or environ.get("PROVENA_CONFIG_FILE")
    if selected:
        path = Path(selected).expanduser()
        try:
            document = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Could not read Provena connection file {path}: {error}") from error
        if not isinstance(document, dict):
            raise RuntimeError(f"Provena connection file {path} must contain a JSON object")
        for field, variable in ENVIRONMENT_KEYS.items():
            value = document.get(field)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise RuntimeError(f"{field} in {path} must be a non-empty string")
                resolved[variable] = value

    for variable in ENVIRONMENT_KEYS.values():
        value = environ.get(variable)
        if value:
            resolved[variable] = value
    return resolved


def default_config_home(environ: Mapping[str, str] | None = None) -> Path:
    values = environ or os.environ
    configured = values.get("XDG_CONFIG_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".config"



SUPPORTED_CONNECTION_HOSTS = ("codex", "claude", "gemini")


def host_connection_path(host: str, environ: Mapping[str, str] | None = None) -> Path:
    """Return the protected connection file that onboarding writes for HOST (ADR 0021)."""

    if host not in SUPPORTED_CONNECTION_HOSTS:
        raise ValueError(f"unsupported agent host: {host}")
    return default_config_home(environ) / "provena" / f"{host}.json"


def setup_hint(host: str) -> str:
    return (
        f"Provena is not set up for {host} yet: run `provena quickstart {host} --plugin` "
        f"for a local service, or `provena connect {host} --plugin` for an existing one."
    )


def load_host_connection(
    environ: Mapping[str, str],
    config_path: str | Path | None = None,
    host: str | None = None,
) -> dict[str, str] | None:
    """Load settings from --config, else from the --host connection file.

    Returns None when only a host was given and its connection file does not exist,
    so plugin-provided commands can stay inert until the user finishes onboarding.
    An explicit --config path keeps priority and still fails loudly when unreadable.
    """

    if config_path is None and host is not None:
        path = host_connection_path(host, environ)
        if not path.exists():
            return None
        config_path = path
    return load_connection_environment(environ, config_path)
