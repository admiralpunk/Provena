"""Deterministic agent workflow over the real local MCP stdio transport.

Requires an active production_database claim in PROVENA_SCOPE_ID, a running API,
and an agent credential in PROVENA_API_KEY. See README.md.
"""

import asyncio
import os
import sys

from mcp import Client, StdioServerParameters


async def call(agent: Client, name: str, arguments: dict) -> dict:
    result = await agent.call_tool(name, arguments)
    if result.is_error or result.structured_content is None:
        raise RuntimeError(f"{name} failed: {result.content}")
    return result.structured_content


async def main() -> None:
    required = ("PROVENA_API_KEY", "PROVENA_SCOPE_ID")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Set {', '.join(missing)} before running this example")
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "provena.mcp_server"],
        env={name: os.environ[name] for name in ("PROVENA_API_KEY", "PROVENA_SCOPE_ID", "PROVENA_API_URL") if name in os.environ},
    )
    async with Client(server) as agent:
        result = await call(agent, "memory_search", {"predicate": "production_database", "limit": 1})
        if not result["claims"]:
            raise SystemExit("No active production_database claim in this scope; complete the README API walkthrough first")
        remembered = result["claims"][0]
        source = remembered["sources"][0]
        print(f"Agent context: {remembered['subject']}.{remembered['predicate']} = {remembered['value']}")
        print(f"Attribution: claim {remembered['id']}; event {source['event_id']}; source authority {source['authority']}")
        print("Agent answer: The recorded production database is shown above; review its evidence before acting on it.")

        event = await call(agent, "memory_record_event", {"text": "Possible backup tool: pg_dump. This is an unverified agent hypothesis.", "source_kind": "hypothesis"})
        candidate = await call(agent, "memory_propose_claim", {"event_id": event["id"], "subject": "project", "predicate": "backup_tool_candidate", "value": {"name": "pg_dump"}})
        explanation = await call(agent, "memory_explain", {"claim_id": candidate["id"]})
        print(f"New memory: claim {candidate['id']} is {candidate['status']} and requires human review")
        print(f"Why: event {explanation['evidence'][0]['event']['id']} has authority {explanation['evidence'][0]['event']['authority']}")


if __name__ == "__main__":
    asyncio.run(main())
