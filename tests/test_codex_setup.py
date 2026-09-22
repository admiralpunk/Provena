import json
import stat
import subprocess
from pathlib import Path
from uuid import uuid4

from provena.integrations.codex_setup import build_provena_hooks, install_codex, merge_hooks
from provena.integrations.connection_config import load_connection_environment


def test_codex_install_preserves_other_hooks_and_keeps_secret_out_of_hook_config(monkeypatch, tmp_path):
    codex_home = tmp_path / "codex"
    config_home = tmp_path / "config"
    codex_home.mkdir()
    existing = {
        "hooks": {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": "/opt/other-hook"}]},
                {"hooks": [{"type": "command", "command": "/old/provena-agent-context"}]},
            ]
        }
    }
    (codex_home / "hooks.json").write_text(json.dumps(existing))
    monkeypatch.setattr("provena.integrations.codex_setup.shutil.which", lambda name: "/usr/bin/codex")
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        returncode = 1 if command[2:4] == ["get", "provena"] else 0
        return subprocess.CompletedProcess(command, returncode, "", "")

    scope_id = str(uuid4())
    result = install_codex(
        "http://127.0.0.1:8000/",
        "agent-secret",
        scope_id,
        mcp_command="/venv/bin/provena-mcp",
        context_command="/venv/bin/provena-agent-context",
        capture_command="/venv/bin/provena-agent-capture",
        codex_home=codex_home,
        config_home=config_home,
        runner=runner,
        environ={},
    )

    connection_path = config_home / "provena" / "codex.json"
    hooks_path = codex_home / "hooks.json"
    assert result["connection_file"] == str(connection_path)
    assert stat.S_IMODE(connection_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(hooks_path.stat().st_mode) == 0o600
    assert json.loads(connection_path.read_text())["api_key"] == "agent-secret"

    hooks_text = hooks_path.read_text()
    assert "agent-secret" not in hooks_text
    assert "/opt/other-hook" in hooks_text
    assert "/old/provena-agent-context" not in hooks_text
    assert "/venv/bin/provena-agent-context" in hooks_text
    assert "/venv/bin/provena-agent-capture" in hooks_text
    assert calls[-1][-3:] == ["/venv/bin/provena-mcp", "--config", str(connection_path)]


def test_connection_file_can_supply_hooks_and_mcp_with_environment_override(tmp_path):
    path = tmp_path / "connection.json"
    path.write_text(
        json.dumps(
            {
                "api_url": "http://file.example",
                "api_key": "file-key",
                "scope_id": str(uuid4()),
                "agent_host": "codex",
            }
        )
    )

    environment = load_connection_environment({"PROVENA_API_URL": "http://override.example"}, path)

    assert environment["PROVENA_API_URL"] == "http://override.example"
    assert environment["PROVENA_API_KEY"] == "file-key"
    assert environment["PROVENA_AGENT_HOST"] == "codex"


def test_hook_merge_replaces_only_provena_handlers():
    additions = build_provena_hooks("/new/context", "/new/capture", Path("/config.json"))
    original = {
        "description": "existing",
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {"type": "command", "command": "/other/stop"},
                        {"type": "command", "command": "/old/provena-codex-capture"},
                    ]
                }
            ]
        },
    }

    merged = merge_hooks(original, additions)
    stop_commands = [handler["command"] for group in merged["hooks"]["Stop"] for handler in group["hooks"]]
    assert "/other/stop" in stop_commands
    assert all("/old/provena-codex-capture" != command for command in stop_commands)
    assert any("/new/capture" in command for command in stop_commands)
