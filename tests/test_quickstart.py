from pathlib import Path

from provena.quickstart import compose_environment, prepare_release, read_env, start_automatic_memory_and_console, start_core


TEMPLATE = """PROVENA_VERSION=0.0.0
POSTGRES_PASSWORD=replace-with-a-random-database-password
BOOTSTRAP_TOKEN=replace-with-a-long-random-bootstrap-token
PROVENA_API_KEY=
PROVENA_SCOPE_ID=
"""


def test_prepare_release_preserves_initialized_environment(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "PROVENA_VERSION=0.1.6\nPOSTGRES_PASSWORD=existing-db-password\nBOOTSTRAP_TOKEN=existing-bootstrap\nPROVENA_API_KEY=human-key\nPROVENA_SCOPE_ID=scope-id\n"
    )

    def download(url: str, destination: Path):
        assert destination.name != ".env"
        destination.write_text("services: {}\n")

    monkeypatch.setattr("provena.quickstart._download", download)
    values = prepare_release("0.1.10", tmp_path)

    assert values["PROVENA_VERSION"] == "0.1.10"
    assert values["POSTGRES_PASSWORD"] == "existing-db-password"
    assert values["BOOTSTRAP_TOKEN"] == "existing-bootstrap"
    assert values["PROVENA_API_KEY"] == "human-key"
    assert values["PROVENA_SCOPE_ID"] == "scope-id"


def test_prepare_release_generates_separate_new_secrets(monkeypatch, tmp_path):
    def download(url: str, destination: Path):
        destination.write_text(TEMPLATE if destination.name == ".env" else "services: {}\n")

    monkeypatch.setattr("provena.quickstart._download", download)
    values = prepare_release("0.1.10", tmp_path)

    assert values["POSTGRES_PASSWORD"] != values["BOOTSTRAP_TOKEN"]
    assert not values["POSTGRES_PASSWORD"].startswith("replace-with-")
    assert not values["BOOTSTRAP_TOKEN"].startswith("replace-with-")
    assert read_env(tmp_path / ".env") == values


def test_compose_environment_uses_managed_values_over_stale_shell(tmp_path):
    (tmp_path / ".env").write_text(
        "PROVENA_VERSION=0.1.10\nPROVENA_API_KEY=current-key\nPROVENA_SCOPE_ID=current-scope\n"
    )

    environment = compose_environment(
        tmp_path,
        {
            "PATH": "/bin",
            "PROVENA_VERSION": "0.1.5",
            "PROVENA_API_KEY": "stale-key",
            "PROVENA_SCOPE_ID": "stale-scope",
        },
    )

    assert environment["PATH"] == "/bin"
    assert environment["PROVENA_VERSION"] == "0.1.10"
    assert environment["PROVENA_API_KEY"] == "current-key"
    assert environment["PROVENA_SCOPE_ID"] == "current-scope"


def test_start_core_passes_managed_environment_to_compose(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("PROVENA_VERSION=0.1.10\nPOSTGRES_PASSWORD=db-secret\n")
    calls = []
    monkeypatch.setenv("PROVENA_VERSION", "0.1.5")
    monkeypatch.setattr("provena.quickstart.wait_until_ready", lambda api_url: None)

    def runner(command, **kwargs):
        calls.append((command, kwargs))

    start_core(tmp_path, {"POSTGRES_PASSWORD": "db-secret"}, runner=runner)

    assert calls[0][1]["env"]["PROVENA_VERSION"] == "0.1.10"


def test_start_console_passes_managed_credentials_to_compose(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("PROVENA_API_KEY=current-key\nPROVENA_SCOPE_ID=current-scope\n")
    calls = []
    monkeypatch.setenv("PROVENA_API_KEY", "stale-key")
    monkeypatch.setenv("PROVENA_SCOPE_ID", "stale-scope")

    def runner(command, **kwargs):
        calls.append((command, kwargs))

    start_automatic_memory_and_console(tmp_path, runner=runner)

    assert calls[0][1]["env"]["PROVENA_API_KEY"] == "current-key"
    assert calls[0][1]["env"]["PROVENA_SCOPE_ID"] == "current-scope"
