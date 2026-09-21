# ADR 0008: Review possible conflicts without erasing evidence

Status: Accepted

An overlapping different value produces an immutable `related_to` relationship as a possible-conflict case. A human reviewer records one resolution: `contradiction`, `temporal_change`, or `dismissed`, with a reason and credential ID. Contradiction adds a `contradicts` relationship. Temporal change requires the reviewer to identify explicitly which of the two claims supersedes the other; recording order is not fact-validity order. The original case and both claims remain. Claim statuses change only through the separate audited status endpoint, so a review decision cannot silently promote or delete a memory.

Unreviewed possible conflicts can be listed by scope with both propositions and validity intervals. Resolutions are append-only; correcting a mistaken resolution requires a new explicit workflow and ADR rather than overwriting history. Preexisting temporal reviews made before the direction field was introduced retain a null direction; their existing `supersedes` relationship remains the historical record.
