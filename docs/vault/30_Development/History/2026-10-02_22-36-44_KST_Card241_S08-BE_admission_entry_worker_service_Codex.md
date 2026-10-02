---
doc_id: "HISTORY-CARD241-S08-BE-ADMISSION-WORKER-20261002"
title: "Card 241 S08-BE trusted admission entry and deployed worker service"
version: "1.1.1"
status: "review"
author: "Codex"
updated: "2026-10-02T23:54:08+09:00"
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

`ApprovalStore` now has the canonical internal build path: `request` validates the exact
`BuildRequest` and its ROOF canonical action, `challenge` and `decide` establish a
distinct human quorum, and `dispatch` records the admission in that same database
transaction. The supplied decision is not trusted: `TrustedBuildAdmissionEntry` locks
the dispatched approval, review snapshot, vote set, and dispatch receipt and requires
the snapshot digest, decision ID, policy version, requester, Run, recovery epoch, exact
request, and reconstructed `approvedBy` set to match before the 0060 insert. An absent,
merely approved, forged, or cross-tenant decision therefore records no admission.

The configured Control Plane still owns the internal entry in `app.state`, but the
product caller is now `ApprovalStore.dispatch`, not a hypothetical upstream planner.
No HTTP route, request schema, or CLI accepts `BuildRequest`, `BuildPlan`, or admission
documents; the route set is asserted identical with and without the internal entry.

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
runtime paths and are not copied into that volume. Operators must prepare `worker.json`
before starting the worker service. Flag enablement additionally requires a deployment
overlay that mounts those four runtime paths; the base Compose file deliberately does
not make an unmeasured builder reachable.

# v1.13 comparison and non-claims

| v1.13 measured gap | Card 241 result | Remaining boundary |
|---|---|---|
| admission store callers were tests only | approval request, distinct vote, decision and dispatch now call the internal admission entry in one transaction; the entry rebinds the decision to committed rows | no public build-admission route exists; physical builder enablement remains separate |
| production deployment had no worker service or worker config | private worker service and strict `worker.json` volume preparation exist | operator enablement and physical rootless builder acceptance remain separate |
| flag-off behavior needed preservation | admissions may remain durable and ready, while flag off produces zero intent/dispatch work | enabling remains an explicit runbook decision |

This change supplies the two code paths requested by Card 241. It does not by itself
claim a score change, S08-BE completion, an enabled production flag, or physical/LAN
BuildKit acceptance; those remain a separate measurement and rollout decision.

# Verification

Local verification used only focused PG-free files; no local PostgreSQL, Docker,
BuildKit, browser, or full suite was started.

| Check | Result |
|---|---|
| product-runtime + Core workflow focused set | 38 passed (19 + 15 deployment + 4 workflow; exact-head rerun pending) |
| `tests/core/test_server_config_volume.py` | 15 passed, 2 explicitly skipped because no pinned local image was supplied |
| `tests/core/test_deployment_credentials.py` | 15 passed |
| Python compilation of changed runtime/tool files | passed |
| `tools/check_docs.py` | passed |
| doc-path citation ratchet against the base | passed; no new broken citation |
| exact-head hosted real-PG | 12-case Core review lane required; local run is intentionally skipped without a disposable DSN |
| exact-head Backend/Core | pending after review-r1 remediation |

The first remediation Core run `37022207788` failed before the focused build
lane because `SELECT ... FOR SHARE` was added to immutable approval snapshot and
dispatch receipt tables. The runtime role intentionally has no `UPDATE` privilege on
those tables. The follow-up keeps the approval request row locked while reading the
append-only snapshot, votes, and receipt with ordinary `SELECT`; focused tests assert
that this least-privilege boundary is not widened. A new exact-head run is required.

# Review-r1 remediation boundary

The original head only stored `TrustedBuildAdmissionEntry` in `app.state`; no product
code called it, and direct recording accepted an uncommitted or forged decision. The
v1.1 path removes both gaps together. The real-PostgreSQL suite now starts at approval
request, issues and consumes a challenge, commits a distinct vote, dispatches, records
one admission and audit event, promotes to one intent, and dispatches once. Separate
negative cases require zero admission for a missing dispatch and for a foreign-tenant
plan, with the approval transaction rolled back. The hosted Core ratchet is raised from
10 to 12 non-skipped cases; exact-head hosted results are merge conditions.
