"""Install Provena's MCP server and lifecycle hooks into a local Codex client."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from uuid import UUID

from .connection_config import default_config_home


Runner = Callable[..., subprocess.CompletedProcess[str]]
PROVENA_HANDLER_NAMES = (
    "provena-agent-context",
    "provena-agent-capture",
    "provena-codex-retrieve",
    "provena-codex-capture",
)


def default_codex_home(environ: Mapping[str, str] | None = None) -> Path:
    values = environ or os.environ
    configured = values.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def connection_document(api_url: str, api_key: str, scope_id: str) -> dict[str, str]:
    UUID(scope_id)
    return {
        "api_url": api_url.rstrip("/"),
        "api_key": api_key,
        "scope_id": scope_id,
        "agent_host": "codex",
    }


def _command(parts: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(parts)) if os.name == "nt" else shlex.join(parts)


def build_provena_hooks(
    context_command: str,
    capture_command: str,
    connection_path: Path,
) -> dict[str, list[dict[str, Any]]]:
    context = _command((context_command, "--config", str(connection_path)))
    capture = _command((capture_command, "--config", str(connection_path)))
    return {
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": context,
                        "timeout": 15,
                        "statusMessage": "Loading relevant Provena memory",
                    },
                    {
                        "type": "command",
                        "command": capture,
                        "async": True,
                        "timeout": 120,
                        "statusMessage": "Recording conversation facts",
                    },
                ]
            }
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": capture,
                        "async": True,
                        "timeout": 120,
                        "statusMessage": "Recording assistant facts",
                    }
                ]
            }
        ],
    }


def _is_provena_handler(handler: object) -> bool:
    if not isinstance(handler, dict):
        return False
    command = handler.get("command")
    return isinstance(command, str) and any(name in command for name in PROVENA_HANDLER_NAMES)


def merge_hooks(document: object, additions: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    if document is None:
        merged: dict[str, Any] = {}
    elif isinstance(document, dict):
        merged = dict(document)
    else:
        raise RuntimeError("Codex hooks.json must contain a JSON object")

    hooks_value = merged.get("hooks", {})
    if not isinstance(hooks_value, dict):
        raise RuntimeError("The hooks field in Codex hooks.json must be a JSON object")
    hooks = dict(hooks_value)

    for event, groups_value in list(hooks.items()):
        if not isinstance(groups_value, list):
            raise RuntimeError(f"The {event} hook groups must be a JSON array")
        retained_groups: list[object] = []
        for group_value in groups_value:
            if not isinstance(group_value, dict):
                retained_groups.append(group_value)
                continue
            handlers_value = group_value.get("hooks", [])
            if not isinstance(handlers_value, list):
                raise RuntimeError(f"The handlers for {event} must be a JSON array")
            handlers = [handler for handler in handlers_value if not _is_provena_handler(handler)]
            if handlers:
                retained_groups.append({**group_value, "hooks": handlers})
        hooks[event] = retained_groups

    for event, groups in additions.items():
        hooks.setdefault(event, []).extend(groups)
    merged["description"] = merged.get("description", "Codex lifecycle hooks")
    merged["hooks"] = hooks
    return merged


def _atomic_private_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(content)
        os.replace(temporary, path)
        path.chmod(0o600)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _read_hooks(path: Path) -> object:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Could not parse {path}: {error}") from error


def install_codex(
    api_url: str,
    api_key: str,
    scope_id: str,
    *,
    mcp_command: str,
    context_command: str,
    capture_command: str,
    codex_home: Path | None = None,
    config_home: Path | None = None,
    runner: Runner = subprocess.run,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Configure Codex MCP plus automatic retrieval and capture after explicit opt-in."""

    values = environ or os.environ
    codex_executable = shutil.which("codex")
    if not codex_executable:
        raise RuntimeError("codex was not found on PATH; install Codex before using --install")

    codex_directory = codex_home or default_codex_home(values)
    connection_directory = (config_home or default_config_home(values)) / "provena"
    connection_path = connection_directory / "codex.json"
    hooks_path = codex_directory / "hooks.json"
    codex_config_path = codex_directory / "config.toml"

    connection = connection_document(api_url, api_key, scope_id)
    additions = build_provena_hooks(context_command, capture_command, connection_path)
    hooks = merge_hooks(_read_hooks(hooks_path), additions)

    previous_connection = connection_path.read_bytes() if connection_path.exists() else None
    previous_hooks = hooks_path.read_bytes() if hooks_path.exists() else None
    previous_codex_config = codex_config_path.read_bytes() if codex_config_path.exists() else None
    process_environment = dict(values)
    process_environment["CODEX_HOME"] = str(codex_directory)

    try:
        _atomic_private_write(connection_path, json.dumps(connection, indent=2) + "\n")
        _atomic_private_write(hooks_path, json.dumps(hooks, indent=2) + "\n")

        existing = runner(
            [codex_executable, "mcp", "get", "provena"],
            env=process_environment,
            text=True,
            capture_output=True,
            check=False,
        )
        if existing.returncode == 0:
            runner(
                [codex_executable, "mcp", "remove", "provena"],
                env=process_environment,
                text=True,
                capture_output=True,
                check=True,
            )
        runner(
            [
                codex_executable,
                "mcp",
                "add",
                "provena",
                "--env",
                f"PROVENA_CONFIG_FILE={connection_path}",
                "--",
                mcp_command,
                "--config",
                str(connection_path),
            ],
            env=process_environment,
            text=True,
            capture_output=True,
            check=True,
        )
    except Exception as error:
        for path, previous in (
            (connection_path, previous_connection),
            (hooks_path, previous_hooks),
            (codex_config_path, previous_codex_config),
        ):
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_private_write(path, previous.decode())
        raise RuntimeError(f"Could not configure Codex: {error}") from error

    return {
        "connection_file": str(connection_path),
        "hooks_file": str(hooks_path),
        "codex_config": str(codex_config_path),
    }

