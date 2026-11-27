import subprocess
from pathlib import Path

import pytest

from provena.quickstart import compose_environment, prepare_release, read_env, require_local_tools, start_automatic_memory_and_console, start_core


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


def test_require_local_tools_names_missing_docker(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None if name == "docker" else f"/usr/bin/{name}")

    with pytest.raises(RuntimeError, match="docker"):
        require_local_tools("codex")


def test_require_local_tools_names_missing_client(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/docker" if name == "docker" else None)

    with pytest.raises(RuntimeError, match="codex"):
        require_local_tools("codex")


def test_require_local_tools_rejects_broken_compose(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="Docker Compose is required"):
        require_local_tools("claude")

    assert calls == [["docker", "compose", "version"]]


def test_require_local_tools_passes_when_tools_available(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="Docker Compose version v2", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    assert require_local_tools("gemini") is None


def test_model_mode_prefers_explicit_choices_then_host_ollama():
    from provena.quickstart import choose_model_mode

    assert choose_model_mode(no_local_models=True, wait_for_models=False, allow_host_ollama=True, host_models={"x"}) == "none"
    assert choose_model_mode(no_local_models=False, wait_for_models=True, allow_host_ollama=True, host_models={"x"}) == "wait"
    assert choose_model_mode(no_local_models=False, wait_for_models=False, allow_host_ollama=True, host_models=set()) == "host"
    assert choose_model_mode(no_local_models=False, wait_for_models=False, allow_host_ollama=False, host_models={"x"}) == "background"
    assert choose_model_mode(no_local_models=False, wait_for_models=False, allow_host_ollama=True, host_models=None) == "background"


def test_missing_models_accepts_latest_tags():
    from provena.quickstart import missing_models

    assert missing_models({"qwen2.5:1.5b", "nomic-embed-text:latest"}) == []
    assert missing_models({"llama3:latest"}) == ["qwen2.5:1.5b", "nomic-embed-text"]


def test_host_ollama_detection_returns_none_when_nothing_listens():
    from provena.quickstart import host_ollama_models

    assert host_ollama_models("http://127.0.0.1:9", timeout=0.5) is None


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("none", [["--profile", "console", "up", "-d"]]),
        ("background", [["-f", "compose.ollama.yaml", "up", "-d", "ollama-models"], ["-f", "compose.ollama.yaml", "--profile", "console", "up", "-d", "--no-deps", "api", "console"]]),
        ("host", [["-f", "compose.host-ollama.yaml", "--profile", "console", "up", "-d", "--no-deps", "api", "console"]]),
    ],
)
def test_model_modes_do_not_wait_for_downloads(tmp_path, mode, expected):
    from provena.quickstart import start_memory_and_console

    (tmp_path / ".env").write_text("PROVENA_VERSION=0.1.15\n")
    calls = []
    start_memory_and_console(tmp_path, mode, runner=lambda command, **kwargs: calls.append([part.replace(str(tmp_path) + "/", "") for part in command]))

    assert len(calls) == len(expected)
    for call, tail in zip(calls, expected):
        assert call[:5] == ["docker", "compose", "--project-directory", str(tmp_path), "-f"]
        rendered = " ".join(call)
        assert " ".join(tail) in rendered
    if mode == "none":
        assert "ollama" not in " ".join(calls[0])
