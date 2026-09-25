import json
import stat
import subprocess
from pathlib import Path
from uuid import uuid4

from provena.integrations.connection_config import load_connection_environment
from provena.integrations.host_setup import build_provena_hooks, install_claude, install_codex, install_gemini, merge_hooks


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
    monkeypatch.setattr("provena.integrations.host_setup.shutil.which", lambda name: "/usr/bin/codex")
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


def test_claude_install_preserves_settings_and_uses_protected_connection_file(monkeypatch, tmp_path):
    claude_home = tmp_path / "claude"
    config_home = tmp_path / "config"
    claude_home.mkdir()
    settings_path = claude_home / "settings.json"
    state_path = claude_home / ".claude.json"
    settings_path.write_text(json.dumps({"theme": "dark", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/opt/other"}]}]}}))
    state_path.write_text(json.dumps({"projects": {"/work": {}}, "mcpServers": {"other": {"command": "/opt/other-mcp"}}}))
    monkeypatch.setattr("provena.integrations.host_setup.shutil.which", lambda name: "/usr/bin/claude")

    scope_id = str(uuid4())
    result = install_claude(
        "http://127.0.0.1:8000/",
        "claude-agent-secret",
        scope_id,
        mcp_command="/venv/bin/provena-mcp",
        context_command="/venv/bin/provena-agent-context",
        capture_command="/venv/bin/provena-agent-capture",
        claude_home=claude_home,
        claude_state=state_path,
        config_home=config_home,
        environ={},
    )

    connection_path = config_home / "provena" / "claude.json"
    settings = json.loads(settings_path.read_text())
    state = json.loads(state_path.read_text())
    assert result["claude_config"] == str(state_path)
    assert settings["theme"] == "dark"
    assert "/opt/other" in json.dumps(settings)
    assert "UserPromptSubmit" in settings["hooks"]
    assert "Stop" in settings["hooks"]
    assert state["projects"] == {"/work": {}}
    assert state["mcpServers"]["other"]["command"] == "/opt/other-mcp"
    assert state["mcpServers"]["provena"] == {
        "type": "stdio",
        "command": "/venv/bin/provena-mcp",
        "args": ["--config", str(connection_path)],
    }
    assert "claude-agent-secret" not in settings_path.read_text()
    assert "claude-agent-secret" not in state_path.read_text()
    assert json.loads(connection_path.read_text())["agent_host"] == "claude"
    assert stat.S_IMODE(connection_path.stat().st_mode) == 0o600


def test_gemini_install_merges_mcp_and_native_hooks_idempotently(monkeypatch, tmp_path):
    gemini_home = tmp_path / "gemini"
    config_home = tmp_path / "config"
    gemini_home.mkdir()
    settings_path = gemini_home / "settings.json"
    settings_path.write_text(json.dumps({"ui": {"theme": "ANSI"}, "mcpServers": {"other": {"command": "/opt/other"}}}))
    monkeypatch.setattr("provena.integrations.host_setup.shutil.which", lambda name: "/usr/bin/gemini")

    scope_id = str(uuid4())
    arguments = {
        "mcp_command": "/venv/bin/provena-mcp",
        "context_command": "/venv/bin/provena-agent-context",
        "capture_command": "/venv/bin/provena-agent-capture",
        "gemini_home": gemini_home,
        "config_home": config_home,
        "environ": {},
    }
    install_gemini("http://127.0.0.1:8000", "gemini-agent-secret", scope_id, **arguments)
    install_gemini("http://127.0.0.1:8000", "gemini-agent-secret", scope_id, **arguments)

    connection_path = config_home / "provena" / "gemini.json"
    settings = json.loads(settings_path.read_text())
    assert settings["ui"] == {"theme": "ANSI"}
    assert settings["mcpServers"]["other"]["command"] == "/opt/other"
    assert settings["mcpServers"]["provena"] == {
        "command": "/venv/bin/provena-mcp",
        "args": ["--config", str(connection_path)],
    }
    assert len(settings["hooks"]["BeforeAgent"]) == 1
    assert len(settings["hooks"]["AfterAgent"]) == 1
    assert settings["hooks"]["BeforeAgent"][0]["sequential"] is False
    assert "gemini-agent-secret" not in settings_path.read_text()
    assert json.loads(connection_path.read_text())["agent_host"] == "gemini"
