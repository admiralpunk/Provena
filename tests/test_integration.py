import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from provena.api import Settings, create_app
from provena.intelligence import ExtractedFact


@pytest.fixture(scope="module")
def url():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("set TEST_DATABASE_URL to a migrated disposable PostgreSQL database")
    return value


@pytest.fixture
def client(url):
    with TestClient(create_app(Settings(database_url=url, bootstrap_token="test-bootstrap-secret"))) as instance:
        yield instance


def tenant(client):
    response = client.post("/organizations", headers={"X-Bootstrap-Token": "test-bootstrap-secret"}, json={"name": "test tenant"})
    assert response.status_code == 201, response.text
    data = response.json()
    return data, {"X-API-Key": data["api_key"]}


def credential(client, organization_id, role="human", label="reviewer"):
    response = client.post(f"/organizations/{organization_id}/credentials", headers={"X-Bootstrap-Token": "test-bootstrap-secret"}, json={"role": role, "label": label})
    assert response.status_code == 201, response.text
    return response.json(), {"X-API-Key": response.json()["api_key"]}


def project(client, headers):
    response = client.post("/projects", headers=headers, json={"name": "sample"})
    assert response.status_code == 201, response.text
    return response.json()


def event(client, headers, scope_id, value="PostgreSQL"):
    response = client.post("/events", headers=headers, json={"scope_id": scope_id, "source_kind": "user_statement", "payload": {"text": f"Production uses {value}"}})
    assert response.status_code == 201, response.text
    assert response.json()["authority"] == "low"
    return response.json()["id"]


def claim(client, headers, scope_id, event_id, value="PostgreSQL"):
    response = client.post("/claims", headers=headers, json={"scope_id": scope_id, "subject": "project", "predicate": "production_database", "value": {"name": value}, "evidence_event_ids": [event_id]})
    assert response.status_code == 201, response.text
    return response.json()


def test_explain_retrieval_and_supersession(client):
    organization, headers = tenant(client)
    reviewer, human_headers = credential(client, organization["id"])
    scope = project(client, headers)["scope_id"]
    old = claim(client, headers, scope, event(client, headers, scope))
    assert old["status"] == "candidate"
    assert client.post(f"/claims/{old['id']}/status", headers=headers, json={"status": "active", "reason": "agent attempt"}).status_code == 403
    assert client.post(f"/claims/{old['id']}/status", headers=human_headers, json={"status": "active", "reason": "reviewed"}).status_code == 200
    result = client.get("/claims", headers=headers, params={"scope_id": scope})
    assert [x["id"] for x in result.json()["claims"]] == [old["id"]]
    new = claim(client, headers, scope, event(client, headers, scope, "MySQL"), "MySQL")
    assert old["id"] in new["possible_conflicts"]
    new_explanation = client.get(f"/claims/{new['id']}/explain", headers=headers).json()
    assert any(action["action"] == "possible_conflict" for action in new_explanation["actions"])
    assert any(relation["kind"] == "related_to" for relation in new_explanation["relationships"])
    relationship = client.post("/relationships", headers=human_headers, json={"from_claim_id": new["id"], "to_claim_id": old["id"], "kind": "supersedes", "reason": "documented migration"})
    assert relationship.status_code == 201, relationship.text
    assert client.post(f"/claims/{old['id']}/status", headers=human_headers, json={"status": "superseded", "reason": "documented migration"}).status_code == 200
    explained = client.get(f"/claims/{old['id']}/explain", headers=headers).json()
    assert explained["claim"]["status"] == "superseded"
    assert explained["evidence"][0]["event"]["payload"]["text"] == "Production uses PostgreSQL"
    assert len(explained["actions"]) == 3
    assert explained["actions"][1]["credential_id"] == reviewer["id"]
    assert explained["retrievals"][0]["id"] == result.json()["retrieval_id"]
    assert explained["action_influence"] == "not_tracked"


def test_tenant_and_branch_isolation(client):
    first_org, first = tenant(client)
    _, human = credential(client, first_org["id"])
    second_org, second = tenant(client)
    _, second_human = credential(client, second_org["id"])
    first_project = project(client, first)
    second_project = project(client, second)
    old = claim(client, first, first_project["scope_id"], event(client, first, first_project["scope_id"]))
    assert client.get(f"/claims/{old['id']}", headers=second).status_code == 404
    assert client.get("/claims", headers=second, params={"scope_id": first_project["scope_id"]}).status_code == 404
    own = claim(client, second, second_project["scope_id"], event(client, second, second_project["scope_id"]))
    assert client.post("/relationships", headers=second_human, json={"from_claim_id": own["id"], "to_claim_id": old["id"], "kind": "supports", "reason": "cross tenant"}).status_code == 404
    branch = client.post("/scopes", headers=first, json={"kind": "branch", "project_id": first_project["id"], "parent_id": first_project["scope_id"], "key": "feature/x"}).json()["id"]
    branch_claim = claim(client, first, branch, event(client, first, branch))
    client.post(f"/claims/{branch_claim['id']}/status", headers=human, json={"status": "active", "reason": "reviewed"})
    project_claims = client.get("/claims", headers=first, params={"scope_id": first_project["scope_id"]}).json()["claims"]
    assert [item["id"] for item in project_claims] == [old["id"]]
    assert client.get("/claims", headers=first, params={"scope_id": branch}).json()["claims"][0]["id"] == branch_claim["id"]
    assert second_project["scope_id"] != first_project["scope_id"]


def test_database_invariants(client, url):
    first, headers = tenant(client)
    second, other_headers = tenant(client)
    scope = project(client, headers)["scope_id"]
    other_scope = project(client, other_headers)["scope_id"]
    event_id = event(client, headers, scope)
    claim_id = claim(client, headers, scope, event_id)["id"]
    other_claim = claim(client, other_headers, other_scope, event(client, other_headers, other_scope))["id"]
    engine = create_engine(url)
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("UPDATE event SET payload='{}'::jsonb WHERE id=:id"), {"id": event_id})
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("UPDATE claim SET subject='changed' WHERE id=:id"), {"id": claim_id})
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("UPDATE claim SET status='active' WHERE id=:id"), {"id": claim_id})
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("INSERT INTO memory_action (id, organization_id, claim_id, action, version, old_status, new_status, reason, actor_ref, credential_id) VALUES (gen_random_uuid(), :org, :claim, 'status_changed', 1, 'candidate', 'active', 'forged', 'agent', :credential)"), {"org": first["id"], "claim": claim_id, "credential": first["credential_id"]})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("INSERT INTO evidence (id, organization_id, claim_id, event_id) VALUES (gen_random_uuid(), :org, :claim, gen_random_uuid())"), {"org": first["id"], "claim": claim_id})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("INSERT INTO claim_relationship (id, organization_id, from_claim_id, to_claim_id, kind, reason) VALUES (gen_random_uuid(), :org, :from_id, :to_id, 'contradicts', 'cross tenant')"), {"org": first["id"], "from_id": claim_id, "to_id": other_claim})
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("INSERT INTO claim (id, organization_id, scope_id, subject, predicate, value, status, status_version) VALUES (gen_random_uuid(), :org, :scope, 'x', 'y', '{}'::jsonb, 'candidate', 0)"), {"org": first["id"], "scope": scope})
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("INSERT INTO event (id, organization_id, scope_id, credential_id, source_kind, authority, payload) VALUES (gen_random_uuid(), :org, :scope, :credential, 'user_statement', 'medium', '{}'::jsonb)"), {"org": first["id"], "scope": scope, "credential": first["credential_id"]})
    engine.dispose()


def test_temporal_change_is_not_forced_conflict(client):
    _, headers = tenant(client)
    scope = project(client, headers)["scope_id"]
    first = client.post("/claims", headers=headers, json={"scope_id": scope, "subject": "backend", "predicate": "language", "value": {"name": "Go"}, "evidence_event_ids": [event(client, headers, scope)], "valid_from": "2026-01-01T00:00:00Z", "valid_to": "2026-09-01T00:00:00Z"})
    assert first.status_code == 201, first.text
    later = client.post("/claims", headers=headers, json={"scope_id": scope, "subject": "backend", "predicate": "language", "value": {"name": "Python"}, "evidence_event_ids": [event(client, headers, scope)], "valid_from": "2026-09-01T00:00:00Z"})
    assert later.status_code == 201, later.text
    assert later.json()["possible_conflicts"] == []


def test_source_roles_and_credential_rotation(client):
    organization, agent_headers = tenant(client)
    human, human_headers = credential(client, organization["id"], "human", "Alice")
    tool, tool_headers = credential(client, organization["id"], "tool", "CI runner")
    scope = project(client, agent_headers)["scope_id"]
    def post_event(headers, kind):
        return client.post("/events", headers=headers, json={"scope_id": scope, "source_kind": kind, "payload": {"text": "observed"}})
    assert post_event(agent_headers, "tool_observation").status_code == 403
    assert post_event(human_headers, "test_output").status_code == 403
    correction = post_event(human_headers, "user_correction")
    assert correction.status_code == 201
    assert correction.json()["authority"] == "high"
    correction_claim = claim(client, human_headers, scope, correction.json()["id"])
    explained = client.get(f"/claims/{correction_claim['id']}/explain", headers=agent_headers).json()
    assert explained["evidence"][0]["event"]["credential"]["role"] == "human"
    assert explained["evidence"][0]["event"]["credential"]["label"] == "Alice"
    output = post_event(tool_headers, "test_output")
    assert output.status_code == 201
    assert output.json()["authority"] == "high"
    rotated = client.post(f"/organizations/{organization['id']}/credentials/{human['id']}/rotate", headers={"X-Bootstrap-Token": "test-bootstrap-secret"})
    assert rotated.status_code == 200, rotated.text
    assert post_event(human_headers, "user_statement").status_code == 401
    new_human_headers = {"X-API-Key": rotated.json()["api_key"]}
    assert post_event(new_human_headers, "user_statement").json()["authority"] == "medium"
    historical = client.get(f"/events/{correction.json()['id']}", headers=agent_headers).json()
    assert historical["credential_id"] == human["id"]
    assert historical["authority"] == "high"
    other, _ = tenant(client)
    assert client.post(f"/organizations/{other['id']}/credentials/{tool['id']}/rotate", headers={"X-Bootstrap-Token": "test-bootstrap-secret"}).status_code == 404
    assert client.post(f"/organizations/{organization['id']}/credentials", headers=agent_headers, json={"role": "human", "label": "forged"}).status_code == 403


def test_conflict_review_outcomes(client):
    organization, agent_headers = tenant(client)
    reviewer, human_headers = credential(client, organization["id"])
    scope = project(client, agent_headers)["scope_id"]
    cases = []
    for index, decision in enumerate(("contradiction", "temporal_change", "dismissed")):
        subject = f"service-{index}"
        previous_event = event(client, agent_headers, scope, "Go")
        current_event = event(client, agent_headers, scope, "Python")
        def make_claim(value, event_id):
            return client.post("/claims", headers=agent_headers, json={"scope_id": scope, "subject": subject, "predicate": "language", "value": {"name": value}, "evidence_event_ids": [event_id]}).json()
        previous = make_claim("Go", previous_event)
        current = make_claim("Python", current_event)
        assert client.post("/relationships", headers=human_headers, json={"from_claim_id": current["id"], "to_claim_id": previous["id"], "kind": "related_to", "reason": "manual"}).status_code == 422
        assert previous["id"] in current["possible_conflicts"]
        pending = client.get("/conflicts", headers=agent_headers, params={"scope_id": scope}).json()["cases"]
        case = next(item for item in pending if item["from_claim_id"] == current["id"])
        assert case["from_claim"]["value"] == {"name": "Python"}
        assert case["to_claim"]["value"] == {"name": "Go"}
        review_body = {"decision": decision, "reason": "reviewed evidence"}
        if decision == "temporal_change":
            assert client.post(f"/conflicts/{case['id']}/review", headers=human_headers, json=review_body).status_code == 422
            review_body["superseding_claim_id"] = previous["id"]
        assert client.post(f"/conflicts/{case['id']}/review", headers=agent_headers, json=review_body).status_code == 403
        reviewed = client.post(f"/conflicts/{case['id']}/review", headers=human_headers, json=review_body)
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["reviewer_credential_id"] == reviewer["id"]
        assert client.post(f"/conflicts/{case['id']}/review", headers=human_headers, json={**review_body, "reason": "again"}).status_code == 409
        explanation = client.get(f"/claims/{current['id']}/explain", headers=agent_headers).json()
        assert explanation["conflict_reviews"][0]["decision"] == decision
        kinds = {relation["kind"] for relation in explanation["relationships"]}
        expected = {"contradiction": "contradicts", "temporal_change": "supersedes"}.get(decision)
        if expected:
            assert expected in kinds
            if decision == "temporal_change":
                assert reviewed.json()["superseding_claim_id"] == previous["id"]
                relation = next(item for item in explanation["relationships"] if item["kind"] == "supersedes")
                assert relation["from_claim_id"] == previous["id"]
                assert relation["to_claim_id"] == current["id"]
        else:
            assert kinds == {"related_to"}
        cases.append(case["id"])
    remaining = client.get("/conflicts", headers=agent_headers, params={"scope_id": scope}).json()["cases"]
    assert not any(case["id"] in cases for case in remaining)


def test_mcp_agent_flow(client):
    mcp = pytest.importorskip("mcp")
    from provena.mcp_server import ProvenaHTTPClient, build_server

    organization, agent_headers = tenant(client)
    _, human_headers = credential(client, organization["id"])
    scope = project(client, agent_headers)["scope_id"]
    rest = ProvenaHTTPClient("http://testserver", agent_headers["X-API-Key"], scope, http=client)

    async def scenario():
        async with mcp.Client(build_server(rest)) as agent:
            listed = await agent.list_tools()
            names = {tool.name for tool in listed.tools}
            assert names == {"memory_context", "memory_search", "memory_capture_turn", "memory_record_event", "memory_remember", "memory_propose_claim", "memory_explain"}
            assert "memory_activate" not in names
            event_result = await agent.call_tool("memory_record_event", {"text": "Assistant noticed a PostgreSQL deployment config"})
            assert not event_result.is_error
            event_id = event_result.structured_content["id"]
            proposal = await agent.call_tool("memory_propose_claim", {"event_id": event_id, "subject": "project", "predicate": "production_database", "value": {"name": "PostgreSQL"}})
            assert not proposal.is_error
            claim_id = proposal.structured_content["id"]
            assert proposal.structured_content["status"] == "candidate"
            before = await agent.call_tool("memory_search", {"predicate": "production_database"})
            assert before.structured_content["claims"][0]["id"] == claim_id
            assert before.structured_content["claims"][0]["status"] == "candidate"
            assert client.post(f"/claims/{claim_id}/status", headers=human_headers, json={"status": "active", "reason": "reviewed source"}).status_code == 200
            found = await agent.call_tool("memory_search", {"predicate": "production_database"})
            assert found.structured_content["claims"][0]["id"] == claim_id
            assert found.structured_content["claims"][0]["sources"][0]["authority"] == "low"
            explanation = await agent.call_tool("memory_explain", {"claim_id": claim_id})
            assert explanation.structured_content["evidence"][0]["event"]["payload"]["text"] == "Assistant noticed a PostgreSQL deployment config"

            remembered = await agent.call_tool("memory_remember", {"text": "Assistant inferred local development uses PostgreSQL", "subject": "project", "predicate": "local_development_database", "value": {"name": "PostgreSQL"}})
            assert not remembered.is_error
            saved = remembered.structured_content
            assert saved["event"]["authority"] == "low"
            assert saved["claim"]["status"] == "candidate"
            confirmed = await agent.call_tool("memory_explain", {"claim_id": saved["claim"]["id"]})
            assert confirmed.structured_content["evidence"][0]["event"]["id"] == saved["event"]["id"]

    asyncio.run(scenario())


def test_mcp_explain_respects_configured_scope(client):
    pytest.importorskip("mcp")
    from provena.mcp_server import ProvenaHTTPClient

    organization, headers = tenant(client)
    first = project(client, headers)["scope_id"]
    second = client.post("/projects", headers=headers, json={"name": "another"}).json()["scope_id"]
    second_claim = claim(client, headers, second, event(client, headers, second))
    adapter = ProvenaHTTPClient("http://testserver", headers["X-API-Key"], first, http=client)
    with pytest.raises(ValueError, match="outside the configured MCP scope"):
        adapter.explain(second_claim["id"])


def test_atomic_memory_write_and_candidate_review_boundary(client, url):
    organization, agent = tenant(client)
    scope = project(client, agent)["scope_id"]
    body = {"scope_id": scope, "source_kind": "user_statement", "text": "Local development uses PostgreSQL.", "proposition": {"subject": "project", "predicate": "local_development_database", "value": {"name": "PostgreSQL"}}}
    saved = client.post("/memories", headers=agent, json=body)
    assert saved.status_code == 201, saved.text
    result = saved.json()
    assert result["event"]["authority"] == "low"
    assert result["claim"]["status"] == "candidate"
    explained = client.get(f"/claims/{result['claim']['id']}/explain", headers=agent).json()
    assert explained["evidence"][0]["event"]["id"] == result["event"]["id"]
    assert explained["evidence"][0]["event"]["payload"]["text"] == body["text"]
    provisional = client.get("/claims", headers=agent, params={"scope_id": scope}).json()["claims"]
    assert provisional[0]["id"] == result["claim"]["id"]
    assert provisional[0]["status"] == "candidate"

    captured = client.post("/memories", headers=agent, json={"scope_id": scope, "source_kind": "assistant_inference", "text": "Potential migration discussed."})
    assert captured.status_code == 201
    assert captured.json()["claim"] is None

    engine = create_engine(url)
    with engine.connect() as connection:
        before = connection.scalar(text("SELECT count(*) FROM event WHERE organization_id=:org"), {"org": organization["id"]})
    invalid = client.post("/memories", headers=agent, json={**body, "proposition": {**body["proposition"], "valid_from": "2026-09-20T00:00:00Z", "valid_to": "2026-09-19T00:00:00Z"}})
    assert invalid.status_code == 422
    assert client.post("/memories", headers=agent, json={**body, "text": "   "}).status_code == 422
    with engine.connect() as connection:
        after = connection.scalar(text("SELECT count(*) FROM event WHERE organization_id=:org"), {"org": organization["id"]})
    assert before == after
    engine.dispose()


def test_opt_in_conversation_capture(client):
    from provena.capture import ConversationCapture

    organization, agent = tenant(client)
    scope = project(client, agent)["scope_id"]
    capture = ConversationCapture("http://testserver", agent["X-API-Key"], scope, http=client)
    assert capture.record_turn("user", "Bananas are red.") is None

    capture.enabled = True
    user_turn = capture.record_turn("user", "Local development uses PostgreSQL.", {"subject": "project", "predicate": "local_development_database", "value": {"name": "PostgreSQL"}})
    assert user_turn is not None
    assert user_turn["source_kind"] == "user_statement"
    assert user_turn["event"]["authority"] == "low"
    assert user_turn["claim"]["status"] == "candidate"
    explained = client.get(f"/claims/{user_turn['claim']['id']}/explain", headers=agent).json()
    assert explained["evidence"][0]["event"]["credential"]["role"] == "agent"
    assert explained["evidence"][0]["event"]["payload"]["text"] == "Local development uses PostgreSQL."

    assistant_turn = capture.record_turn("assistant", "Maybe the backend is Python.")
    assert assistant_turn is not None
    assert assistant_turn["claim"] is None
    assert client.get(f"/events/{assistant_turn['event']['id']}", headers=agent).json()["source_kind"] == "assistant_inference"
    with pytest.raises(ValueError, match="role must be"):
        capture.record_turn("tool", "forged output")

    portable = ConversationCapture("http://testserver", agent["X-API-Key"], scope, enabled=True, session_external_ref="claude:session-42", http=client)
    first = portable.record_turn("user", "Remember this across agents.")
    second = portable.record_turn("assistant", "I will use the shared scope.")
    assert first["session_id"] == second["session_id"]


def test_automatic_extraction_and_semantic_candidate_retrieval(url):
    class FakeIntelligence:
        extraction_model = "test-extractor-v1"
        embedding_model = "test-embedding-v1"
        fail = False

        def extract(self, source, source_kind):
            if self.fail:
                raise RuntimeError("temporary extractor failure")
            if "cheese" in source.lower():
                return [ExtractedFact(subject="user", predicate="dietary_allergy", value={"food": "cheese"}, confidence=0.98)]
            return []

        def embed(self, texts):
            return [[1.0, 0.0] + [0.0] * 1534 if "cheese" in text.lower() else [0.0, 1.0] + [0.0] * 1534 for text in texts]

    settings = Settings(database_url=url, bootstrap_token="test-bootstrap-secret")
    fake = FakeIntelligence()
    with TestClient(create_app(settings, intelligence=fake)) as semantic_client:
        organization, agent = tenant(semantic_client)
        scope = project(semantic_client, agent)["scope_id"]
        source = semantic_client.post("/memories", headers=agent, json={"scope_id": scope, "source_kind": "user_statement", "text": "I am allergic to cheese."}).json()["event"]
        extracted = semantic_client.post(f"/events/{source['id']}/extract", headers=agent)
        assert extracted.status_code == 201, extracted.text
        result = extracted.json()
        assert result["status"] == "completed", result
        assert result["claims"][0]["status"] == "candidate"
        claim_id = result["claims"][0]["id"]
        repeated = semantic_client.post(f"/events/{source['id']}/extract", headers=agent).json()
        assert repeated["reused"] is True
        assert claim_id in repeated["claim_ids"]

        found = semantic_client.get("/claims", headers=agent, params={"scope_id": scope, "q": "Which pizza is safe without cheese?"})
        assert found.status_code == 200, found.text
        payload = found.json()
        assert payload["claims"][0]["id"] == claim_id
        assert payload["claims"][0]["status"] == "candidate"
        assert payload["claims"][0]["sources"][0]["source_kind"] == "user_statement"
        explanation = semantic_client.get(f"/claims/{claim_id}/explain", headers=agent).json()
        assert explanation["evidence"][0]["event"]["payload"]["text"] == "I am allergic to cheese."
        assert any(action["action"] == "extracted" for action in explanation["actions"])
        assert explanation["extractions"][0]["extractor_model"] == "test-extractor-v1"

        _, other_agent = tenant(semantic_client)
        other_scope = project(semantic_client, other_agent)["scope_id"]
        assert semantic_client.get("/claims", headers=other_agent, params={"scope_id": other_scope, "q": "cheese allergy"}).json()["claims"] == []

        retry_event = semantic_client.post("/memories", headers=agent, json={"scope_id": scope, "source_kind": "user_statement", "text": "Cheese causes an allergic reaction."}).json()["event"]
        fake.fail = True
        failed = semantic_client.post(f"/events/{retry_event['id']}/extract", headers=agent).json()
        assert failed["status"] == "failed"
        fake.fail = False
        retried = semantic_client.post(f"/events/{retry_event['id']}/extract", headers=agent).json()
        assert retried["status"] == "completed"
        assert retried["reused"] is False

    engine = create_engine(url)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(text("UPDATE extraction_run SET status='failed' WHERE id=:id"), {"id": result["id"]})
    engine.dispose()
