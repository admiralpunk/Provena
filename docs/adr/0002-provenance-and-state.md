# ADR 0002: Separate immutable events from claims

Status: Accepted

Events represent source material. Claims represent structured propositions. Evidence links connect them. Event and evidence rows cannot be changed or removed; claim proposition columns cannot change. Claim status may change only with an append-only action carrying the next status version in the same transaction. The version prevents reuse of an old action to justify a later transition. Supersession creates a relationship and preserves both claims.
