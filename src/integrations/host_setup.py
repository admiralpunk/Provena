"""Install Provena MCP and lifecycle hooks into supported local agent hosts."""

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
SUPPORTED_HOSTS = ("codex", "claude", "gemini")
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


def default_claude_home(environ: Mapping[str, str] | None = None) -> Path:
    values = environ or os.environ
    configured = values.get("CLAUDE_CONFIG_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".claude"


def default_claude_state(home: Path, environ: Mapping[str, str] | None = None) -> Path:
    values = environ or os.environ
    if values.get("CLAUDE_CONFIG_DIR"):
        return home / ".claude.json"
    return home.parent / ".claude.json"


def default_gemini_home(environ: Mapping[str, str] | None = None) -> Path:
    values = environ or os.environ
    root = Path(values.get("GEMINI_CLI_HOME", Path.home())).expanduser()
    return root / ".gemini"


def connection_document(host: str, api_url: str, api_key: str, scope_id: str) -> dict[str, str]:
    if host not in SUPPORTED_HOSTS:
        raise ValueError(f"unsupported agent host: {host}")
    UUID(scope_id)
    return {
        "api_url": api_url.rstrip("/"),
        "api_key": api_key,
        "scope_id": scope_id,
        "agent_host": host,
    }


def _command(parts: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(parts)) if os.name == "nt" else shlex.join(parts)


def build_provena_hooks(
    context_command: str,
    capture_command: str,
    connection_path: Path,
    *,
    host: str = "codex",
) -> dict[str, list[dict[str, Any]]]:
    """Build host-native hooks while keeping capture and retrieval commands portable."""

    context = _command((context_command, "--config", str(connection_path)))
    capture = _command((capture_command, "--config", str(connection_path)))
    if host in {"codex", "claude"}:
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
    if host == "gemini":
        return {
            "BeforeAgent": [
                {
                    "sequential": False,
                    "hooks": [
                        {
                            "name": "provena-context",
                            "type": "command",
                            "command": context,
                            "timeout": 15000,
                            "description": "Load relevant attributed Provena memory",
                        },
                        {
                            "name": "provena-capture-user",
                            "type": "command",
                            "command": capture,
                            "timeout": 120000,
                            "description": "Record and extract candidate facts from the user turn",
                        },
                    ],
                }
            ],
            "AfterAgent": [
                {
                    "hooks": [
                        {
                            "name": "provena-capture-assistant",
                            "type": "command",
                            "command": capture,
                            "timeout": 120000,
                            "description": "Record and extract candidate facts from the assistant turn",
                        }
                    ]
                }
            ],
        }
    raise ValueError(f"unsupported agent host: {host}")


def _is_provena_handler(handler: object) -> bool:
    if not isinstance(handler, dict):
        return False
    command = handler.get("command")
    return isinstance(command, str) and any(name in command for name in PROVENA_HANDLER_NAMES)


def merge_hooks(
    document: object,
    additions: dict[str, list[dict[str, Any]]],
    *,
    description: str | None = None,
) -> dict[str, Any]:
    if document is None:
        merged: dict[str, Any] = {}
    elif isinstance(document, dict):
        merged = dict(document)
    else:
        raise RuntimeError("Agent settings must contain a JSON object")

    hooks_value = merged.get("hooks", {})
    if not isinstance(hooks_value, dict):
        raise RuntimeError("The hooks field in agent settings must be a JSON object")
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
    if description is not None:
        merged["description"] = merged.get("description", description)
    merged["hooks"] = hooks
    return merged


def merge_mcp_server(document: object, server: dict[str, Any]) -> dict[str, Any]:
    if document is None:
        merged: dict[str, Any] = {}
    elif isinstance(document, dict):
        merged = dict(document)
    else:
        raise RuntimeError("Agent configuration must contain a JSON object")
    servers_value = merged.get("mcpServers", {})
    if not isinstance(servers_value, dict):
        raise RuntimeError("The mcpServers field in agent configuration must be a JSON object")
    merged["mcpServers"] = {**servers_value, "provena": server}
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


def _read_json(path: Path) -> object:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Could not parse {path}: {error}") from error


def _restore(paths: Sequence[tuple[Path, bytes | None]]) -> None:
    for path, previous in paths:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            _atomic_private_write(path, previous.decode())


def _json_text(document: object) -> str:
    return json.dumps(document, indent=2) + "\n"


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

    connection = connection_document("codex", api_url, api_key, scope_id)
    additions = build_provena_hooks(context_command, capture_command, connection_path, host="codex")
    hooks = merge_hooks(_read_json(hooks_path), additions, description="Codex lifecycle hooks")

    previous = tuple(
        (path, path.read_bytes() if path.exists() else None)
        for path in (connection_path, hooks_path, codex_config_path)
    )
    process_environment = dict(values)
    process_environment["CODEX_HOME"] = str(codex_directory)

    try:
        _atomic_private_write(connection_path, _json_text(connection))
        _atomic_private_write(hooks_path, _json_text(hooks))

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
        _restore(previous)
        raise RuntimeError(f"Could not configure Codex: {error}") from error

    return {
        "connection_file": str(connection_path),
        "hooks_file": str(hooks_path),
        "codex_config": str(codex_config_path),
    }


def install_claude(
    api_url: str,
    api_key: str,
    scope_id: str,
    *,
    mcp_command: str,
    context_command: str,
    capture_command: str,
    claude_home: Path | None = None,
    claude_state: Path | None = None,
    config_home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Configure user-scoped Claude Code MCP and lifecycle hooks."""

    values = environ or os.environ
    if not shutil.which("claude"):
        raise RuntimeError("claude was not found on PATH; install Claude Code before using --install")
    directory = claude_home or default_claude_home(values)
    state_path = claude_state or (directory / ".claude.json" if claude_home is not None else default_claude_state(directory, values))
    settings_path = directory / "settings.json"
    connection_path = (config_home or default_config_home(values)) / "provena" / "claude.json"

    connection = connection_document("claude", api_url, api_key, scope_id)
    additions = build_provena_hooks(context_command, capture_command, connection_path, host="claude")
    settings = merge_hooks(_read_json(settings_path), additions)
    state = merge_mcp_server(
        _read_json(state_path),
        {"type": "stdio", "command": mcp_command, "args": ["--config", str(connection_path)]},
    )
    previous = tuple(
        (path, path.read_bytes() if path.exists() else None)
        for path in (connection_path, settings_path, state_path)
    )
    try:
        _atomic_private_write(connection_path, _json_text(connection))
        _atomic_private_write(settings_path, _json_text(settings))
        _atomic_private_write(state_path, _json_text(state))
    except Exception as error:
        _restore(previous)
        raise RuntimeError(f"Could not configure Claude Code: {error}") from error
    return {
        "connection_file": str(connection_path),
        "hooks_file": str(settings_path),
        "claude_config": str(state_path),
    }


def install_gemini(
    api_url: str,
    api_key: str,
    scope_id: str,
    *,
    mcp_command: str,
    context_command: str,
    capture_command: str,
    gemini_home: Path | None = None,
    config_home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Configure user-scoped Gemini CLI MCP and lifecycle hooks."""

    values = environ or os.environ
    if not shutil.which("gemini"):
        raise RuntimeError("gemini was not found on PATH; install Gemini CLI before using --install")
    directory = gemini_home or default_gemini_home(values)
    settings_path = directory / "settings.json"
    connection_path = (config_home or default_config_home(values)) / "provena" / "gemini.json"

    connection = connection_document("gemini", api_url, api_key, scope_id)
    additions = build_provena_hooks(context_command, capture_command, connection_path, host="gemini")
    settings = merge_hooks(_read_json(settings_path), additions)
    settings = merge_mcp_server(
        settings,
        {"command": mcp_command, "args": ["--config", str(connection_path)]},
    )
    previous = tuple(
        (path, path.read_bytes() if path.exists() else None)
        for path in (connection_path, settings_path)
    )
    try:
        _atomic_private_write(connection_path, _json_text(connection))
        _atomic_private_write(settings_path, _json_text(settings))
    except Exception as error:
        _restore(previous)
        raise RuntimeError(f"Could not configure Gemini CLI: {error}") from error
    return {
        "connection_file": str(connection_path),
        "hooks_file": str(settings_path),
        "gemini_config": str(settings_path),
    }


def install_host(
    host: str,
    api_url: str,
    api_key: str,
    scope_id: str,
    *,
    mcp_command: str,
    context_command: str,
    capture_command: str,
) -> dict[str, str]:
    installers = {
        "codex": install_codex,
        "claude": install_claude,
        "gemini": install_gemini,
    }
    try:
        installer = installers[host]
    except KeyError as error:
        raise ValueError(f"unsupported agent host: {host}") from error
    return installer(
        api_url,
        api_key,
        scope_id,
        mcp_command=mcp_command,
        context_command=context_command,
        capture_command=capture_command,
    )
