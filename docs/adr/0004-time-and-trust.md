# ADR 0004: Separate fact time, system time, and authority

Status: Accepted

PostgreSQL records when information entered the system. Optional validity endpoints represent when the proposition applies. The API never derives one from the other. The server assigns authority from source class and authenticated caller capability. A Phase 1 tenant key cannot prove a human spoke, even when an event is labeled `user_statement`; such reports have low authority. Medium or high authority waits for authenticated user or trusted integration identities. Relevance and permission to act are independent of source authority.
