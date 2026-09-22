from pathlib import Path

from provena.quickstart import prepare_release, read_env


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
    values = prepare_release("0.1.7", tmp_path)

    assert values["PROVENA_VERSION"] == "0.1.7"
    assert values["POSTGRES_PASSWORD"] == "existing-db-password"
    assert values["BOOTSTRAP_TOKEN"] == "existing-bootstrap"
    assert values["PROVENA_API_KEY"] == "human-key"
    assert values["PROVENA_SCOPE_ID"] == "scope-id"


def test_prepare_release_generates_separate_new_secrets(monkeypatch, tmp_path):
    def download(url: str, destination: Path):
        destination.write_text(TEMPLATE if destination.name == ".env" else "services: {}\n")

    monkeypatch.setattr("provena.quickstart._download", download)
    values = prepare_release("0.1.7", tmp_path)

    assert values["POSTGRES_PASSWORD"] != values["BOOTSTRAP_TOKEN"]
    assert not values["POSTGRES_PASSWORD"].startswith("replace-with-")
    assert not values["BOOTSTRAP_TOKEN"].startswith("replace-with-")
    assert read_env(tmp_path / ".env") == values
