"""ADR 0026: Docker-free local mode with system PostgreSQL."""

import json
import os
import socket
import stat
import subprocess
import urllib.request
from argparse import Namespace
from pathlib import Path

import pytest

from provena import local_server as ls


def _fake_postgres(root: Path, major: int, *, pgvector: bool = True) -> Path:
    bindir = root / "bin"
    bindir.mkdir(parents=True)
    for name in ("pg_ctl", "initdb"):
        (bindir / name).write_text("#!/bin/sh\nexit 0\n")
    (bindir / "postgres").write_text(f"#!/bin/sh\necho 'postgres (PostgreSQL) {major}.3'\n")
    for name in ("pg_ctl", "initdb", "postgres"):
        (bindir / name).chmod(0o755)
    if pgvector:
        extension = root / "share" / "postgresql" / "extension"
        extension.mkdir(parents=True)
        (extension / "vector.control").write_text("default_version = '0.8.0'\n")
    return bindir


def test_explicit_bindir_is_the_only_candidate(tmp_path):
    first = _fake_postgres(tmp_path / "a", 17)
    candidates = ls.candidate_bindirs({"PROVENA_PG_BINDIR": str(first), "PATH": "/usr/bin"}, run=lambda *a, **k: subprocess.CompletedProcess(a, 1, "", ""))
    assert candidates == [first]


def test_find_postgres_accepts_16_plus_with_pgvector(tmp_path):
    bindir = _fake_postgres(tmp_path, 18)
    assert ls.find_postgres({"PROVENA_PG_BINDIR": str(bindir), "PATH": ""}) == (bindir, 18)


def test_find_postgres_explains_old_versions_and_missing_pgvector(tmp_path):
    old = _fake_postgres(tmp_path / "old", 15)
    with pytest.raises(ls.LocalServerError, match="PostgreSQL 15; Provena needs 16 or newer"):
        ls.find_postgres({"PROVENA_PG_BINDIR": str(old), "PATH": ""})

    bare = _fake_postgres(tmp_path / "bare", 17, pgvector=False)
    with pytest.raises(ls.LocalServerError, match="not the pgvector extension") as error:
        ls.find_postgres({"PROVENA_PG_BINDIR": str(bare), "PATH": ""})
    assert "Install it with:" in str(error.value)


def test_pgvector_check_is_tied_to_the_checked_installation(tmp_path):
    # A Debian-layout server's extensions only count for that server, never for another bindir.
    bare = _fake_postgres(tmp_path / "bare", 17, pgvector=False)
    assert Path("/usr/share/postgresql/17/extension") not in ls.extension_dirs(bare, 17)
    assert Path("/usr/share/postgresql/17/extension") in ls.extension_dirs(Path("/usr/lib/postgresql/17/bin"), 17)


@pytest.mark.parametrize(
    ("system", "os_release", "expected"),
    [
        ("Darwin", None, "brew install postgresql@18 pgvector"),
        ("Linux", "ID=ubuntu\nID_LIKE=debian\n", "sudo apt install postgresql-16 postgresql-16-pgvector"),
        ("Linux", "ID=debian\n", "sudo apt install postgresql-17 postgresql-17-pgvector"),
        ("Linux", "ID=arch\n", "sudo pacman -S postgresql pgvector"),
        ("Linux", "ID=endeavouros\nID_LIKE=arch\n", "sudo pacman -S postgresql pgvector"),
        ("Windows", None, "PROVENA_PG_BINDIR"),
    ],
)
def test_install_hints_name_the_platform_packages(tmp_path, system, os_release, expected):
    release = tmp_path / "os-release"
    if os_release:
        release.write_text(os_release)
    assert expected in ls.install_hint(system=system, os_release=release)


def test_prepare_state_creates_protected_secrets_once(tmp_path):
    first = ls.prepare_state(tmp_path / "state")
    second = ls.prepare_state(tmp_path / "state")
    assert first["PROVENA_LOCAL_MODE"] == "system"
    assert first["POSTGRES_PASSWORD"] == second["POSTGRES_PASSWORD"] and len(first["POSTGRES_PASSWORD"]) >= 32
    assert stat.S_IMODE((tmp_path / "state" / ".env").stat().st_mode) == 0o600


def test_prepare_state_refuses_a_docker_state_directory(tmp_path):
    (tmp_path / "compose.yaml").write_text("services: {}\n")
    (tmp_path / ".env").write_text("POSTGRES_PASSWORD=x\n")
    with pytest.raises(ls.LocalServerError, match="belongs to a Docker installation"):
        ls.prepare_state(tmp_path)


def test_major_version_change_is_refused_without_running_initdb(tmp_path):
    ls.prepare_state(tmp_path)
    (tmp_path / "postgres").mkdir()
    (tmp_path / "postgres" / "PG_VERSION").write_text("17\n")
    calls = []
    with pytest.raises(ls.LocalServerError, match="created with PostgreSQL 17.*pg_dump"):
        ls.init_cluster(tmp_path, Path("/opt/pg18/bin"), 18, run=lambda *a, **k: calls.append(a))
    assert calls == []


def test_api_environment_replaces_stale_shell_settings():
    values = {"POSTGRES_PASSWORD": "pw", "PROVENA_PG_PORT": "5555", "BOOTSTRAP_TOKEN": "boot"}
    environment = ls.api_environment(values, {"MEMORY_PROVIDER": "none"}, {"PATH": "/bin", "DATABASE_URL": "postgresql://stale", "OLLAMA_BASE_URL": "http://stale"})
    assert environment["DATABASE_URL"] == "postgresql+psycopg://provena:pw@127.0.0.1:5555/provena"
    assert environment["MEMORY_PROVIDER"] == "none" and "OLLAMA_BASE_URL" not in environment
    assert environment["PATH"] == "/bin"


def test_migrations_are_found_in_development_and_installed_layouts():
    location = ls.migrations_location()
    assert (location / "env.py").is_file()
    assert any(path.name.endswith("_fulltext_retrieval_method.py") for path in (location / "versions").iterdir())


def test_no_docker_quickstart_never_touches_docker(monkeypatch, tmp_path):
    from provena import cli

    calls = []
    monkeypatch.setattr("provena.cli.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr("provena.cli.require_local_tools", lambda client: calls.append("docker-check"))
    monkeypatch.setattr("provena.cli.prepare_release", lambda *a: calls.append("docker-release"))
    monkeypatch.setattr("provena.cli.start_core", lambda *a: calls.append("docker-core"))
    monkeypatch.setattr("provena.cli.start_memory_and_console", lambda *a: calls.append("docker-models"))
    monkeypatch.setattr("provena.cli.host_ollama_models", lambda: None)
    monkeypatch.setattr(ls, "require_server_dependencies", lambda: None)
    monkeypatch.setattr(ls, "start_service", lambda state_dir, memory: calls.append(("local", memory)) or {"postgres_major": 17, "postgres_bindir": "/usr/lib/postgresql/17/bin"})
    monkeypatch.setattr(ls, "wait_for_api", lambda *a, **k: None)
    monkeypatch.setattr("provena.cli.wait_until_ready", lambda api_url: None)
    monkeypatch.setattr("provena.cli._existing_quickstart_connection", lambda api_url, client: None)
    monkeypatch.setattr("provena.cli.bootstrap_workspace", lambda *a: {"PROVENA_AGENT_KEY": "agent", "PROVENA_HUMAN_KEY": "human", "PROVENA_SCOPE_ID": "00000000-0000-4000-8000-000000000000"})
    monkeypatch.setattr("provena.cli.install_claude_plugin_connection", lambda *a: {"connection_file": "/config/claude.json"})

    args = Namespace(client="claude", state_dir=str(tmp_path / "local"), organization="o", project="p", plugin=True, no_docker=True, no_local_models=False, wait_for_models=False, no_host_ollama=False)
    assert cli._quickstart_command(args) == 0

    assert not [call for call in calls if isinstance(call, str) and call.startswith("docker")]
    assert ("local", {"MEMORY_PROVIDER": "none"}) in calls


def test_local_memory_settings_use_a_host_ollama_directly(monkeypatch):
    from provena import cli

    monkeypatch.setattr("provena.cli.host_ollama_models", lambda: {"qwen2.5:1.5b"})
    mode, settings, _ = cli._local_memory_settings(Namespace(no_local_models=False, no_host_ollama=False))
    assert mode == "host" and settings["OLLAMA_BASE_URL"] == "http://127.0.0.1:11434"
    assert cli._local_memory_settings(Namespace(no_local_models=True, no_host_ollama=False))[0] == "none"


# --- real PostgreSQL ------------------------------------------------------------------

def _port_free(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


@pytest.mark.skipif(not os.getenv("PROVENA_PG_BINDIR"), reason="set PROVENA_PG_BINDIR to a PostgreSQL 16+ bin directory with pgvector")
def test_system_postgres_service_end_to_end(tmp_path):
    if not _port_free(ls.API_PORT):
        pytest.skip("port 8000 is in use")
    state = tmp_path / "state"
    ls.prepare_state(state)
    try:
        info = ls.start_service(state, {"MEMORY_PROVIDER": "none"})
        ls.wait_for_api()
        assert info["cluster_created"] is True and info["postgres_major"] >= 16
        assert stat.S_IMODE((state / "postgres").stat().st_mode) == 0o700
        assert "unix_socket_directories" in (state / "postgres" / "postmaster.opts").read_text()
        assert "timezone=UTC" in (state / "postgres" / "postmaster.opts").read_text()
        assert "scram-sha-256" in (state / "postgres" / "pg_hba.conf").read_text()
        assert "trust" not in [line.split()[-1] for line in (state / "postgres" / "pg_hba.conf").read_text().splitlines() if line.strip() and not line.startswith("#")]

        from provena.cli import bootstrap_workspace, request_json

        values = ls.read_env(state / ".env")
        api = f"http://127.0.0.1:{ls.API_PORT}"
        workspace = bootstrap_workspace(api, values["BOOTSTRAP_TOKEN"], "Local development", "e2e")
        agent = {"X-API-Key": workspace["PROVENA_AGENT_KEY"]}
        scope = workspace["PROVENA_SCOPE_ID"]
        saved = request_json(api, "/memories", method="POST", headers=agent, body={"scope_id": scope, "source_kind": "user_statement", "text": "CI runs on GitHub Actions.", "proposition": {"subject": "project", "predicate": "ci_provider", "value": {"name": "GitHub Actions"}}})
        found = request_json(api, f"/claims?scope_id={scope}&q=which%20ci%20provider", headers=agent)
        assert [claim["id"] for claim in found["claims"]] == [saved["claim"]["id"]]

        assert ls.stop_service(state) == {"api_stopped": True, "postgres_stopped": True}
        assert ls.service_status(state)["postgres"] == "stopped"

        restarted = ls.start_service(state)
        ls.wait_for_api()
        assert restarted["cluster_created"] is False and restarted["memory"] == {"MEMORY_PROVIDER": "none"}
        again = request_json(api, f"/claims?scope_id={scope}&predicate=ci_provider", headers=agent)
        assert again["claims"][0]["value"] == {"name": "GitHub Actions"}
        with urllib.request.urlopen(f"{api}/intelligence", timeout=5) as response:
            assert json.load(response)["provider"] == "none"
    finally:
        ls.stop_service(state)
