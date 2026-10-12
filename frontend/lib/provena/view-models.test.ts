import assert from "node:assert/strict";
import test from "node:test";

import { claimRow, formatDate, payloadText } from "./view-models";
import type { OperatorClaim } from "./types";

const baseClaim: OperatorClaim = {
  id: "claim-1",
  scope_id: "scope-1",
  subject: "profile",
  predicate: "theme",
  value: { color: "blue" },
  status: "verified",
  status_version: 1,
  valid_from: null,
  valid_to: null,
  recorded_at: "2026-02-03T04:05:06Z",
  statement: "The preferred theme is blue.",
  authority: "high",
  confidence: 0.876,
  sources: [],
  evidence_count: 0,
  extraction: null,
  relationships: [],
  risk_flags: [],
  risk_assessment: "not_recorded",
};

test("claimRow maps claim fields and confidence", () => {
  assert.deepEqual(claimRow(baseClaim), {
    id: "claim-1",
    title: "profile.theme",
    subject: "profile",
    predicate: "theme",
    value: JSON.stringify({ color: "blue" }),
    status: "verified",
    authority: "High",
    confidence: 88,
    relevance: null,
    note: undefined,
  });
});

test("claimRow represents missing authority and confidence", () => {
  assert.deepEqual(
    claimRow({ ...baseClaim, authority: null, confidence: null }),
    {
      id: "claim-1",
      title: "profile.theme",
      subject: "profile",
      predicate: "theme",
      value: JSON.stringify({ color: "blue" }),
      status: "verified",
      authority: "Unavailable",
      confidence: null,
      relevance: null,
      note: undefined,
    },
  );
});

for (const kind of ["related_to", "contradicts"] as const) {
  test(`claimRow marks ${kind} relationships as conflicts`, () => {
    const row = claimRow({
      ...baseClaim,
      relationships: [{
        id: "relationship-1",
        kind,
        from_claim_id: "claim-1",
        to_claim_id: "claim-2",
        reason: "The claims disagree.",
      }],
    });

    assert.equal(row.note, "Conflict recorded");
  });
}

test("claimRow leaves the conflict note unset for other relationships", () => {
  const row = claimRow({
    ...baseClaim,
    relationships: [{
      id: "relationship-1",
      kind: "supports",
      from_claim_id: "claim-1",
      to_claim_id: "claim-2",
      reason: "The claims agree.",
    }],
  });

  assert.equal(row.note, undefined);
});

test("payloadText returns text payloads directly", () => {
  assert.equal(payloadText({ text: "A plain message" }), "A plain message");
});

test("payloadText serializes non-text payloads", () => {
  assert.equal(payloadText({ text: 42, source: "manual" }), JSON.stringify({ text: 42, source: "manual" }));
});

test("formatDate marks missing values unavailable", () => {
  assert.equal(formatDate(null), "Unavailable");
  assert.equal(formatDate(undefined), "Unavailable");
});

test("formatDate formats dates in UTC", () => {
  assert.equal(formatDate("2026-02-03T04:05:06-05:00"), "Feb 3, 2026, 9:05:06 AM");
});
