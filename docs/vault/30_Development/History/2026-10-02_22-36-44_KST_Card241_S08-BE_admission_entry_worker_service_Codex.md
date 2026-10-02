---
doc_id: "HISTORY-CARD241-S08-BE-ADMISSION-WORKER-20261002"
title: "Card 241 S08-BE trusted admission entry and deployed worker service"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-02T22:36:44+09:00"
source_of_truth: "Git"
base_sha: "a2d64b6193913a56448a0ef495d1b7b374de2a54"
reviewer: "Claude"
---

# Selection and scope

Card 241 is the next external-prerequisite-free S08-BE item measured by the v1.13
rescore. Migration 0060 and the product loop existed, but
`BuildExecutionAdmissionStore.record(...)` had no configured internal ingress, and the
production Compose definition had no worker process or `INV_WORKER_CONFIG`. The base is
the train 26 candidate `a2d64b61`; no migration is added.

# Trusted internal admission entry

`TrustedBuildAdmissionEntry.record_committed(...)` accepts only the exact committed
`BuildRequest`, `BuildPlan`, `PolicyDecision`, policy version, Run ID, Evidence ID, and
authenticated `Principal`. It delegates to the existing 0060 authority checks; it never
synthesizes a caller, document, Run, lease, decision, or Evidence identity. The
production Control Plane factory installs this object in `app.state` for an in-process
policy/planning caller. No HTTP route, request schema, or CLI exposes it.

The first successful 0060 insert and the redacted
`inv.build.admission_recorded` outbox event now commit in the same transaction. Exact
replay returns the same row and emits no second audit event. Permission, policy, live
Run/Node/resource/lease authority, FORCE RLS, immutable payload, promotion, and one-shot
dispatch remain the existing database-owned boundaries.

# Worker deployment and private configuration

`docker-compose.prod.yml` now contains a private `worker` service using the backend
image and `python -m inv.worker`. It publishes no port, uses the existing non-owner
runtime DSN and private `server_config` volume, waits for PostgreSQL health, and reads
`/run/saintvision/worker.json`. `INV_BUILDKIT_PRODUCT_ENABLED` defaults to `0`; at zero,
the delivery worker continues but no BuildKit runtime is constructed, promoted, claimed,
or dispatched.

`tools/prepare_server_config.py` optionally collects a strict `worker.json` plus only
its flat `/run/saintvision/` TLS references. The Node private key is classified private,
unreferenced files remain excluded, duplicate/unknown/missing keys and path aliases are
rejected, and the image-side verification constructs the strict worker configuration
and `NodeTLSClient` before a prepared volume is accepted. This is the concrete
`worker.json` boundary anticipated by the deployment runbook in PR #335.

The required document is:

```json
{
  "tenantId": "<canonical tenant UUID>",
  "tls": {
    "ca_file": "/run/saintvision/node-ca.pem",
    "certificate_file": "/run/saintvision/worker.pem",
    "key_file": "/run/saintvision/worker.key",
    "timeout": 40
  },
  "outputRoot": "/optional/legacy/output/root",
  "buildExecution": {
    "buildctlPath": "/usr/bin/buildctl",
    "address": "unix:///run/user/65532/buildkit/buildkitd.sock",
    "sourceRoot": "/workspaces",
    "referenceHealthReceipt": "/run/saintvision/buildkit-health.json",
    "productReceiptDirectory": "/var/lib/saintvision/build-receipts",
    "builderInstanceId": "<measured builder instance>",
    "builderProfileId": "buildkit-rootless-v1",
    "providerRecoveryEpoch": 7,
    "nodeId": "<leased node ID>"
  }
}
```

`outputRoot` is optional and mutually constrained by the existing canonical object-store
configuration. `buildExecution` is optional while the product flag is off and required
when it is exactly `1`. TLS paths are flat files in the prepared private volume; the
BuildKit socket, workspace root, health receipt, and product receipt directory are
runtime paths and are not copied into that volume.

# v1.13 comparison and non-claims

| v1.13 measured gap | Card 241 result | Remaining boundary |
|---|---|---|
| admission store callers were tests only | configured Control Plane owns an internal-only exact-document entry; real-PG uses that entry | the upstream policy/planner remains responsible for producing already committed exact documents |
| production deployment had no worker service or worker config | private worker service and strict `worker.json` volume preparation exist | operator enablement and physical rootless builder acceptance remain separate |
| flag-off behavior needed preservation | admissions may remain durable and ready, while flag off produces zero intent/dispatch work | enabling remains an explicit runbook decision |

This change supplies the two code paths requested by Card 241 and can be considered by
the next score owner. It does not claim S08-BE completion, an enabled production flag,
or physical/LAN BuildKit acceptance.

# Verification

Local verification used only focused PG-free files; no local PostgreSQL, Docker,
BuildKit, browser, or full suite was started.

| Check | Result |
|---|---|
| product-runtime + Core workflow focused set | 23 passed (19 + 4) |
| `tests/core/test_server_config_volume.py` | 15 passed, 2 explicitly skipped because no pinned local image was supplied |
| `tests/core/test_deployment_credentials.py` | 15 passed |
| Python compilation of changed runtime/tool files | passed |
| `tools/check_docs.py` | passed |
| doc-path citation ratchet against the base | passed; no new broken citation |
| exact-head hosted real-PG | pending Core review lane |
| exact-head Backend/Core | pending |
