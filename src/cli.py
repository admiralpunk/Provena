"""Operator CLI for bootstrapping and connecting Provena installations."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import shlex
import sys
import sysconfig
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence
from uuid import UUID

from .integrations.connection_config import default_config_home, load_connection_environment
from .integrations.host_setup import install_host
from .quickstart import default_state_dir, prepare_release, require_local_tools, start_automatic_memory_and_console, start_core, update_env, wait_until_ready


DEFAULT_API_URL = "http://127.0.0.1:8000"


def package_version() -> str:
    # scripts/check_release.py keeps this synchronized with package metadata,
    # images, deployment files, and release tags. A constant also prevents a
    # stale source-tree egg-info directory from selecting an older deployment.
    return "0.1.10"


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {"Accept": "application/json", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"Provena returned HTTP {error.code} for {path}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach Provena at {base_url}: {error.reason}") from error


def bootstrap_workspace(
    api_url: str,
    bootstrap_token: str,
    organization_name: str,
    project_name: str,
) -> dict[str, str]:
    bootstrap_headers = {"X-Bootstrap-Token": bootstrap_token}
    organization = request_json(
        api_url,
        "/organizations",
        method="POST",
        body={"name": organization_name},
        headers=bootstrap_headers,
    )
    project = request_json(
        api_url,
        "/projects",
        method="POST",
        body={"name": project_name},
        headers={"X-API-Key": organization["api_key"]},
    )
    reviewer = request_json(
        api_url,
        f"/organizations/{organization['id']}/credentials",
        method="POST",
        body={"role": "human", "label": "local reviewer"},
        headers=bootstrap_headers,
    )
    return {
        "PROVENA_ORG_ID": str(organization["id"]),
        "PROVENA_PROJECT_ID": str(project["id"]),
        "PROVENA_SCOPE_ID": str(project["scope_id"]),
        "PROVENA_AGENT_KEY": str(organization["api_key"]),
        "PROVENA_HUMAN_KEY": str(reviewer["api_key"]),
    }


def render_values(values: dict[str, str], output_format: str) -> str:
    if output_format == "shell":
        return "\n".join(f"export {key}={shlex.quote(value)}" for key, value in values.items())
    return json.dumps(values, indent=2)


def installed_command(name: str) -> str:
    scripts = Path(sysconfig.get_path("scripts"))
    for filename in (name, f"{name}.exe"):
        candidate = scripts / filename
        if candidate.is_file():
            return str(candidate.resolve())
    executable = shutil.which(name)
    if executable:
        return str(Path(executable).resolve())
    raise RuntimeError(f"{name} was not found; reinstall provena-agent-memory in the active environment")


def installed_mcp_command() -> str:
    return installed_command("provena-mcp")


def build_client_config(
    client: str,
    api_url: str,
    api_key: str,
    scope_id: str,
    connector_command: str = "provena-mcp",
) -> str:
    UUID(scope_id)
    environment = {
        "PROVENA_API_URL": api_url.rstrip("/"),
        "PROVENA_API_KEY": api_key,
        "PROVENA_SCOPE_ID": scope_id,
    }
    if client == "codex":
        lines = [
            "[mcp_servers.provena]",
            f"command = {json.dumps(connector_command)}",
            "",
            "[mcp_servers.provena.env]",
        ]
        lines.extend(f"{key} = {json.dumps(value)}" for key, value in environment.items())
        return "\n".join(lines)
    return json.dumps(
        {
            "mcpServers": {
                "provena": {
                    "command": connector_command,
                    "env": environment,
                }
            }
        },
        indent=2,
    )


def _required(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _init_command(args: argparse.Namespace) -> int:
    values = bootstrap_workspace(
        args.api_url,
        _required(args.bootstrap_token, "BOOTSTRAP_TOKEN"),
        args.organization,
        args.project,
    )
    print(render_values(values, args.format))
    if args.format == "json":
        print("Credentials are shown once. Store them in a secret manager.", file=sys.stderr)
    return 0


def _status_command(args: argparse.Namespace) -> int:
    liveness = request_json(args.api_url, "/health")
    readiness = request_json(args.api_url, "/ready")
    print(json.dumps({"api_url": args.api_url, "liveness": liveness, "readiness": readiness}, indent=2))
    return 0


def _doctor_command(args: argparse.Namespace) -> int:
    api_key = _required(args.api_key, "PROVENA_API_KEY")
    scope_id = _required(args.scope_id, "PROVENA_SCOPE_ID")
    UUID(scope_id)
    checks: list[dict[str, str]] = []
    for name, path, headers in (
        ("liveness", "/health", {}),
        ("database", "/ready", {}),
        ("credential_and_scope", f"/claims?scope_id={scope_id}&limit=1", {"X-API-Key": api_key}),
    ):
        request_json(args.api_url, path, headers=headers)
        checks.append({"name": name, "status": "ok"})
    print(json.dumps({"status": "ok", "checks": checks}, indent=2))
    return 0


def _connect_command(args: argparse.Namespace) -> int:
    api_key = _required(args.api_key, "PROVENA_API_KEY")
    scope_id = _required(args.scope_id, "PROVENA_SCOPE_ID")
    if args.install:
        if args.client == "generic":
            raise RuntimeError("--install requires a supported host: codex, claude, or gemini")
        _doctor_command(args)
        installed = install_host(
            args.client,
            args.api_url,
            api_key,
            scope_id,
            mcp_command=installed_mcp_command(),
            context_command=installed_command("provena-agent-context"),
            capture_command=installed_command("provena-agent-capture"),
        )
        print(json.dumps({"status": "installed", "client": args.client, "automatic_memory": True, **installed}, indent=2))
        print(_host_restart_instruction(args.client), file=sys.stderr)
        return 0
    print(
        build_client_config(
            args.client,
            args.api_url,
            api_key,
            scope_id,
            installed_mcp_command(),
        )
    )
    return 0


def _host_restart_instruction(client: str) -> str:
    instructions = {
        "codex": "Restart Codex, open /hooks, trust the Provena hooks, and then use Codex normally.",
        "claude": "Restart Claude Code, review Provena in /hooks and /mcp, and then use Claude normally.",
        "gemini": "Restart Gemini CLI, review Provena in /hooks and /mcp, and then use Gemini normally.",
    }
    return instructions[client]


def _existing_quickstart_connection(api_url: str, client: str) -> dict[str, str] | None:
    candidates = (client, *(host for host in ("codex", "claude", "gemini") if host != client))
    for host in candidates:
        path = default_config_home() / "provena" / f"{host}.json"
        if not path.exists():
            continue
        try:
            environment = load_connection_environment({}, path)
            context = request_json(
                api_url,
                f"/operator/context?scope_id={environment['PROVENA_SCOPE_ID']}",
                headers={"X-API-Key": environment["PROVENA_API_KEY"]},
            )
            return {**environment, "PROVENA_ORG_ID": str(context["organization"]["id"])}
        except (KeyError, RuntimeError):
            continue
    return None


def _ensure_console_reviewer(
    api_url: str,
    state_dir: Path,
    deployment: dict[str, str],
    agent_connection: dict[str, str],
) -> None:
    scope_id = agent_connection["PROVENA_SCOPE_ID"]
    current_key = deployment.get("PROVENA_API_KEY")
    current_scope = deployment.get("PROVENA_SCOPE_ID")
    if current_key and current_scope == scope_id:
        try:
            context = request_json(
                api_url,
                f"/operator/context?scope_id={scope_id}",
                headers={"X-API-Key": current_key},
            )
            if context["principal"]["role"] == "human":
                return
        except (KeyError, RuntimeError):
            pass

    reviewer = request_json(
        api_url,
        f"/organizations/{agent_connection['PROVENA_ORG_ID']}/credentials",
        method="POST",
        body={"role": "human", "label": "local reviewer"},
        headers={"X-Bootstrap-Token": deployment["BOOTSTRAP_TOKEN"]},
    )
    update_env(
        state_dir / ".env",
        {"PROVENA_API_KEY": str(reviewer["api_key"]), "PROVENA_SCOPE_ID": scope_id},
    )


def _quickstart_command(args: argparse.Namespace) -> int:
    require_local_tools(args.client)
    state_dir = Path(args.state_dir).expanduser().resolve()
    current_version = package_version()
    print(f"Preparing Provena {current_version} in {state_dir}...")
    deployment = prepare_release(current_version, state_dir)
    print("Starting PostgreSQL and the Provena API...")
    start_core(state_dir, deployment)

    api_url = "http://127.0.0.1:8000"
    existing = _existing_quickstart_connection(api_url, args.client)
    if existing:
        agent_key = existing["PROVENA_API_KEY"]
        scope_id = existing["PROVENA_SCOPE_ID"]
        _ensure_console_reviewer(api_url, state_dir, deployment, existing)
        print("Reusing the existing Provena agent credential and scope.")
    else:
        workspace = bootstrap_workspace(
            api_url,
            deployment["BOOTSTRAP_TOKEN"],
            args.organization,
            args.project,
        )
        agent_key = workspace["PROVENA_AGENT_KEY"]
        scope_id = workspace["PROVENA_SCOPE_ID"]
        update_env(
            state_dir / ".env",
            {
                "PROVENA_API_KEY": workspace["PROVENA_HUMAN_KEY"],
                "PROVENA_SCOPE_ID": scope_id,
            },
        )
        print("Created a local organization, project scope, and separate agent and reviewer credentials.")

    installed = install_host(
        args.client,
        api_url,
        agent_key,
        scope_id,
        mcp_command=installed_mcp_command(),
        context_command=installed_command("provena-agent-context"),
        capture_command=installed_command("provena-agent-capture"),
    )
    print(f"Configured {args.client.title()} MCP plus automatic memory capture and retrieval.")
    print("Starting local Ollama models and the Provena console; the first model download can take several minutes...")
    start_automatic_memory_and_console(state_dir)
    wait_until_ready(api_url)
    print(
        json.dumps(
            {
                "status": "ready",
                "api_url": api_url,
                "console_url": f"http://127.0.0.1:3000/overview?scope={scope_id}",
                "scope_id": scope_id,
                "state_dir": str(state_dir),
                **installed,
            },
            indent=2,
        )
    )
    print(_host_restart_instruction(args.client), file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="provena", description="Operate and connect a Provena memory service.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Create an organization, project, and initial credentials.")
    init.add_argument("--api-url", default=os.getenv("PROVENA_API_URL", DEFAULT_API_URL))
    init.add_argument("--bootstrap-token", default=os.getenv("BOOTSTRAP_TOKEN"))
    init.add_argument("--organization", default="Local development")
    init.add_argument("--project", default="provena-demo")
    init.add_argument("--format", choices=("json", "shell"), default="json")
    init.set_defaults(handler=_init_command)

    status = commands.add_parser("status", help="Check API and database health.")
    status.add_argument("--api-url", default=os.getenv("PROVENA_API_URL", DEFAULT_API_URL))
    status.set_defaults(handler=_status_command)

    doctor = commands.add_parser("doctor", help="Check API, database, credential, and scope access.")
    doctor.add_argument("--api-url", default=os.getenv("PROVENA_API_URL", DEFAULT_API_URL))
    doctor.add_argument("--api-key", default=os.getenv("PROVENA_API_KEY"))
    doctor.add_argument("--scope-id", default=os.getenv("PROVENA_SCOPE_ID"))
    doctor.set_defaults(handler=_doctor_command)

    connect = commands.add_parser("connect", help="Configure a supported agent host or print MCP configuration.")
    connect.add_argument("client", choices=("codex", "claude", "gemini", "generic"))
    connect.add_argument("--api-url", default=os.getenv("PROVENA_API_URL", DEFAULT_API_URL))
    connect.add_argument("--api-key", default=os.getenv("PROVENA_API_KEY"))
    connect.add_argument("--scope-id", default=os.getenv("PROVENA_SCOPE_ID"))
    connect.add_argument("--install", action="store_true", help="Install MCP plus automatic capture and retrieval hooks.")
    connect.set_defaults(handler=_connect_command)

    quickstart = commands.add_parser("quickstart", help="Start local Provena and configure automatic agent memory.")
    quickstart.add_argument("client", nargs="?", choices=("codex", "claude", "gemini"), default="codex")
    quickstart.add_argument("--state-dir", default=str(default_state_dir()))
    quickstart.add_argument("--organization", default="Local development")
    quickstart.add_argument("--project", default="provena-demo")
    quickstart.set_defaults(handler=_quickstart_command)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        raise SystemExit(args.handler(args))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


def bootstrap_main() -> None:
    """Compatibility entry point for ``scripts/bootstrap_workspace.py``."""
    main(["init", *sys.argv[1:]])


if __name__ == "__main__":
    main()
