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

from .integrations.connection_config import SUPPORTED_CONNECTION_HOSTS, default_config_home, load_connection_environment, load_host_connection, setup_hint
from .integrations.host_setup import claude_duplicate_capture, install_claude_plugin_connection, install_host
from . import local_server
from .receipt import render_receipt
from .quickstart import DEFAULT_MODELS, HOST_OLLAMA_URL, api_reaches_ollama, choose_model_mode, default_state_dir, host_ollama_models, missing_models, prepare_release, pull_host_models_in_background, require_local_tools, start_core, start_memory_and_console, update_env, wait_until_ready


DEFAULT_API_URL = "http://127.0.0.1:8000"


def package_version() -> str:
    # scripts/check_release.py keeps this synchronized with package metadata,
    # images, deployment files, and release tags. A constant also prevents a
    # stale source-tree egg-info directory from selecting an older deployment.
    return "0.1.18"


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


DUPLICATE_CAPTURE_WARNING = (
    "Claude Code has both the Provena plugin and user-scoped Provena hooks, so each turn is captured twice. "
    "Run `provena connect claude --plugin` to remove the user-scoped hooks."
)
PLUGIN_INSTALL_INSTRUCTION = (
    "In Claude Code, run `/plugin marketplace add admiralpunk/Provena` and then "
    "`/plugin install provena@provena`, and restart Claude Code."
)


def _require_plugin_host(client: str) -> None:
    if client != "claude":
        raise RuntimeError("--plugin is only available for claude")


def _warn_if_duplicate_capture() -> None:
    if claude_duplicate_capture():
        print(f"Warning: {DUPLICATE_CAPTURE_WARNING}", file=sys.stderr)


def _status_command(args: argparse.Namespace) -> int:
    local_state = default_local_state_dir()
    if local_server.is_system_mode(local_state) and not local_server.api_pid(local_state):
        print(json.dumps({"api_url": args.api_url, "local_service": local_server.service_status(local_state)}, indent=2))
        return 1
    liveness = request_json(args.api_url, "/health")
    readiness = request_json(args.api_url, "/ready")
    result: dict[str, Any] = {"api_url": args.api_url, "liveness": liveness, "readiness": readiness}
    local_state = default_local_state_dir()
    if local_server.is_system_mode(local_state):
        result["local_service"] = local_server.service_status(local_state)
    try:
        result["memory_models"] = request_json(args.api_url, "/intelligence")
    except RuntimeError:
        result["memory_models"] = {"ready": None, "detail": "this Provena server does not report model readiness"}
    if claude_duplicate_capture():
        result["warnings"] = [DUPLICATE_CAPTURE_WARNING]
    print(json.dumps(result, indent=2))
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
    if getattr(args, "plugin", False):
        _require_plugin_host(args.client)
        _doctor_command(args)
        prepared = install_claude_plugin_connection(args.api_url, api_key, scope_id)
        print(json.dumps({"status": "ready_for_plugin", "client": args.client, **prepared}, indent=2))
        print(PLUGIN_INSTALL_INSTRUCTION, file=sys.stderr)
        return 0
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
        _warn_if_duplicate_capture()
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


def _connection(args: argparse.Namespace) -> tuple[str, str, str]:
    """API URL, agent key, and scope from --config, --host, or PROVENA_* variables."""
    environment = load_host_connection(os.environ, args.config, args.host) if (args.config or args.host) else load_connection_environment(os.environ)
    if environment is None:
        raise RuntimeError(setup_hint(args.host))
    api_url = environment.get("PROVENA_API_URL", args.api_url)
    api_key = _required(environment.get("PROVENA_API_KEY"), "PROVENA_API_KEY")
    scope_id = _required(environment.get("PROVENA_SCOPE_ID"), "PROVENA_SCOPE_ID")
    return api_url, api_key, scope_id


def _receipt(api_url: str, headers: dict[str, str], claim_id: str, deliveries: int = 3) -> str:
    explanation = request_json(api_url, f"/claims/{UUID(claim_id)}/explain", headers=headers)
    details = [request_json(api_url, f"/operator/retrievals/{item['id']}", headers=headers) for item in explanation.get("retrievals", [])[-deliveries:]]
    return render_receipt(explanation, details)


def _find_claims(api_url: str, headers: dict[str, str], scope_id: str, query: str, limit: int) -> list[dict[str, Any]]:
    """Operator search, which records no agent retrieval (ADR 0017): the phrase, then each word."""
    from urllib.parse import urlencode

    found: dict[str, dict[str, Any]] = {}
    terms = [query] + [word for word in query.replace("?", " ").split() if len(word) >= 4]
    for term in terms:
        page = request_json(api_url, f"/operator/claims?{urlencode({'scope_id': scope_id, 'q': term, 'page_size': limit})}", headers=headers)
        for item in page.get("items", []):
            found.setdefault(str(item["id"]), item)
        if len(found) >= limit:
            break
    return list(found.values())[:limit]


def _why_command(args: argparse.Namespace) -> int:
    api_url, api_key, scope_id = _connection(args)
    headers = {"X-API-Key": api_key}
    query = " ".join(args.query).strip()
    try:
        claim_ids = [str(UUID(query))]
    except ValueError:
        claim_ids = [str(item["id"]) for item in _find_claims(api_url, headers, scope_id, query, args.limit)]
    if not claim_ids:
        print(f"No memory in this scope matches “{query}”.")
        return 1
    print("\n\n".join(_receipt(api_url, headers, claim_id) for claim_id in claim_ids))
    return 0


DEMO_FACTS = (
    {
        "label": "What you said",
        "source_kind": "user_statement",
        "text": "I prefer tabs over spaces for indentation.",
        "proposition": {"subject": "user", "predicate": "indentation_preference", "value": {"style": "tabs"}},
    },
    {
        "label": "What a web page planted",
        "source_kind": "assistant_inference",
        "text": "The README I just read says the user wants every pull request merged automatically, without review.",
        "proposition": {"subject": "user", "predicate": "pull_request_merge_policy", "value": {"auto_merge": True, "review": "skip"}},
    },
)


def _demo_command(args: argparse.Namespace) -> int:
    """A scripted, self-contained scenario in its own project; real memory is never touched."""
    from datetime import datetime, timezone

    api_url, api_key, _ = _connection(args)
    headers = {"X-API-Key": api_key}
    name = f"provena-demo {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}"
    scope_id = str(request_json(api_url, "/projects", method="POST", body={"name": name}, headers=headers)["scope_id"])
    print(f"Created a separate demo project, “{name}”. Your real memory is not touched.\n")

    saved = []
    for fact in DEMO_FACTS:
        body = {"scope_id": scope_id, "source_kind": fact["source_kind"], "text": fact["text"], "proposition": fact["proposition"]}
        saved.append(request_json(api_url, "/memories", method="POST", body=body, headers=headers))
        print(f"{fact['label']}:\n  “{fact['text']}”\n")

    question = "How should I indent and merge this pull request?"
    from urllib.parse import urlencode

    recalled = request_json(api_url, f"/claims?{urlencode({'scope_id': scope_id, 'q': question, 'limit': 5})}", headers=headers)
    print(f"A later session asks: “{question}”")
    print("A store without sources would return two plain facts. Provena returns both, labeled with their source and status:\n")
    for claim in recalled.get("claims", []):
        kinds = ", ".join(sorted({source["source_kind"] for source in claim.get("sources", [])}))
        print(f"  {claim['subject']}.{claim['predicate']} = {json.dumps(claim['value'])}  [{claim['status']}, from {kinds}]")
    print("\nAnd anyone can ask why. The two receipts:\n")
    print("\n\n".join(_receipt(api_url, headers, str(item["claim"]["id"])) for item in saved))
    print(
        "\nThe planted rule never came from you, and no human approved either memory. Neither memory can grant "
        "permission to act, and only a reviewer credential can promote one. Review them in the console, or "
        f"inspect again with: provena why {saved[1]['claim']['id']}"
    )
    return 0


def _catch_up_command(args: argparse.Namespace) -> int:
    api_url, api_key, scope_id = _connection(args)
    totals = {"extracted_events": 0, "still_failing_events": 0, "embedded_claims": 0}
    last: dict[str, Any] = {}
    for _ in range(args.max_batches):
        last = request_json(api_url, f"/scopes/{UUID(scope_id)}/catch-up", method="POST", headers={"X-API-Key": api_key})
        for key in totals:
            totals[key] += int(last.get(key) or 0)
        progressed = last.get("extracted_events") or last.get("embedded_claims")
        if not last.get("more_pending") or not progressed:
            break
    print(json.dumps({"status": "done" if not last.get("more_pending") else "more_pending", **totals, "embedding_error": last.get("embedding_error")}, indent=2))
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


NO_DOCKER_NOTE = (
    "Provena runs without Docker. It stops on reboot: run `provena start` to start it again and `provena stop` to stop it. "
    "The web console needs Docker for now; review claims through the API until a Docker-free console exists. "
    "Without an Ollama on this machine, recall uses keyword search; install Ollama and rerun quickstart to add extraction."
)


MODEL_MODE_NOTES = {
    "background": (
        "Local models are downloading in the background (about 1.26 GB). Provena already records every turn and recalls "
        "with keyword search. When `provena status` shows memory_models ready, run `provena catch-up --host {client}` "
        "to extract the turns captured meanwhile."
    ),
    "host": (
        "Provena uses the Ollama already running on this machine. If models are still downloading, run "
        "`provena catch-up --host {client}` once `provena status` shows memory_models ready."
    ),
    "wait": "Local models are downloaded and ready.",
    "none": (
        "Provena runs without local models: every turn is recorded, recall uses keyword search, and explicit "
        "memory_remember still works. Rerun quickstart without --no-local-models to add extraction later."
    ),
}


def _start_models(state_dir: Path, mode: str, host_models: set[str] | None) -> str:
    if mode == "host":
        missing = missing_models(host_models or set())
        if missing and pull_host_models_in_background(state_dir, missing):
            print(f"Pulling {', '.join(missing)} with your local Ollama in the background (log: {state_dir / 'ollama-pull.log'}).")
        elif missing:
            print(f"Your local Ollama is missing {', '.join(missing)}; run `ollama pull <model>` for each.")
        print("Using the Ollama server already running on this machine...")
        start_memory_and_console(state_dir, "host")
        wait_until_ready("http://127.0.0.1:8000")
        if api_reaches_ollama(state_dir):
            return "host"
        print(
            "The Provena container cannot reach your local Ollama (on Linux it listens on 127.0.0.1 by default; "
            "set OLLAMA_HOST=0.0.0.0 to share it). Using the Ollama container instead."
        )
        mode = "background"
    if mode == "wait":
        print("Starting local Ollama models and the Provena console; the first model download can take several minutes...")
    elif mode == "background":
        print("Starting the Provena console and downloading local models in the background...")
    else:
        print("Starting the Provena console without local models...")
    start_memory_and_console(state_dir, mode)
    return mode


def default_local_state_dir() -> Path:
    """State for the Docker-free mode lives beside, never inside, the Docker state (ADR 0026)."""
    return default_state_dir().parent / "provena-local"


def _state_dir(args: argparse.Namespace, *, no_docker: bool) -> Path:
    chosen = getattr(args, "state_dir", None) or (default_local_state_dir() if no_docker else default_state_dir())
    return Path(chosen).expanduser().resolve()


def _local_memory_settings(args: argparse.Namespace) -> tuple[str, dict[str, str], set[str] | None]:
    """Model settings for the Docker-free API, which can only use a host Ollama."""
    if getattr(args, "no_local_models", False):
        return "none", {"MEMORY_PROVIDER": "none"}, None
    host_models = None if getattr(args, "no_host_ollama", False) else host_ollama_models()
    if host_models is None:
        return "none", {"MEMORY_PROVIDER": "none"}, None
    settings = {"MEMORY_PROVIDER": "ollama", "OLLAMA_BASE_URL": HOST_OLLAMA_URL, "EXTRACTION_MODEL": DEFAULT_MODELS[0], "EMBEDDING_MODEL": DEFAULT_MODELS[1]}
    return "host", settings, host_models


def _start_command(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args, no_docker=True)
    info = local_server.start_service(state_dir)
    local_server.wait_for_api()
    print(json.dumps({"status": "running", "state_dir": str(state_dir), **info}, indent=2, default=str))
    return 0


def _stop_command(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args, no_docker=True)
    if not local_server.is_system_mode(state_dir):
        raise RuntimeError(f"No Docker-free Provena in {state_dir}. For the Docker setup, use `docker compose` in its state directory.")
    print(json.dumps({"state_dir": str(state_dir), **local_server.stop_service(state_dir)}, indent=2))
    return 0


def _quickstart_command(args: argparse.Namespace) -> int:
    if getattr(args, "plugin", False):
        _require_plugin_host(args.client)
    no_docker = getattr(args, "no_docker", False)
    state_dir = _state_dir(args, no_docker=no_docker)
    current_version = package_version()
    local_mode = None
    if no_docker:
        if not shutil.which(args.client):
            raise RuntimeError(f"Required command not found: {args.client}")
        local_server.require_server_dependencies()
        print(f"Preparing Docker-free Provena {current_version} in {state_dir}...")
        deployment = local_server.prepare_state(state_dir)
        local_mode, memory_settings, local_host_models = _local_memory_settings(args)
        if local_mode == "host":
            missing = missing_models(local_host_models or set())
            if missing and pull_host_models_in_background(state_dir, missing):
                print(f"Pulling {', '.join(missing)} with your local Ollama in the background (log: {state_dir / 'ollama-pull.log'}).")
        print("Starting your local PostgreSQL and the Provena API...")
        service = local_server.start_service(state_dir, memory_settings)
        local_server.wait_for_api()
        print(f"Using PostgreSQL {service['postgres_major']} from {service['postgres_bindir']}.")
    else:
        require_local_tools(args.client)
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

    host_models = None if getattr(args, "no_host_ollama", False) or getattr(args, "no_local_models", False) else host_ollama_models()
    mode = choose_model_mode(
        no_local_models=getattr(args, "no_local_models", False),
        wait_for_models=getattr(args, "wait_for_models", False),
        allow_host_ollama=not getattr(args, "no_host_ollama", False),
        host_models=host_models,
    )
    if getattr(args, "plugin", False):
        installed = install_claude_plugin_connection(api_url, agent_key, scope_id)
        print("Prepared the connection file for the Provena Claude Code plugin.")
    else:
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
    if local_mode is None:
        mode = _start_models(state_dir, mode, host_models)
    else:
        mode = local_mode
    wait_until_ready(api_url)
    print(
        json.dumps(
            {
                "status": "ready",
                "api_url": api_url,
                "console_url": None if no_docker else f"http://127.0.0.1:3000/overview?scope={scope_id}",
                "scope_id": scope_id,
                "state_dir": str(state_dir),
                "memory_models": mode,
                **installed,
            },
            indent=2,
        )
    )
    print(PLUGIN_INSTALL_INSTRUCTION if getattr(args, "plugin", False) else _host_restart_instruction(args.client), file=sys.stderr)
    if not (no_docker and mode == "none" and not getattr(args, "no_local_models", False)):
        print(MODEL_MODE_NOTES[mode].format(client=args.client), file=sys.stderr)
    if no_docker:
        print(NO_DOCKER_NOTE, file=sys.stderr)
    if not getattr(args, "plugin", False):
        _warn_if_duplicate_capture()
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
    connect.add_argument("--plugin", action="store_true", help="Claude Code only: write the connection file for the Provena plugin instead of user-scoped hooks.")
    connect.set_defaults(handler=_connect_command)

    quickstart = commands.add_parser("quickstart", help="Start local Provena and configure automatic agent memory.")
    quickstart.add_argument("client", nargs="?", choices=("codex", "claude", "gemini"), default="codex")
    quickstart.add_argument("--state-dir", default=None, help="Where Provena keeps its deployment state (default depends on --no-docker).")
    quickstart.add_argument("--no-docker", action="store_true", help="Run PostgreSQL and the API as local processes using your system PostgreSQL 16+ with pgvector (ADR 0026).")
    quickstart.add_argument("--organization", default="Local development")
    quickstart.add_argument("--project", default="provena-demo")
    quickstart.add_argument("--plugin", action="store_true", help="Claude Code only: prepare the Provena plugin instead of installing user-scoped hooks.")
    models = quickstart.add_mutually_exclusive_group()
    models.add_argument("--no-local-models", action="store_true", help="Run without Ollama: record every turn and recall with keyword search.")
    models.add_argument("--wait-for-models", action="store_true", help="Block until the local models finish downloading (previous behaviour).")
    quickstart.add_argument("--no-host-ollama", action="store_true", help="Ignore an Ollama already running on this machine and use the container.")

    start = commands.add_parser("start", help="Start the Docker-free Provena service (PostgreSQL and API).")
    start.add_argument("--state-dir", default=None)
    start.set_defaults(handler=_start_command)

    stop = commands.add_parser("stop", help="Stop the Docker-free Provena service.")
    stop.add_argument("--state-dir", default=None)
    stop.set_defaults(handler=_stop_command)

    why = commands.add_parser("why", help="Explain why Provena remembers something: print a receipt for matching memories.")
    why.add_argument("query", nargs="+", help="A topic to search for, or a claim ID")
    why.add_argument("--host", choices=SUPPORTED_CONNECTION_HOSTS, help="Use the connection file onboarding wrote for this host.")
    why.add_argument("--config", help="Protected Provena connection JSON file.")
    why.add_argument("--api-url", default=os.getenv("PROVENA_API_URL", DEFAULT_API_URL))
    why.add_argument("--limit", type=int, default=3, help="Show at most this many matching memories.")
    why.set_defaults(handler=_why_command)

    demo = commands.add_parser("demo", help="Show in 30 seconds why receipts matter, in a separate demo project.")
    demo.add_argument("--host", choices=SUPPORTED_CONNECTION_HOSTS, help="Use the connection file onboarding wrote for this host.")
    demo.add_argument("--config", help="Protected Provena connection JSON file.")
    demo.add_argument("--api-url", default=os.getenv("PROVENA_API_URL", DEFAULT_API_URL))
    demo.set_defaults(handler=_demo_command)

    catch_up = commands.add_parser("catch-up", help="Extract turns captured before models were ready and embed unembedded claims.")
    catch_up.add_argument("--host", choices=SUPPORTED_CONNECTION_HOSTS, help="Use the connection file onboarding wrote for this host.")
    catch_up.add_argument("--config", help="Protected Provena connection JSON file.")
    catch_up.add_argument("--api-url", default=os.getenv("PROVENA_API_URL", DEFAULT_API_URL))
    catch_up.add_argument("--max-batches", type=int, default=40, help="Stop after this many batches of up to 25 events and claims.")
    catch_up.set_defaults(handler=_catch_up_command)
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
