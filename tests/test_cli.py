import json
from uuid import uuid4

from provena.cli import build_client_config, render_values


def test_codex_config_uses_isolated_public_connector_package():
    scope_id = str(uuid4())
    rendered = build_client_config("codex", "https://memory.example.test/", "secret-key", scope_id)

    assert "[mcp_servers.provena]" in rendered
    assert '"provena-agent-memory"' in rendered
    assert 'PROVENA_API_URL = "https://memory.example.test"' in rendered
    assert f'PROVENA_SCOPE_ID = "{scope_id}"' in rendered


def test_generic_config_is_valid_mcp_json():
    scope_id = str(uuid4())
    config = json.loads(build_client_config("claude", "http://127.0.0.1:8000", "secret-key", scope_id))

    server = config["mcpServers"]["provena"]
    assert server["command"] == "uvx"
    assert server["args"][-1] == "provena-mcp"
    assert server["env"]["PROVENA_SCOPE_ID"] == scope_id


def test_shell_bootstrap_output_quotes_credentials():
    rendered = render_values({"PROVENA_AGENT_KEY": "contains a space"}, "shell")
    assert rendered == "export PROVENA_AGENT_KEY='contains a space'"
