import io
import json

import httpx

from provena.agent_hooks import capture_run as run


SCOPE_ID = "fdf2203a-9909-4035-ad68-de28b6b1aa87"


def test_user_prompt_hook_records_exact_prompt_and_codex_actor():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/extract"):
            return httpx.Response(201, json={"status": "completed", "claims": []})
        return httpx.Response(201, json={"event": {"id": "event-id"}, "claim": None})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    payload = {"hook_event_name": "UserPromptSubmit", "session_id": "session-1", "turn_id": "turn-2", "prompt": "banana is red"}
    stderr = io.StringIO()
    assert run(io.StringIO(json.dumps(payload)), stderr, {"PROVENA_API_URL": "http://provena.test", "PROVENA_API_KEY": "secret", "PROVENA_SCOPE_ID": SCOPE_ID}, client) == 0
    assert stderr.getvalue() == ""
    assert len(requests) == 2
    body = json.loads(requests[0].content)
    assert body == {"scope_id": SCOPE_ID, "source_kind": "user_statement", "text": "banana is red", "session_external_ref": "codex:session-1", "actor_ref": "codex:session-1:turn:turn-2"}
    assert requests[0].headers["X-API-Key"] == "secret"
    assert requests[1].url.path == "/events/event-id/extract"


def test_stop_hook_records_assistant_as_inference():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/extract"):
            return httpx.Response(201, json={"status": "completed", "claims": []})
        return httpx.Response(201, json={"event": {"id": "assistant-event"}, "claim": None})

    payload = {"hook_event_name": "Stop", "session_id": "session-1", "turn_id": "turn-2", "last_assistant_message": "Try a cheese-free pizza."}
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert run(io.StringIO(json.dumps(payload)), io.StringIO(), {"PROVENA_API_KEY": "secret", "PROVENA_SCOPE_ID": SCOPE_ID}, client) == 0
    body = json.loads(requests[0].content)
    assert body["source_kind"] == "assistant_inference"
    assert body["text"] == "Try a cheese-free pizza."


def test_hook_fails_open_when_provena_is_unavailable():
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    payload = {"hook_event_name": "UserPromptSubmit", "session_id": "session-1", "turn_id": "turn-2", "prompt": "keep working"}
    stderr = io.StringIO()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert run(io.StringIO(json.dumps(payload)), stderr, {"PROVENA_API_KEY": "secret", "PROVENA_SCOPE_ID": SCOPE_ID}, client) == 0
    assert "Provena capture failed" in stderr.getvalue()


def test_gemini_after_agent_captures_assistant_response():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/extract"):
            return httpx.Response(201, json={"status": "completed", "claims": []})
        return httpx.Response(201, json={"event": {"id": "gemini-event"}, "claim": None})

    from provena.agent_hooks import capture_run

    payload = {"hook_event_name": "AfterAgent", "session_id": "gemini-1", "prompt_response": "Use a cheese-free crust."}
    environment = {"PROVENA_API_KEY": "secret", "PROVENA_SCOPE_ID": SCOPE_ID, "PROVENA_AGENT_HOST": "gemini"}
    assert capture_run(io.StringIO(json.dumps(payload)), io.StringIO(), environment, httpx.Client(transport=httpx.MockTransport(handler))) == 0
    body = json.loads(requests[0].content)
    assert body["source_kind"] == "assistant_inference"
    assert body["session_external_ref"] == "gemini:gemini-1"
