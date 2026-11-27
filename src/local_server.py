"""Docker-free local mode: a private PostgreSQL cluster and API process (ADR 0026).

Provena finds a PostgreSQL 16+ installation with pgvector from the system package
manager but never installs packages or runs sudo. It creates a user-owned cluster in
the state directory, listening on 127.0.0.1 only with SCRAM authentication and no Unix
socket, and supervises only the processes it started.
"""

from __future__ import annotations

import json
import os
import platform
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Mapping

from .quickstart import read_env, update_env

MIN_MAJOR = 16
PG_PROGRAMS = ("pg_ctl", "initdb", "postgres")
API_PORT = 8000
SERVER_MODULES = ("fastapi", "uvicorn", "sqlalchemy", "psycopg", "alembic", "pgvector", "pydantic_settings")

Runner = Callable[..., subprocess.CompletedProcess[str]]


class LocalServerError(RuntimeError):
    """A problem the user can fix; the message names the next step."""


# --- discovery -----------------------------------------------------------------------


def _has_programs(directory: Path) -> bool:
    return all((directory / name).is_file() and os.access(directory / name, os.X_OK) for name in PG_PROGRAMS)


def candidate_bindirs(environ: Mapping[str, str] | None = None, *, run: Runner = subprocess.run) -> list[Path]:
    """Directories that may hold PostgreSQL server programs, in ADR 0026 order."""

    values = os.environ if environ is None else environ
    candidates: list[Path] = []
    if values.get("PROVENA_PG_BINDIR"):
        candidates.append(Path(values["PROVENA_PG_BINDIR"]).expanduser())
    pg_config = shutil.which("pg_config", path=values.get("PATH"))
    if pg_config:
        result = run([pg_config, "--bindir"], text=True, capture_output=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            candidates.append(Path(result.stdout.strip()))
    brew = shutil.which("brew", path=values.get("PATH"))
    if brew:
        for formula in ("postgresql@18", "postgresql@19"):
            result = run([brew, "--prefix", formula], text=True, capture_output=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                candidates.append(Path(result.stdout.strip()) / "bin")
    debian = Path("/usr/lib/postgresql")
    if debian.is_dir():
        majors = sorted((entry for entry in debian.iterdir() if entry.name.isdigit()), key=lambda entry: int(entry.name), reverse=True)
        candidates.extend(entry / "bin" for entry in majors)
    postgres = shutil.which("postgres", path=values.get("PATH"))
    if postgres:
        candidates.append(Path(postgres).parent)
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def server_major(bindir: Path, *, run: Runner = subprocess.run) -> int:
    result = run([str(bindir / "postgres"), "-V"], text=True, capture_output=True, check=False)
    match = re.search(r"PostgreSQL\)?\s+(\d+)", result.stdout)
    if result.returncode or not match:
        raise LocalServerError(f"Could not read the PostgreSQL version from {bindir / 'postgres'}: {result.stderr.strip() or result.stdout.strip()}")
    return int(match.group(1))


def extension_dirs(bindir: Path, major: int, *, run: Runner = subprocess.run) -> list[Path]:
    dirs: list[Path] = []
    pg_config = bindir / "pg_config"
    if pg_config.is_file():
        result = run([str(pg_config), "--sharedir"], text=True, capture_output=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            dirs.append(Path(result.stdout.strip()) / "extension")
    prefix = bindir.parent
    dirs.extend(
        [
            prefix / "share" / "extension",
            prefix / "share" / "postgresql" / "extension",
            prefix / "share" / f"postgresql@{major}" / "extension",
            Path("/usr/share/postgresql") / str(major) / "extension",
            Path("/usr/share/postgresql") / "extension",
        ]
    )
    return dirs


def has_pgvector(bindir: Path, major: int, *, run: Runner = subprocess.run) -> bool:
    return any((directory / "vector.control").is_file() for directory in extension_dirs(bindir, major, run=run))


def install_hint(environ: Mapping[str, str] | None = None, *, system: str | None = None, os_release: Path = Path("/etc/os-release")) -> str:
    system = system or platform.system()
    if system == "Darwin":
        return "brew install postgresql@18 pgvector"
    if system == "Linux" and os_release.is_file():
        info = read_env(os_release)
        family = {info.get("ID", ""), *info.get("ID_LIKE", "").split()}
        if "arch" in family:
            return "sudo pacman -S postgresql pgvector"
        if info.get("ID") == "ubuntu":
            return "sudo apt install postgresql-16 postgresql-16-pgvector"
        if "debian" in family:
            return "sudo apt install postgresql-17 postgresql-17-pgvector"
    return "install PostgreSQL 16 or newer and pgvector with your package manager, or set PROVENA_PG_BINDIR to its bin directory"


def find_postgres(environ: Mapping[str, str] | None = None, *, run: Runner = subprocess.run) -> tuple[Path, int]:
    """Return (bindir, major) for the first PostgreSQL 16+ with pgvector, or explain what to install."""

    problems: list[str] = []
    for bindir in candidate_bindirs(environ, run=run):
        if not _has_programs(bindir):
            continue
        try:
            major = server_major(bindir, run=run)
        except LocalServerError as error:
            problems.append(str(error))
            continue
        if major < MIN_MAJOR:
            problems.append(f"{bindir} has PostgreSQL {major}; Provena needs {MIN_MAJOR} or newer")
            continue
        if not has_pgvector(bindir, major, run=run):
            problems.append(f"{bindir} has PostgreSQL {major} but not the pgvector extension")
            continue
        return bindir, major
    detail = "; ".join(problems) if problems else "no PostgreSQL server programs (pg_ctl, initdb, postgres) were found"
    raise LocalServerError(f"Provena needs a local PostgreSQL {MIN_MAJOR}+ with pgvector for --no-docker: {detail}. Install it with: {install_hint(environ)}")


def require_server_dependencies() -> None:
    import importlib.util

    missing = [name for name in SERVER_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        raise LocalServerError(
            f"The Provena server components are not installed ({', '.join(missing)}). "
            "Run: pipx install --force 'provena-agent-memory[server]'"
        )


def migrations_location() -> Path:
    """Alembic scripts shipped in the wheel, or the repository's alembic/ in development."""
    import provena

    package_root = Path(provena.__file__).resolve().parent
    for candidate in (package_root / "migrations", package_root.parent / "alembic"):
        if (candidate / "env.py").is_file() and (candidate / "versions").is_dir():
            return candidate
    raise LocalServerError("Provena's database migrations are missing from this installation; reinstall provena-agent-memory[server]")


# --- state ---------------------------------------------------------------------------


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def prepare_state(state_dir: Path) -> dict[str, str]:
    """Create or reuse the protected state file for the Docker-free mode."""

    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "logs").mkdir(exist_ok=True)
    env_path = state_dir / ".env"
    if not env_path.exists():
        env_path.touch(mode=0o600)
    values = read_env(env_path)
    if values.get("PROVENA_LOCAL_MODE") not in (None, "", "system"):
        raise LocalServerError(f"{state_dir} belongs to a Docker installation; pass a different --state-dir for --no-docker")
    if (state_dir / "compose.yaml").exists() and not values.get("PROVENA_LOCAL_MODE"):
        raise LocalServerError(f"{state_dir} belongs to a Docker installation; pass a different --state-dir for --no-docker")
    updates = {"PROVENA_LOCAL_MODE": "system"}
    for key in ("POSTGRES_PASSWORD", "BOOTSTRAP_TOKEN"):
        if not values.get(key) or values[key].startswith("replace-with-"):
            updates[key] = secrets.token_urlsafe(32)
    update_env(env_path, updates)
    return read_env(env_path)


def is_system_mode(state_dir: Path) -> bool:
    env_path = state_dir / ".env"
    return env_path.is_file() and read_env(env_path).get("PROVENA_LOCAL_MODE") == "system"


def database_url(values: Mapping[str, str], database: str = "provena") -> str:
    return f"postgresql+psycopg://provena:{values['POSTGRES_PASSWORD']}@127.0.0.1:{values['PROVENA_PG_PORT']}/{database}"


# --- PostgreSQL ----------------------------------------------------------------------


def data_dir(state_dir: Path) -> Path:
    return state_dir / "postgres"


def init_cluster(state_dir: Path, bindir: Path, major: int, *, run: Runner = subprocess.run) -> bool:
    """Create the private cluster once. Returns True when it was created now."""

    data = data_dir(state_dir)
    values = read_env(state_dir / ".env")
    if (data / "PG_VERSION").is_file():
        cluster_major = int((data / "PG_VERSION").read_text().strip())
        if cluster_major != major:
            raise LocalServerError(
                f"The Provena database in {data} was created with PostgreSQL {cluster_major}, but {bindir} is PostgreSQL {major}. "
                f"Provena never upgrades it automatically: start PostgreSQL {cluster_major} with PROVENA_PG_BINDIR, export with pg_dump, "
                "then restore into a new state directory."
            )
        return False
    descriptor, password_file = tempfile.mkstemp(prefix=".pw-", dir=state_dir)
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(values["POSTGRES_PASSWORD"])
        result = run(
            [str(bindir / "initdb"), "-D", str(data), "-U", "provena", f"--pwfile={password_file}", "--auth=scram-sha-256", "--encoding=UTF8", "--no-instructions"],
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        os.unlink(password_file)
    if result.returncode:
        raise LocalServerError(f"initdb failed: {result.stderr.strip() or result.stdout.strip()}")
    update_env(state_dir / ".env", {"PROVENA_PG_MAJOR": str(major)})
    return True


def postgres_running(state_dir: Path, bindir: Path, *, run: Runner = subprocess.run) -> bool:
    if not (data_dir(state_dir) / "PG_VERSION").is_file():
        return False
    result = run([str(bindir / "pg_ctl"), "-D", str(data_dir(state_dir)), "status"], text=True, capture_output=True, check=False)
    return result.returncode == 0


def start_postgres(state_dir: Path, bindir: Path, *, run: Runner = subprocess.run) -> int:
    values = read_env(state_dir / ".env")
    port = int(values.get("PROVENA_PG_PORT") or 0)
    if postgres_running(state_dir, bindir, run=run) and port:
        return port
    if not port:
        port = free_port()
        update_env(state_dir / ".env", {"PROVENA_PG_PORT": str(port)})
    options = f"-p {port} -c listen_addresses=127.0.0.1 -c unix_socket_directories=''"
    result = run(
        [str(bindir / "pg_ctl"), "-D", str(data_dir(state_dir)), "-l", str(state_dir / "logs" / "postgres.log"), "-o", options, "-w", "-t", "60", "start"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise LocalServerError(f"PostgreSQL did not start; see {state_dir / 'logs' / 'postgres.log'}: {result.stderr.strip() or result.stdout.strip()}")
    return port


def stop_postgres(state_dir: Path, bindir: Path, *, run: Runner = subprocess.run) -> bool:
    if not postgres_running(state_dir, bindir, run=run):
        return False
    run([str(bindir / "pg_ctl"), "-D", str(data_dir(state_dir)), "-m", "fast", "-w", "stop"], text=True, capture_output=True, check=False)
    return True


def ensure_database(values: Mapping[str, str]) -> None:
    """Create the provena database and confirm pgvector loads in this server."""
    import psycopg

    admin = database_url(values, "postgres").replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(admin, autocommit=True) as connection:
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname = 'provena'").fetchone():
            connection.execute("CREATE DATABASE provena")
        if not connection.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'").fetchone():
            raise LocalServerError("This PostgreSQL server cannot load pgvector; install the pgvector package that matches its major version")


def migrate(values: Mapping[str, str]) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", str(migrations_location()))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url(values)
    try:
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


# --- API process ---------------------------------------------------------------------


def _pid_alive(pid: int) -> bool:
    try:
        # Reap the API if this process started it; an exited child stays a zombie
        # that `kill(pid, 0)` still reports as alive.
        if os.waitpid(pid, os.WNOHANG)[0] == pid:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def api_pid(state_dir: Path) -> int | None:
    path = state_dir / "api.pid"
    if not path.is_file():
        return None
    try:
        pid = int(path.read_text().strip())
    except ValueError:
        return None
    return pid if _pid_alive(pid) else None


def api_environment(values: Mapping[str, str], memory: Mapping[str, str], environ: Mapping[str, str] | None = None) -> dict[str, str]:
    process = dict(os.environ if environ is None else environ)
    for key in ("DATABASE_URL", "BOOTSTRAP_TOKEN", "MEMORY_PROVIDER", "OLLAMA_BASE_URL", "EXTRACTION_MODEL", "EMBEDDING_MODEL", "OPENAI_API_KEY"):
        process.pop(key, None)
    process.update({"DATABASE_URL": database_url(values), "BOOTSTRAP_TOKEN": values["BOOTSTRAP_TOKEN"], **memory})
    return process


def start_api(state_dir: Path, memory: Mapping[str, str], *, popen: Callable[..., subprocess.Popen] = subprocess.Popen) -> int:
    """Start uvicorn with this interpreter; returns its pid. Reuses a running API."""

    running = api_pid(state_dir)
    if running:
        return running
    values = read_env(state_dir / ".env")
    log = open(state_dir / "logs" / "api.log", "a")
    process = popen(
        [sys.executable, "-m", "uvicorn", "provena.api:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
        env=api_environment(values, memory),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        cwd=state_dir,
        start_new_session=True,
    )
    (state_dir / "api.pid").write_text(f"{process.pid}\n")
    update_env(state_dir / ".env", {f"PROVENA_API_{key}": value for key, value in memory.items()})
    return process.pid


def stop_api(state_dir: Path, *, timeout: float = 10) -> bool:
    pid = api_pid(state_dir)
    if not pid:
        (state_dir / "api.pid").unlink(missing_ok=True)
        return False
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and _pid_alive(pid):
        time.sleep(0.1)
    if _pid_alive(pid):
        os.kill(pid, signal.SIGKILL)
    (state_dir / "api.pid").unlink(missing_ok=True)
    return True


def remembered_memory_settings(state_dir: Path) -> dict[str, str]:
    values = read_env(state_dir / ".env")
    prefix = "PROVENA_API_"
    return {key[len(prefix):]: value for key, value in values.items() if key.startswith(prefix) and key[len(prefix):] in ("MEMORY_PROVIDER", "OLLAMA_BASE_URL", "EXTRACTION_MODEL", "EMBEDDING_MODEL")}


# --- whole service -------------------------------------------------------------------


def resolve_bindir(state_dir: Path, environ: Mapping[str, str] | None = None, *, run: Runner = subprocess.run) -> tuple[Path, int]:
    """Prefer the installation recorded for this state, so restarts use the same server."""

    values = read_env(state_dir / ".env") if (state_dir / ".env").is_file() else {}
    merged = dict(os.environ if environ is None else environ)
    if values.get("PROVENA_PG_BINDIR") and not merged.get("PROVENA_PG_BINDIR"):
        merged["PROVENA_PG_BINDIR"] = values["PROVENA_PG_BINDIR"]
    return find_postgres(merged, run=run)


def start_service(state_dir: Path, memory: Mapping[str, str] | None = None, *, environ: Mapping[str, str] | None = None) -> dict[str, object]:
    """Start (or reuse) PostgreSQL and the API; apply migrations first."""

    require_server_dependencies()
    if not is_system_mode(state_dir):
        raise LocalServerError(f"No Docker-free Provena in {state_dir}; run `provena quickstart <host> --no-docker` first")
    bindir, major = resolve_bindir(state_dir, environ)
    created = init_cluster(state_dir, bindir, major)
    update_env(state_dir / ".env", {"PROVENA_PG_BINDIR": str(bindir)})
    port = start_postgres(state_dir, bindir)
    values = read_env(state_dir / ".env")
    ensure_database(values)
    migrate(values)
    settings = dict(memory) if memory is not None else remembered_memory_settings(state_dir) or {"MEMORY_PROVIDER": "none"}
    pid = start_api(state_dir, settings)
    return {"postgres_bindir": str(bindir), "postgres_major": major, "postgres_port": port, "cluster_created": created, "api_pid": pid, "memory": settings}


def stop_service(state_dir: Path, *, environ: Mapping[str, str] | None = None) -> dict[str, bool]:
    api = stop_api(state_dir)
    try:
        bindir, _ = resolve_bindir(state_dir, environ)
        database = stop_postgres(state_dir, bindir)
    except LocalServerError:
        database = False
    return {"api_stopped": api, "postgres_stopped": database}


def service_status(state_dir: Path, *, environ: Mapping[str, str] | None = None) -> dict[str, object]:
    values = read_env(state_dir / ".env")
    try:
        bindir, major = resolve_bindir(state_dir, environ)
        database = postgres_running(state_dir, bindir)
    except LocalServerError as error:
        return {"mode": "system", "postgres": "unavailable", "detail": str(error), "api_pid": api_pid(state_dir)}
    return {
        "mode": "system",
        "postgres": "running" if database else "stopped",
        "postgres_major": major,
        "postgres_port": values.get("PROVENA_PG_PORT"),
        "api_pid": api_pid(state_dir),
        "logs": str(state_dir / "logs"),
        "hint": None if database and api_pid(state_dir) else "run `provena start` to start the Docker-free Provena service",
    }


def wait_for_api(url: str = f"http://127.0.0.1:{API_PORT}", timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    last = "no answer"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/ready", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError) as error:
            last = str(error)
        time.sleep(0.5)
    raise LocalServerError(f"The Provena API did not become ready within {int(timeout)} seconds ({last}); see the api.log in the state directory")


def main() -> None:  # pragma: no cover - manual helper used by CI
    """`python -m provena.local_server STATE_DIR`: start the cluster only and print DATABASE_URL."""
    state_dir = Path(sys.argv[1]).resolve()
    prepare_state(state_dir)
    bindir, major = find_postgres()
    init_cluster(state_dir, bindir, major)
    update_env(state_dir / ".env", {"PROVENA_PG_BINDIR": str(bindir)})
    start_postgres(state_dir, bindir)
    values = read_env(state_dir / ".env")
    ensure_database(values)
    print(json.dumps({"database_url": database_url(values), "postgres_major": major, "bindir": str(bindir)}))


if __name__ == "__main__":  # pragma: no cover
    main()
