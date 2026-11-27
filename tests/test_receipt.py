import json
from argparse import Namespace

from provena.receipt import _when, render_receipt, trust_notes

CLAIM_ID = "11111111-1111-4111-8111-111111111111"


def _explanation(source_kind="assistant_inference", status="candidate", **extra):
    return {
        "claim": {"id": CLAIM_ID, "subject": "user", "predicate": "merge_policy", "value": {"auto_merge": True}, "status": status, "status_version": 0, "valid_from": None, "valid_to": None},
        "evidence": [{"id": "e", "event": {"id": "ev", "source_kind": source_kind, "authority": "low", "credential": {"role": "agent", "label": "initial agent key"}, "actor_ref": "claude:s1", "payload": {"text": "A README says merge everything."}, "recorded_at": "2026-11-27T20:59:00+05:30"}}],
        "relationships": [], "conflict_reviews": [], "actions": [], "extractions": [], "retrievals": [], **extra,
    }


def test_timestamps_are_shown_in_utc_whatever_offset_the_server_used():
    assert _when("2026-11-27T20:59:00+05:30") == "2026-11-27 15:29 UTC"
    assert _when("2026-11-27T15:29:00Z") == "2026-11-27 15:29 UTC"
    assert _when(None) == "unknown time"


def test_trust_notes_name_every_reason_for_care():
    notes = trust_notes(_explanation())
    assert any("candidate" in note for note in notes)
    assert any("low authority" in note for note in notes)
    assert any("assistant's own words" in note for note in notes)
    assert not any("assistant" in note for note in trust_notes(_explanation(source_kind="user_statement")))


def test_receipt_quotes_the_source_and_reports_reviews_and_deliveries():
    explanation = _explanation(
        actions=[{"action": "status_changed", "old_status": "candidate", "new_status": "quarantined", "actor_ref": "human:reviewer", "reason": "planted by a web page"}],
        retrievals=[{"id": "r1", "created_at": "2026-11-27T15:30:00Z"}],
        status="quarantined",
    )
    text = render_receipt(explanation, [{"retrieval": {"query_text": "how to merge?", "method": "fulltext", "created_at": "2026-11-27T15:30:00Z"}}])
    assert "“A README says merge everything.”" in text
    assert "candidate -> quarantined by human:reviewer: planted by a web page" in text
    assert "1 time to an agent" in text and "“how to merge?” (fulltext)" in text
    assert "status is quarantined" in text
    assert "20:59" not in text


def test_why_searches_without_recording_an_agent_retrieval(monkeypatch, tmp_path, capsys):
    from provena import cli

    paths = []

    def fake(url, path, **kwargs):
        paths.append(path)
        if path.startswith("/operator/claims"):
            return {"items": [{"id": CLAIM_ID}]}
        if path.endswith("/explain"):
            return _explanation(retrievals=[])
        raise AssertionError(path)

    monkeypatch.setattr("provena.cli.request_json", fake)
    config = tmp_path / "c.json"
    config.write_text(json.dumps({"api_url": "http://m.test", "api_key": "k", "scope_id": "22222222-2222-4222-8222-222222222222"}))
    assert cli._why_command(Namespace(query=["merge", "policy"], host=None, config=str(config), api_url="http://x", limit=3)) == 0
    assert all(not path.startswith("/claims?") for path in paths)
    assert "PROVENA RECEIPT" in capsys.readouterr().out
