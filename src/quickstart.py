"""Self-hosted quickstart orchestration for the published connector package."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping


Runner = Callable[..., subprocess.CompletedProcess[str]]
RELEASE_FILES = ("compose.yaml", "compose.ollama.yaml", "compose.host-ollama.yaml")


def default_state_dir(environ: Mapping[str, str] | None = None) -> Path:
    values = environ or os.environ
    legacy = Path.home() / "provena-server"
    if (legacy / ".env").exists() and (legacy / "compose.yaml").exists():
        return legacy
    configured = values.get("XDG_DATA_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".local" / "share"
    return base / "provena"


def _download(url: str, destination: Path) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as output, urllib.request.urlopen(url, timeout=30) as response:
            shutil.copyfileobj(response, output)
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def update_env(path: Path, updates: Mapping[str, str]) -> None:
    remaining = dict(updates)
    lines: list[str] = []
    for line in path.read_text().splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in remaining:
                line = f"{key}={remaining.pop(key)}"
        lines.append(line)
    if remaining:
        if lines and lines[-1]:
            lines.append("")
        lines.extend(f"{key}={value}" for key, value in remaining.items())
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)


def prepare_release(version: str, state_dir: Path) -> dict[str, str]:
    state_dir.mkdir(parents=True, exist_ok=True)
    base_url = f"https://raw.githubusercontent.com/admiralpunk/Provena/v{version}/deploy"
    try:
        for name in RELEASE_FILES:
            _download(f"{base_url}/{name}", state_dir / name)
        env_path = state_dir / ".env"
        if not env_path.exists():
            _download(f"{base_url}/.env.example", env_path)
    except (OSError, urllib.error.URLError) as error:
        raise RuntimeError(f"Could not download Provena {version} deployment files: {error}") from error

    values = read_env(env_path)
    updates = {"PROVENA_VERSION": version}
    if not values.get("POSTGRES_PASSWORD") or values["POSTGRES_PASSWORD"].startswith("replace-with-"):
        updates["POSTGRES_PASSWORD"] = secrets.token_urlsafe(32)
    if not values.get("BOOTSTRAP_TOKEN") or values["BOOTSTRAP_TOKEN"].startswith("replace-with-"):
        updates["BOOTSTRAP_TOKEN"] = secrets.token_urlsafe(32)
    update_env(env_path, updates)
    return read_env(env_path)


def compose_command(state_dir: Path, *, ollama: bool = False, host_ollama: bool = False) -> list[str]:
    command = ["docker", "compose", "--project-directory", str(state_dir), "-f", str(state_dir / "compose.yaml")]
    if ollama:
        command.extend(("-f", str(state_dir / "compose.ollama.yaml")))
    if host_ollama:
        command.extend(("-f", str(state_dir / "compose.host-ollama.yaml")))
    return command


def compose_environment(state_dir: Path, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a Compose environment where the managed state file wins.

    Docker Compose gives exported shell variables precedence over ``.env``.
    Quickstart owns the deployment in ``state_dir``, so stale variables from a
    previous manual setup must not silently select another image, credential,
    or scope.
    """
    values = dict(environ or os.environ)
    values.update(read_env(state_dir / ".env"))
    return values


def require_local_tools(client: str) -> None:
    missing = [name for name in ("docker", client) if not shutil.which(name)]
    if missing:
        raise RuntimeError(f"Required command not found: {', '.join(missing)}")
    result = subprocess.run(["docker", "compose", "version"], text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("Docker Compose is required; `docker compose version` failed")


def wait_until_ready(api_url: str, timeout: int = 90) -> None:
    deadline = time.monotonic() + timeout
    last_error = "service did not answer"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{api_url.rstrip('/')}/ready", timeout=3) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError) as error:
            last_error = str(error)
        time.sleep(1)
    raise RuntimeError(f"Provena API did not become ready within {timeout} seconds: {last_error}")


def start_core(
    state_dir: Path,
    environment: Mapping[str, str],
    *,
    runner: Runner = subprocess.run,
) -> None:
    command = compose_command(state_dir)
    process_environment = compose_environment(state_dir)
    runner([*command, "up", "-d", "postgres", "api"], cwd=state_dir, env=process_environment, check=True)
    try:
        wait_until_ready("http://127.0.0.1:8000")
        return
    except RuntimeError as initial_error:
        logs = runner(
            [*command, "logs", "--no-color", "--tail=80", "api"],
            cwd=state_dir,
            env=process_environment,
            text=True,
            capture_output=True,
            check=False,
        )
        if "password authentication failed for user" not in (logs.stdout + logs.stderr):
            raise initial_error

    password = environment["POSTGRES_PASSWORD"]
    sql = "\\getenv role_password NEW_PASSWORD\nALTER ROLE provena WITH PASSWORD :'role_password';\n"
    runner(
        [*command, "exec", "-T", "-e", f"NEW_PASSWORD={password}", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", "provena", "-d", "provena"],
        cwd=state_dir,
        env=process_environment,
        input=sql,
        text=True,
        check=True,
    )
    runner([*command, "restart", "api"], cwd=state_dir, env=process_environment, check=True)
    wait_until_ready("http://127.0.0.1:8000")


def start_automatic_memory_and_console(
    state_dir: Path,
    *,
    runner: Runner = subprocess.run,
) -> None:
    command = compose_command(state_dir, ollama=True)
    runner(
        [*command, "--profile", "console", "up", "-d"],
        cwd=state_dir,
        env=compose_environment(state_dir),
        check=True,
    )


# --- ADR 0025: how local models are provided -------------------------------------------

HOST_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODELS = ("qwen2.5:1.5b", "nomic-embed-text")
MODEL_MODES = ("background", "wait", "none", "host")


def host_ollama_models(url: str = HOST_OLLAMA_URL, timeout: float = 2) -> set[str] | None:
    """Return model names served by an Ollama already running on this machine, or None."""
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=timeout) as response:
            document = json.load(response)
    except (OSError, urllib.error.URLError, ValueError):
        return None
    models = document.get("models", []) if isinstance(document, dict) else []
    return {str(model.get("name")) for model in models if isinstance(model, dict) and model.get("name")}


def missing_models(available: set[str], wanted: tuple[str, ...] = DEFAULT_MODELS) -> list[str]:
    return [name for name in wanted if name not in available and f"{name}:latest" not in available]


def pull_host_models_in_background(state_dir: Path, models: list[str], *, popen: Callable[..., Any] = subprocess.Popen) -> bool:
    """Start detached `ollama pull` processes; their output goes to state_dir/ollama-pull.log."""
    if not models or not shutil.which("ollama"):
        return False
    log = open(state_dir / "ollama-pull.log", "a")
    for model in models:
        popen(["ollama", "pull", model], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    return True


def choose_model_mode(*, no_local_models: bool, wait_for_models: bool, allow_host_ollama: bool, host_models: set[str] | None) -> str:
    if no_local_models:
        return "none"
    if wait_for_models:
        return "wait"
    if allow_host_ollama and host_models is not None:
        return "host"
    return "background"


def api_reaches_ollama(state_dir: Path, *, runner: Runner = subprocess.run) -> bool:
    """Check from inside the API container that its configured Ollama answers."""
    probe = "import os, urllib.request; urllib.request.urlopen(os.environ['OLLAMA_BASE_URL'].rstrip('/') + '/api/version', timeout=3)"
    result = runner(
        [*compose_command(state_dir, host_ollama=True), "exec", "-T", "api", "python", "-c", probe],
        cwd=state_dir,
        env=compose_environment(state_dir),
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def start_memory_and_console(state_dir: Path, mode: str, *, runner: Runner = subprocess.run) -> None:
    """Start the console and provide models according to MODE without waiting for downloads.

    - none: the API keeps MEMORY_PROVIDER=none; recall uses full-text search.
    - background: start the Ollama container and its model download, then switch the
      API to Ollama immediately; extraction and semantic recall work once models arrive.
    - host: point the API at an Ollama server already running on this machine.
    - wait: the previous behaviour, which blocks until both models are downloaded.
    """
    environment = compose_environment(state_dir)
    if mode == "wait":
        start_automatic_memory_and_console(state_dir, runner=runner)
        return
    if mode == "none":
        runner([*compose_command(state_dir), "--profile", "console", "up", "-d"], cwd=state_dir, env=environment, check=True)
        return
    if mode == "background":
        command = compose_command(state_dir, ollama=True)
        runner([*command, "up", "-d", "ollama-models"], cwd=state_dir, env=environment, check=True)
        runner([*command, "--profile", "console", "up", "-d", "--no-deps", "api", "console"], cwd=state_dir, env=environment, check=True)
        return
    if mode == "host":
        command = compose_command(state_dir, host_ollama=True)
        runner([*command, "--profile", "console", "up", "-d", "--no-deps", "api", "console"], cwd=state_dir, env=environment, check=True)
        return
    raise ValueError(f"unknown model mode: {mode}")
