---
doc_id: "S08-BE-ACTIVATION-PLAN-AUTHORITY-001"
title: "S08-BE activation plan authority"
version: "1.1.0"
status: "implemented-review"
author: "Codex"
updated: "2026-10-03T10:15:54+09:00"
source_of_truth: "Git"
---

# S08-BE activation plan authority

This decision closes the three Medium prerequisites left by Card 247. It does not enable
`INV_BUILDKIT_PRODUCT_ENABLED`; the default remains `0`.

## Decision

1. A build budget is an immutable build-profile policy, not a literal and not a caller field.
   Migration `0063_build_policy_budgets` adds three all-or-none positive fields to
   `inv.build_policy_profiles`. Existing versions remain NULL and therefore cannot be used for
   product enqueue. A new version must fit the locked project CPU/RAM ceilings and storage quota.
2. A base image authority is measured from the exact clean source checkout. Every effective
   Dockerfile `FROM` must carry a literal lowercase `@sha256:<64 hex>` reference. Tags, ARG
   expansion, `scratch`, absent measurements, a dirty checkout, or a source SHA mismatch fail
   closed. The observed digests become `BuildPlan.resolvedBaseImageDigests`; request bytes are
   never hashed into a synthetic image identity. This intentionally rejects Dockerfile stage
   aliases (`FROM build`) and variable references even when a digest suffix is present
   (`FROM ${BASE}@sha256:...`); activation requires each `FROM` to repeat its external literal
   digest-pinned reference.
3. The API does not parse `worker.json`. Its `api.json.buildPlanAuthority` object has exactly eight
   non-secret planning fields and excludes worker TLS, output root and product receipt directory.
   The Control Plane service no longer receives `INV_WORKER_CONFIG`; only the worker service does.
   The API still performs the explicitly intended read-only builder health/source measurement.
   The current deployment compiler still places `worker.json` and its TLS files in the same
   read-only Docker volume mounted by both containers. Because both processes use uid 65532,
   absence of `INV_WORKER_CONFIG` is an application parsing boundary, not a confidentiality
   boundary. Product dispatch remains default-off; a later activation decision must either split
   API/worker volumes or explicitly accept this co-mount as part of the API container trust base.

**Card 262 implementation note:** the split alternative is now implemented. `api_config` remains at
`/run/saintvision`; a distinct `worker_config` is mounted only by the worker at
`/run/saintvision-worker`. Worker TLS references into the API root are rejected, and the flag
remains default-off. The historical paragraph above records why the split was required rather than
the current deployment boundary.

## Binding points

- `services/control-plane/src/inv/build_preparations.py`: profile budget rebind, project policy
  ceiling checks, measured base digest consumption, and the exact minimal config surface.
- `services/control-plane/src/inv/buildkit_transport.py`: clean source/tree and digest-pinned
  Dockerfile measurement.
- `services/control-plane/src/inv/app.py` and `docker-compose.prod.yml`: composition boundary.
- `tools/prepare_server_config.py`: deployment-time exact-key rejection without copying another
  secret file.

## Fail-closed acceptance

- Old profile or partial/zero budget: `RES-0006`, no admission.
- Budget above any locked project policy ceiling: `RES-0006`, no admission.
- Unpinned, variable, malformed, missing or unmeasured base: `VERIFY-0002`, no admission.
- Worker-only/private key in the API authority object: startup refuses the configuration.
- Product flag absent or not exactly `1`: the plan authority is not constructed and dispatch is
  still refused.

Physical builder acceptance remains `NOT_OBSERVED`; hosted real PostgreSQL proves the database and
product chain, while a physical builder remains a separate operational gate.
