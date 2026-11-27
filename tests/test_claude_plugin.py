import json
import stat
import sys
import tomllib
from pathlib import Path
from uuid import uuid4

import pytest

from provena.integrations import capture_hook, context_hook, mcp_server
from provena.integrations.connection_config import host_connection_path, load_host_connection
from provena.integrations.host_setup import claude_duplicate_capture, install_claude, install_claude_plugin_connection

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "provena"


def _write_connection(config_home: Path, scope_id: str) -> Path:
    path = config_home / "provena" / "claude.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"api_url": "http://memory.test", "api_key": "file-key", "scope_id": scope_id, "agent_host": "claude"}))
    return path


def test_host_connection_path_follows_xdg_config_home(tmp_path):
    assert host_connection_path("claude", {"XDG_CONFIG_HOME": str(tmp_path)}) == tmp_path / "provena" / "claude.json"
    with pytest.raises(ValueError):
        host_connection_path("unknown", {})


def test_host_connection_is_inert_until_onboarding_writes_the_file(tmp_path):
    environ = {"XDG_CONFIG_HOME": str(tmp_path)}
    assert load_host_connection(environ, None, "claude") is None

    scope_id = str(uuid4())
    _write_connection(tmp_path, scope_id)
    loaded = load_host_connection(environ, None, "claude")
    assert loaded["PROVENA_API_KEY"] == "file-key"
    assert loaded["PROVENA_AGENT_HOST"] == "claude"


def test_explicit_config_keeps_priority_and_still_fails_loudly(tmp_path):
    environ = {"XDG_CONFIG_HOME": str(tmp_path)}
    with pytest.raises(RuntimeError, match="Could not read Provena connection file"):
        load_host_connection(environ, tmp_path / "missing.json", "claude")


@pytest.mark.parametrize("module", [capture_hook, context_hook])
def test_plugin_hooks_exit_zero_with_a_setup_hint_before_onboarding(module, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["hook", "--host", "claude"])
    monkeypatch.setattr(sys, "stdin", None)  # must not be read before onboarding

    with pytest.raises(SystemExit) as exited:
        module.main()

    assert exited.value.code == 0
    assert "provena quickstart claude --plugin" in capsys.readouterr().err


def test_mcp_connector_explains_missing_plugin_setup(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for name in ("PROVENA_API_KEY", "PROVENA_SCOPE_ID", "PROVENA_CONFIG_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "argv", ["provena-mcp", "--host", "claude"])

    with pytest.raises(SystemExit, match="provena connect claude --plugin"):
        mcp_server.main()


def _user_scoped_install(monkeypatch, tmp_path):
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    settings_path = claude_home / "settings.json"
    state_path = claude_home / ".claude.json"
    settings_path.write_text(json.dumps({"theme": "dark", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/opt/other"}]}]}}))
    state_path.write_text(json.dumps({"mcpServers": {"other": {"command": "/opt/other-mcp"}}}))
    monkeypatch.setattr("provena.integrations.host_setup.shutil.which", lambda name: "/usr/bin/claude")
    install_claude(
        "http://127.0.0.1:8000",
        "old-key",
        str(uuid4()),
        mcp_command="/venv/bin/provena-mcp",
        context_command="/venv/bin/provena-agent-context",
        capture_command="/venv/bin/provena-agent-capture",
        claude_home=claude_home,
        claude_state=state_path,
        config_home=tmp_path / "config",
        environ={},
    )
    return claude_home, settings_path, state_path


def test_plugin_mode_removes_only_provena_user_hooks_and_mcp_entry(monkeypatch, tmp_path):
    claude_home, settings_path, state_path = _user_scoped_install(monkeypatch, tmp_path)
    scope_id = str(uuid4())

    result = install_claude_plugin_connection(
        "http://127.0.0.1:8000/",
        "plugin-key",
        scope_id,
        claude_home=claude_home,
        claude_state=state_path,
        config_home=tmp_path / "config",
        environ={},
    )

    settings = json.loads(settings_path.read_text())
    state = json.loads(state_path.read_text())
    connection_path = tmp_path / "config" / "provena" / "claude.json"
    assert result == {"connection_file": str(connection_path), "removed_user_hooks": "true", "removed_user_mcp_server": "true"}
    assert "provena-agent" not in json.dumps(settings)
    assert settings["theme"] == "dark"
    assert "/opt/other" in json.dumps(settings)
    assert state["mcpServers"] == {"other": {"command": "/opt/other-mcp"}}
    connection = json.loads(connection_path.read_text())
    assert connection == {"api_url": "http://127.0.0.1:8000", "api_key": "plugin-key", "scope_id": scope_id, "agent_host": "claude"}
    assert stat.S_IMODE(connection_path.stat().st_mode) == 0o600


def test_plugin_mode_keeps_an_unrelated_server_named_provena(tmp_path):
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    state_path = claude_home / ".claude.json"
    state_path.write_text(json.dumps({"mcpServers": {"provena": {"command": "/opt/someone-elses-server"}}}))

    result = install_claude_plugin_connection(
        "http://127.0.0.1:8000",
        "plugin-key",
        str(uuid4()),
        claude_home=claude_home,
        claude_state=state_path,
        config_home=tmp_path / "config",
        environ={},
    )

    assert result["removed_user_mcp_server"] == "false"
    assert json.loads(state_path.read_text())["mcpServers"]["provena"]["command"] == "/opt/someone-elses-server"
    assert not (claude_home / "settings.json").exists()


def test_duplicate_capture_needs_both_the_plugin_and_user_hooks(monkeypatch, tmp_path):
    claude_home, settings_path, _ = _user_scoped_install(monkeypatch, tmp_path)
    assert not claude_duplicate_capture(claude_home=claude_home, environ={})

    settings = json.loads(settings_path.read_text())
    settings["enabledPlugins"] = {"provena@provena": True}
    settings_path.write_text(json.dumps(settings))
    assert claude_duplicate_capture(claude_home=claude_home, environ={})

    settings["enabledPlugins"] = {"provena@provena": False}
    settings_path.write_text(json.dumps(settings))
    assert not claude_duplicate_capture(claude_home=claude_home, environ={})


def test_plugin_files_match_the_package_and_never_block_prompts():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    scripts = project["scripts"]
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
    mcp = json.loads((PLUGIN / ".mcp.json").read_text())["mcpServers"]["provena"]

    assert manifest["version"] == project["version"]
    assert [entry["name"] for entry in marketplace["plugins"]] == [manifest["name"]]
    assert (ROOT / marketplace["plugins"][0]["source"]).resolve() == PLUGIN.resolve()
    assert mcp["command"] in scripts and mcp["args"] == ["--host", "claude"]

    commands = [handler["command"] for groups in hooks.values() for group in groups for handler in group["hooks"]]
    assert commands
    for command in commands:
        # A UserPromptSubmit hook that exits 2 blocks the prompt; `|| true` keeps
        # an older or missing CLI from ever doing that.
        assert command.endswith(" || true")
        executable, *arguments = command.removesuffix(" || true").split()
        assert executable in scripts
        assert arguments == ["--host", "claude"]
