import asyncio

import httpx
import pytest

mcp = pytest.importorskip("mcp")

from provena.integrations.mcp_server import ProvenaHTTPClient, ProvenaToolError, build_server

SCOPE = "00000000-0000-4000-8000-000000000000"


def _client(handler) -> ProvenaHTTPClient:
    return ProvenaHTTPClient("http://127.0.0.1:8000", "agent-key", SCOPE, http=httpx.Client(transport=httpx.MockTransport(handler)))


def _call(client: ProvenaHTTPClient, tool: str, arguments: dict):
    async def scenario():
        async with mcp.Client(build_server(client)) as agent:
            return await agent.call_tool(tool, arguments)

    return asyncio.run(scenario())


def _text(result) -> str:
    return " ".join(getattr(block, "text", "") for block in result.content)


def test_unreachable_service_is_explained_to_the_agent():
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    result = _call(_client(refuse), "memory_context", {"query": "database"})

    assert result.is_error
    assert "not reachable at http://127.0.0.1:8000" in _text(result)
    assert "provena status" in _text(result)


def test_rejected_credentials_name_the_configuration_to_check():
    result = _call(_client(lambda request: httpx.Response(401, json={"detail": "invalid API key"})), "memory_search", {"query": "x"})

    assert result.is_error
    assert "401: invalid API key" in _text(result)
    assert "PROVENA_API_KEY" in _text(result)


def test_invalid_claim_id_is_reported_without_calling_the_api():
    def unexpected(request):
        raise AssertionError("the API must not be called")

    result = _call(_client(unexpected), "memory_explain", {"claim_id": "not-a-uuid"})

    assert result.is_error
    assert "claim_id must be a UUID" in _text(result)


def test_client_errors_remain_value_errors_for_direct_callers():
    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        _client(lambda request: httpx.Response(200, json={})).search(limit=0)
    assert issubclass(ProvenaToolError, ValueError)
