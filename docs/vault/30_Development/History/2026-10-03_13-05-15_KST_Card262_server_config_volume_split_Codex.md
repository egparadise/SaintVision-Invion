---
doc_id: "HISTORY-CARD262-SERVER-CONFIG-VOLUME-SPLIT-CODEX-001"
title: "Card 262 server configuration volume split"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-03T13:05:15+09:00"
source_of_truth: "Git"
---

# Card 262 server configuration volume split

## Selection and base

Card 255 left one explicit S08 activation residual: removing `INV_WORKER_CONFIG` from the API
parser did not prevent a compromised API container from reading `worker.json` and its Node TLS
private key because API and worker mounted the same volume. Card 262 starts from train 38 candidate
`ce63a5e8136742389e8148adc64d466df0f7af77` and removes that shared OS trust boundary. There is no
migration and `INV_BUILDKIT_PRODUCT_ENABLED` remains default off.

## Boundary

- `api_config` is the existing `INV_CONFIG_VOLUME`, mounted read-only at `/run/saintvision` by the
  control-plane and worker. It contains `api.json` and only files referenced by API configuration.
- `worker_config` is a new required `INV_WORKER_CONFIG_VOLUME`, mounted read-only at
  `/run/saintvision-worker` by the worker only. It contains `worker.json` and only its flat Node TLS
  references. A worker TLS reference into `/run/saintvision` is rejected.
- `tools/prepare_server_config.py` creates and validates the two new volumes under one ownership
  label. It refuses an existing volume, refuses equal API/worker volume names, and cleans up only
  volumes created by the failing invocation. Receipts expose counts and volume names but no file
  digest or secret value.
- The worker still reads API configuration for the product ObjectStore, but the inverse is not
  true: the API service has no worker volume mount and no worker config environment variable.

## Verification

- `python -m pytest -q tests/core/test_server_config_volume.py -m "not postgres"`:
  **26 passed, 3 explicit candidate-image skips**, exit 0. The opt-in candidate-image case mounts
  the two real volumes into separate container namespaces and asserts that the API namespace has
  neither `worker.json` nor the worker TLS key.
- `python -m pytest -q tests/core/test_deployment_credentials.py`:
  **17 passed**, exit 0. This includes rendered `docker compose config --format json` checks for
  the split external volume names, read-only mounts, API exclusion, and unchanged default-off flag.
- `python -m pytest -q tests/core/test_vf_deployment.py`: **3 passed**, exit 0.
- `python tools/check_docs.py`, `python tools/check_ontology.py`, and
  `python tools/check_doc_single_source.py --ratchet`: exit 0. Obsidian sync check reported no
  conflicts and made no writes.
- The local path-citation ratchet did not produce a valid clean-checkout result: ignored frontend
  build-output and dependency directories made five historical baseline citations appear newly
  repaired. The baseline was not widened or edited; clean hosted Docs remains the citation gate.
- Hosted candidate-image execution and the exact-head Backend/Core result remain review gates; this
  document does not treat the locally skipped container case as measured success.

## Operational effect

Operators prepare two new volume names in one command and set both `INV_CONFIG_VOLUME` and
`INV_WORKER_CONFIG_VOLUME`. Existing volumes are never modified. The canonical S08 activation
runbook and user checklist now treat the shared-volume residual as closed, while physical rootless
builder acceptance remains external and NOT_OBSERVED.
