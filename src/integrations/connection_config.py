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

