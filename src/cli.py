"""Operator CLI for bootstrapping and connecting Provena installations."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import urllib.error
import urllib.request
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Sequence
from uuid import UUID


DEFAULT_API_URL = "http://127.0.0.1:8000"
PACKAGE_NAME = "provena-agent-memory"


def package_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.1.1"


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


def build_client_config(client: str, api_url: str, api_key: str, scope_id: str) -> str:
    UUID(scope_id)
    environment = {
        "PROVENA_API_URL": api_url.rstrip("/"),
        "PROVENA_API_KEY": api_key,
        "PROVENA_SCOPE_ID": scope_id,
    }
    if client == "codex":
        lines = [
            "[mcp_servers.provena]",
            'command = "uvx"',
            f'args = ["--from", "{PACKAGE_NAME}", "provena-mcp"]',
            "",
            "[mcp_servers.provena.env]",
        ]
        lines.extend(f"{key} = {json.dumps(value)}" for key, value in environment.items())
        return "\n".join(lines)
    return json.dumps(
        {
            "mcpServers": {
                "provena": {
                    "command": "uvx",
                    "args": ["--from", PACKAGE_NAME, "provena-mcp"],
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
    print(
        build_client_config(
            args.client,
            args.api_url,
            _required(args.api_key, "PROVENA_API_KEY"),
            _required(args.scope_id, "PROVENA_SCOPE_ID"),
        )
    )
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

    connect = commands.add_parser("connect", help="Print an MCP configuration for an agent client.")
    connect.add_argument("client", choices=("codex", "claude", "gemini", "generic"))
    connect.add_argument("--api-url", default=os.getenv("PROVENA_API_URL", DEFAULT_API_URL))
    connect.add_argument("--api-key", default=os.getenv("PROVENA_API_KEY"))
    connect.add_argument("--scope-id", default=os.getenv("PROVENA_SCOPE_ID"))
    connect.set_defaults(handler=_connect_command)
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
