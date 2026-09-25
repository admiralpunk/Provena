import json
from argparse import Namespace
from uuid import uuid4

from provena.cli import _ensure_console_reviewer, _existing_quickstart_connection, _quickstart_command, build_client_config, installed_mcp_command, render_values


def test_installed_connector_prefers_current_python_environment(monkeypatch, tmp_path):
    connector = tmp_path / "provena-mcp"
    connector.touch()
    monkeypatch.setattr("provena.cli.sysconfig.get_path", lambda name: str(tmp_path))
    monkeypatch.setattr("provena.cli.shutil.which", lambda name: "/wrong/environment/provena-mcp")

    assert installed_mcp_command() == str(connector.resolve())


def test_codex_config_uses_installed_connector():
    scope_id = str(uuid4())
    rendered = build_client_config(
        "codex",
        "https://memory.example.test/",
        "secret-key",
        scope_id,
        "/opt/provena/bin/provena-mcp",
    )

    assert "[mcp_servers.provena]" in rendered
    assert 'command = "/opt/provena/bin/provena-mcp"' in rendered
    assert "uvx" not in rendered
    assert 'PROVENA_API_URL = "https://memory.example.test"' in rendered
    assert f'PROVENA_SCOPE_ID = "{scope_id}"' in rendered


def test_generic_config_is_valid_mcp_json_for_installed_connector():
    scope_id = str(uuid4())
    config = json.loads(
        build_client_config(
            "claude",
            "http://127.0.0.1:8000",
            "secret-key",
            scope_id,
            "/opt/provena/bin/provena-mcp",
        )
    )

    server = config["mcpServers"]["provena"]
    assert server["command"] == "/opt/provena/bin/provena-mcp"
    assert "args" not in server
    assert server["env"]["PROVENA_SCOPE_ID"] == scope_id


def test_shell_bootstrap_output_quotes_credentials():
    rendered = render_values({"PROVENA_AGENT_KEY": "contains a space"}, "shell")
    assert rendered == "export PROVENA_AGENT_KEY='contains a space'"


def test_quickstart_keeps_valid_human_console_credential(monkeypatch, tmp_path):
    requests = []

    def request_json(api_url, path, **kwargs):
        requests.append((path, kwargs))
        return {"principal": {"role": "human"}}

    monkeypatch.setattr("provena.cli.request_json", request_json)
    _ensure_console_reviewer(
        "http://127.0.0.1:8000",
        tmp_path,
        {"BOOTSTRAP_TOKEN": "bootstrap", "PROVENA_API_KEY": "reviewer", "PROVENA_SCOPE_ID": "scope"},
        {"PROVENA_API_KEY": "agent", "PROVENA_SCOPE_ID": "scope", "PROVENA_ORG_ID": "organization"},
    )

    assert len(requests) == 1
    assert requests[0][0] == "/operator/context?scope_id=scope"


def test_quickstart_replaces_invalid_console_credential(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("BOOTSTRAP_TOKEN=bootstrap\nPROVENA_API_KEY=stale\nPROVENA_SCOPE_ID=scope\n")
    requests = []

    def request_json(api_url, path, **kwargs):
        requests.append((path, kwargs))
        if path.startswith("/operator/context"):
            raise RuntimeError("invalid API key")
        return {"api_key": "new-reviewer"}

    monkeypatch.setattr("provena.cli.request_json", request_json)
    _ensure_console_reviewer(
        "http://127.0.0.1:8000",
        tmp_path,
        {"BOOTSTRAP_TOKEN": "bootstrap", "PROVENA_API_KEY": "stale", "PROVENA_SCOPE_ID": "scope"},
        {"PROVENA_API_KEY": "agent", "PROVENA_SCOPE_ID": "scope", "PROVENA_ORG_ID": "organization"},
    )

    assert requests[1][0] == "/organizations/organization/credentials"
    assert requests[1][1]["headers"] == {"X-Bootstrap-Token": "bootstrap"}
    assert "PROVENA_API_KEY=new-reviewer" in env_path.read_text()


def test_quickstart_dispatches_selected_host_installer(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("provena.cli.require_local_tools", lambda client: calls.append(("tools", client)))
    monkeypatch.setattr("provena.cli.prepare_release", lambda version, state_dir: {"BOOTSTRAP_TOKEN": "bootstrap"})
    monkeypatch.setattr("provena.cli.start_core", lambda state_dir, deployment: None)
    monkeypatch.setattr(
        "provena.cli._existing_quickstart_connection",
        lambda api_url, client: {
            "PROVENA_API_KEY": "agent-key",
            "PROVENA_SCOPE_ID": str(uuid4()),
            "PROVENA_ORG_ID": str(uuid4()),
        },
    )
    monkeypatch.setattr("provena.cli._ensure_console_reviewer", lambda *args: None)
    monkeypatch.setattr("provena.cli.installed_mcp_command", lambda: "/bin/provena-mcp")
    monkeypatch.setattr("provena.cli.installed_command", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        "provena.cli.install_host",
        lambda host, *args, **kwargs: calls.append(("install", host)) or {"connection_file": "/config/claude.json"},
    )
    monkeypatch.setattr("provena.cli.start_automatic_memory_and_console", lambda state_dir: None)
    monkeypatch.setattr("provena.cli.wait_until_ready", lambda api_url: None)

    result = _quickstart_command(
        Namespace(client="claude", state_dir=str(tmp_path), organization="Local development", project="provena-demo")
    )

    assert result == 0
    assert ("tools", "claude") in calls
    assert ("install", "claude") in calls


def test_quickstart_reuses_a_valid_connection_from_another_host(monkeypatch, tmp_path):
    scope_id = str(uuid4())
    config_directory = tmp_path / "provena"
    config_directory.mkdir()
    (config_directory / "codex.json").write_text(
        json.dumps(
            {
                "api_url": "http://127.0.0.1:8000",
                "api_key": "shared-agent-key",
                "scope_id": scope_id,
                "agent_host": "codex",
            }
        )
    )
    monkeypatch.setattr("provena.cli.default_config_home", lambda: tmp_path)
    monkeypatch.setattr(
        "provena.cli.request_json",
        lambda api_url, path, **kwargs: {"organization": {"id": "organization-id"}},
    )

    existing = _existing_quickstart_connection("http://127.0.0.1:8000", "claude")

    assert existing == {
        "PROVENA_API_URL": "http://127.0.0.1:8000",
        "PROVENA_API_KEY": "shared-agent-key",
        "PROVENA_SCOPE_ID": scope_id,
        "PROVENA_AGENT_HOST": "codex",
        "PROVENA_ORG_ID": "organization-id",
    }
