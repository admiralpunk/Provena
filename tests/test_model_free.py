"""ADR 0025: retrieval without local models, and catch-up once models are ready."""

import os

import pytest
from fastapi.testclient import TestClient

from provena.api import Settings, create_app
from provena.memory.intelligence import ExtractedFact

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="requires TEST_DATABASE_URL")

BOOTSTRAP = "test-bootstrap-secret"


def _settings(memory_provider: str = "none") -> Settings:
    return Settings(database_url=os.environ["TEST_DATABASE_URL"], bootstrap_token=BOOTSTRAP, memory_provider=memory_provider)


def _workspace(client):
    organization = client.post("/organizations", headers={"X-Bootstrap-Token": BOOTSTRAP}, json={"name": "model-free"})
    assert organization.status_code == 201, organization.text
    agent = {"X-API-Key": organization.json()["api_key"]}
    scope = client.post("/projects", headers=agent, json={"name": "model-free"}).json()["scope_id"]
    return organization.json(), agent, scope


def _remember(client, agent, scope, text, subject, predicate, value):
    saved = client.post("/memories", headers=agent, json={"scope_id": scope, "source_kind": "user_statement", "text": text, "proposition": {"subject": subject, "predicate": predicate, "value": value}})
    assert saved.status_code == 201, saved.text
    return saved.json()


def _method(client, agent, retrieval_id):
    return client.get(f"/operator/retrievals/{retrieval_id}", headers=agent).json()["retrieval"]["method"]


class WarmingIntelligence:
    """Fails like an Ollama whose models are still downloading, until `ready` is set."""

    extraction_model = "warm-extractor-v1"
    embedding_model = "warm-embedding-v1"

    def __init__(self):
        self.ready = False

    def extract(self, source, source_kind):
        if not self.ready:
            raise RuntimeError("model 'warm-extractor-v1' not found, try pulling it first")
        if "peanut" in source.lower():
            return [ExtractedFact(subject="user", predicate="food_allergy", value={"food": "peanuts"}, confidence=0.97)]
        return []

    def embed(self, texts):
        if not self.ready:
            raise RuntimeError("model 'warm-embedding-v1' not found, try pulling it first")
        return [[1.0, 0.0, 0.0] if "postgres" in text.lower() else [0.0, 1.0, 0.0] for text in texts]


def test_text_query_without_models_uses_audited_fulltext_retrieval():
    with TestClient(create_app(_settings())) as client:
        _, agent, scope = _workspace(client)
        remembered = _remember(client, agent, scope, "Local development uses PostgreSQL.", "project", "local_development_database", {"name": "PostgreSQL"})
        _remember(client, agent, scope, "The user prefers tabs.", "user", "indentation_preference", {"style": "tabs"})

        found = client.get("/claims", headers=agent, params={"scope_id": scope, "q": "Which database should I use for local development here?"})

        assert found.status_code == 200, found.text
        claims = found.json()["claims"]
        assert [claim["id"] for claim in claims] == [remembered["claim"]["id"]]
        assert claims[0]["status"] == "candidate"
        assert claims[0]["sources"][0]["authority"] == "low"
        assert _method(client, agent, found.json()["retrieval_id"]) == "fulltext"


def test_fulltext_matches_json_values_and_stays_in_exact_scope():
    with TestClient(create_app(_settings())) as client:
        _, agent, scope = _workspace(client)
        other_scope = client.post("/projects", headers=agent, json={"name": "other"}).json()["scope_id"]
        _remember(client, agent, other_scope, "Production uses MySQL.", "project", "production_database", {"name": "MySQL"})
        mine = _remember(client, agent, scope, "Staging uses MySQL too.", "project", "staging_database", {"name": "MySQL"})

        found = client.get("/claims", headers=agent, params={"scope_id": scope, "q": "mysql"}).json()["claims"]

        assert [claim["id"] for claim in found] == [mine["claim"]["id"]]


@pytest.mark.parametrize("query", ["the and of it", "it's O'Brien & co | !(x) :*", "—"])
def test_fulltext_handles_stop_words_and_query_syntax_characters(query):
    with TestClient(create_app(_settings())) as client:
        _, agent, scope = _workspace(client)
        _remember(client, agent, scope, "O'Brien owns the deploy key rotation.", "team", "key_rotation_owner", {"name": "O'Brien"})

        found = client.get("/claims", headers=agent, params={"scope_id": scope, "q": query})

        assert found.status_code == 200, found.text


def test_unreachable_ollama_falls_back_to_fulltext_and_reports_catch_up_errors():
    # Port 9 is reserved (discard) and refuses connections: Ollama is configured but not running.
    settings = Settings(database_url=os.environ["TEST_DATABASE_URL"], bootstrap_token=BOOTSTRAP, memory_provider="ollama", ollama_base_url="http://127.0.0.1:9")
    with TestClient(create_app(settings)) as client:
        _, agent, scope = _workspace(client)
        remembered = _remember(client, agent, scope, "Local development uses PostgreSQL.", "project", "local_development_database", {"name": "PostgreSQL"})

        found = client.get("/claims", headers=agent, params={"scope_id": scope, "q": "postgresql"}).json()
        assert [claim["id"] for claim in found["claims"]] == [remembered["claim"]["id"]]
        assert _method(client, agent, found["retrieval_id"]) == "fulltext"

        summary = client.post(f"/scopes/{scope}/catch-up", headers=agent).json()
        assert summary["embedded_claims"] == 0 and summary["embedding_error"]


def test_catch_up_requires_a_configured_model():
    with TestClient(create_app(_settings())) as client:
        _, agent, scope = _workspace(client)
        response = client.post(f"/scopes/{scope}/catch-up", headers=agent)
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]


def test_models_warming_up_fall_back_then_catch_up_is_idempotent():
    warming = WarmingIntelligence()
    with TestClient(create_app(_settings(), intelligence=warming)) as client:
        _, agent, scope = _workspace(client)
        other_scope = client.post("/projects", headers=agent, json={"name": "untouched"}).json()["scope_id"]

        # While models download: capture keeps evidence, extraction fails and is recorded, recall still works.
        captured = client.post("/memories", headers=agent, json={"scope_id": scope, "source_kind": "user_statement", "text": "I am allergic to peanuts."}).json()["event"]
        attempt = client.post(f"/events/{captured['id']}/extract", headers=agent).json()
        assert attempt["status"] == "failed"
        elsewhere = client.post("/memories", headers=agent, json={"scope_id": other_scope, "source_kind": "user_statement", "text": "Peanuts are fine for me."}).json()["event"]
        assert client.post(f"/events/{elsewhere['id']}/extract", headers=agent).json()["status"] == "failed"
        remembered = _remember(client, agent, scope, "Local development uses PostgreSQL.", "project", "local_development_database", {"name": "PostgreSQL"})
        early = client.get("/claims", headers=agent, params={"scope_id": scope, "q": "postgresql database"}).json()
        assert [claim["id"] for claim in early["claims"]] == [remembered["claim"]["id"]]
        assert _method(client, agent, early["retrieval_id"]) == "fulltext"

        warming.ready = True
        caught_up = client.post(f"/scopes/{scope}/catch-up", headers=agent)

        assert caught_up.status_code == 200, caught_up.text
        summary = caught_up.json()
        assert summary["retried_events"] == 1 and summary["extracted_events"] == 1 and summary["still_failing_events"] == 0
        assert summary["embedded_claims"] == 1  # the remembered claim; extraction embeds its own claim
        assert summary["more_pending"] is False

        again = client.post(f"/scopes/{scope}/catch-up", headers=agent).json()
        assert again["retried_events"] == 0 and again["embedded_claims"] == 0

        semantic = client.get("/claims", headers=agent, params={"scope_id": scope, "q": "postgres setup"}).json()
        assert semantic["claims"][0]["id"] == remembered["claim"]["id"]
        assert _method(client, agent, semantic["retrieval_id"]) == "semantic"

        allergy = [claim for claim in client.get("/claims", headers=agent, params={"scope_id": scope, "predicate": "food_allergy"}).json()["claims"]]
        assert len(allergy) == 1 and allergy[0]["status"] == "candidate"
        explained = client.get(f"/claims/{allergy[0]['id']}/explain", headers=agent).json()
        assert explained["evidence"][0]["event"]["id"] == captured["id"]

        # The other scope's failed extraction was not touched.
        untouched = client.get("/claims", headers=agent, params={"scope_id": other_scope, "predicate": "food_allergy"}).json()["claims"]
        assert untouched == []
