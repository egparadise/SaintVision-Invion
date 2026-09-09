# Architecture baseline

Experience (React SPA / Monaco / xterm) → API and identity → FastAPI Control Plane → Go Node Agent / isolated Runtime. TypeScript Agent Gateway connects provider adapters. PostgreSQL owns durable state; S3-compatible storage owns binary objects; NATS delivers at least once; Redis caches ephemeral state. OPA governs execution and OTel/Alloy observes it.

Reverse-Ontology links final outcomes to acceptance evidence, contracts, entities, tasks and responsible agents. See docs/vault/50_Ontology/Reverse-Ontology 최종 설계.md via the main guide for authoritative links.

The source documents are archived in docs/sources. Current decisions are in docs/vault/40_Governance/설계 충돌 정정 및 ADR.md. Product code is not implemented by this documentation baseline.
