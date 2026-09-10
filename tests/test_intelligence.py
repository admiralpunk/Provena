import json

import httpx

from provena.memory.intelligence import OllamaMemoryIntelligence, StructuredFacts, parse_value_object


def test_provider_schema_is_strict_and_supports_json_claim_values():
    schema = StructuredFacts.model_json_schema()
    assert schema["additionalProperties"] is False
    fact_schema = schema["$defs"]["StructuredFact"]
    assert fact_schema["additionalProperties"] is False
    parsed = StructuredFacts.model_validate({"facts": [{"subject": "user", "predicate": "dietary_allergy", "value_json": '{"food":"cheese"}', "confidence": 0.98}]})
    assert json.loads(parsed.facts[0].value_json) == {"food": "cheese"}
    percentage = StructuredFacts.model_validate({"facts": [{"subject": "user", "predicate": "dietary_allergy", "value_json": '{"food":"cheese"}', "confidence": 100}]})
    assert percentage.facts[0].confidence == 1
    assert parse_value_object("{'food': 'cheese'}") == {"food": "cheese"}


def test_ollama_extracts_structured_facts_and_embeds_locally():
    requests = []

    def handler(request: httpx.Request):
        requests.append((request.url.path, json.loads(request.content)))
        if request.url.path == "/api/chat":
            content = {"facts": [{"subject": "user", "predicate": "food_allergy", "value_json": '{"food":"cheese"}', "confidence": 0.99}]}
            return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps(content)}})
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})
        return httpx.Response(404)

    intelligence = OllamaMemoryIntelligence(transport=httpx.MockTransport(handler))
    facts = intelligence.extract("I am allergic to cheese", "user_statement")
    embeddings = intelligence.embed(["user food_allergy cheese"])

    assert facts[0].value == {"food": "cheese"}
    assert embeddings == [[0.1, 0.2, 0.3]]
    assert intelligence.extraction_model == "ollama:qwen2.5:1.5b"
    assert intelligence.embedding_model == "ollama:nomic-embed-text"
    assert requests[0][1]["format"]["additionalProperties"] is False
    assert requests[0][1]["stream"] is False
    assert requests[1][1]["input"] == ["user food_allergy cheese"]


def test_ollama_rejects_embedding_count_mismatch():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={"embeddings": []})

    intelligence = OllamaMemoryIntelligence(transport=httpx.MockTransport(handler))
    try:
        intelligence.embed(["one"])
    except ValueError as exc:
        assert str(exc) == "Ollama returned an unexpected number of embeddings"
    else:
        raise AssertionError("expected embedding count validation")
