# Restricted container output / denial / lease-reclaim evidence (S03-DB)

- collected_at: 2026-09-22T14:39:39+00:00 · git HEAD `fd1ae8ba` · collector sha256 `5ac7a2b00b3410078b918da5f81ef429993d700e194c7b4cd97d4eec6d7015d7` · uncommitted: ['tools/collect_container_evidence.py']
- verdict: **UNMEASURED** (C1..C4 on the DB lane, P1..P4 on the container lane; a lane with nothing to judge makes the verdict UNMEASURED, never PASS)
- unmeasured: db lane observed 0 runs: output/hash/lease facts unmeasured
- rerun: `INV_AUDIT_DSN=<owner dsn> python tools/collect_container_evidence.py --container-image <image> --out-dir <dir>` (DSN never recorded)
- condition: Windows host: the Linux private Node provider that produces real runs does not execute here, so the DB lane observes an empty disposable ledger (synthetic ledger is exercised by the self-test); container lane probes the local python:3.12-slim image (a probe image, not the product node image)

## DB lane

database `inv_s03_fe940d4bcea74e1bb495a655fc5b6fde` · PostgreSQL 16.15 · migration head `0046_model_manifest_readiness` · tenant filter all

counts: runs 0, leases 0, tool_claims 0, deliveries 0, stop_receipts 0, commitments 0, completions 0, evidence 0, storage_objects 0

**no runs observed on this database** — output/hash/lease facts are unmeasured here (the Linux private Node provider that produces runs does not execute on this host).

denials observed: delivery error codes none · ingestion errors none · approval audit phases none

## Container lane

image `python:3.12-slim` (`sha256:9e87977b8678`) · docker server 20.10.22 · plan {"network": "none", "rootfsReadOnly": true, "capDropAll": true, "noNewPrivileges": true, "userId": 65532, "pidsLimit": 64}

| probe | exit | stdout (bytes, sha256, head) | stderr (bytes, sha256, head) | expectation |
|---|---|---|---|---|
| P1 output-capture | 0 | 13, `5ea0daed9fc3…`, 'probe-stdout' | 13, `043ddd6263a2…`, 'probe-stderr' | exit 0, stdout 'probe-stdout\n', stderr 'probe-stderr\n' |
| P2 rootfs-write-denied | 2 | 0, `e3b0c44298fc…`, '' | 59, `b695fb68e373…`, 'sh: 1: cannot create /etc/inv-probe: Read-only file system' | non-zero exit, stderr mentions read-only |
| P3 network-namespace-isolated | 0 | 68, `cd78d368b757…`, '{"ifaces": ["lo"], "routes": [], "external_connect": "ENETUNREACH"}' | 0, `e3b0c44298fc…`, '' | ifaces == ['lo'], routes == [], external connect ENETUNREACH (loopback refusal is not evidence) |
| P4 uid-and-capabilities | 0 | 31, `459b483188da…`, '65532\nCapEff:\t0000000000000000' | 0, `e3b0c44298fc…`, '' | uid 65532, CapEff 0000000000000000 |
| control (network=bridge) | 0 | {"ifaces": ["eth0", "lo"], "routes": ["eth0", "eth0"], "external_connect": "TimeoutError"} | - | isolated=False — isolation removed on purpose; must NOT look isolated |
