import io
import json

import httpx

from provena.agent_hooks import context_run as run


def test_retrieval_hook_injects_attributed_candidate_context():
    def handler(request):
        assert request.url.params["q"] == "suggest pizzas"
        return httpx.Response(200, json={"claims": [{"id": "claim-1", "subject": "user", "predicate": "dietary_allergy", "value": {"food": "cheese"}, "status": "candidate", "sources": [{"source_kind": "user_statement", "authority": "low"}]}]})

    output = io.StringIO()
    error = io.StringIO()
    payload = {"hook_event_name": "UserPromptSubmit", "prompt": "suggest pizzas"}
    environment = {"PROVENA_API_KEY": "secret", "PROVENA_SCOPE_ID": "scope"}
    assert run(io.StringIO(json.dumps(payload)), output, error, environment, httpx.Client(transport=httpx.MockTransport(handler))) == 0
    result = json.loads(output.getvalue())
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "pending human review" in context
    assert '"food":"cheese"' in context
    assert error.getvalue() == ""


def test_retrieval_hook_fails_open():
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    payload = {"hook_event_name": "UserPromptSubmit", "prompt": "hello"}
    output, error = io.StringIO(), io.StringIO()
    environment = {"PROVENA_API_KEY": "secret", "PROVENA_SCOPE_ID": "scope"}
    assert run(io.StringIO(json.dumps(payload)), output, error, environment, httpx.Client(transport=httpx.MockTransport(handler))) == 0
    assert output.getvalue() == ""
    assert "Provena retrieval failed" in error.getvalue()


def test_gemini_before_agent_uses_portable_hook_event_name():
    def handler(request):
        return httpx.Response(200, json={"claims": [{"id": "claim-1", "subject": "user", "predicate": "allergy", "value": {"food": "cheese"}, "status": "candidate", "sources": []}]})

    from provena.agent_hooks import context_run

    output = io.StringIO()
    payload = {"hook_event_name": "BeforeAgent", "prompt": "pizza", "session_id": "gemini-1"}
    environment = {"PROVENA_API_KEY": "secret", "PROVENA_SCOPE_ID": "scope"}
    assert context_run(io.StringIO(json.dumps(payload)), output, io.StringIO(), environment, httpx.Client(transport=httpx.MockTransport(handler))) == 0
    assert json.loads(output.getvalue())["hookSpecificOutput"]["hookEventName"] == "BeforeAgent"
