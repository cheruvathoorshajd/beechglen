---
inclusion: always
---

# Product: Nexus911

Nexus911 is a 5-hour hackathon prototype: a claim-weighted knowledge graph for 911 that links duplicate calls into incidents, weighs conflicting witness accounts, and prioritizes calls by new information, with a Massachusetts focus.

Users: 911 call-takers (operator console), supervisors (queue and metrics), police officers (briefing, dispatch package, leads).

Non-negotiable principles:
- No call is ever dropped or hidden. The system only reorders and annotates the queue.
- AI suggests, humans decide. Operators can confirm or split any link, and every decision is written to the audit log.
- Fail-open. LLM or network failures never block a call from entering the graph.
- Minority accounts stay visible: always return every value with its share.
- Caller-role credibility changes claim weight only, never call priority.
- Synthetic data only. No real 911 data or phone numbers.

README.md at the repo root is the source of truth for features, formulas, defaults, field names, endpoints and demo outcomes. Follow it exactly. Do not invent endpoints, fields, parameters or features that are not in README.md.
