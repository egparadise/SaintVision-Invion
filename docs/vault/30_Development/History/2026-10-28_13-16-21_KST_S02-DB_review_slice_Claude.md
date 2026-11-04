---
doc_id: "HIST-20261028-S02-DB-REVIEW-SLICE-CLAUDE"
title: "S02-DB User/Node/Capability/Snapshot review slice"
version: "1.0.0"
status: "review"
author: "Claude"
created: "2026-10-28T13:16:21+09:00"
updated: "2026-10-28T13:16:21+09:00"
source_of_truth: "Git"
---

# S02-DB User/Node/Capability/Snapshot review slice

## Verdict and boundary

The reviewed exact source has **no corrective product finding** in this slice. User, Node,
Capability, and Snapshot migration/model/contract boundaries remain coherent. The specified
dependency-complete Node output/chunk test selection is **not run / environment blocked**, not
PASS: both Claude and the coordinator had Python 3.12 while the repository venv contains CPython
3.14 `rpds`/`psycopg` wheels. The coordinator's temporary official dependency installation could
not complete within the DNS/retry and execution limits.

This is a Claude owner-side re-review, not the registry's independent Codex review and not
operational acceptance. `S02-DB` remains `review`. It must not be promoted: `S01-BE` and `S01-ST`
are still `in_progress`, and the S02 lane chain is not done. The existing 75% classification
therefore remains a software-evidence milestone, not task completion. No registry, common progress
board, VF-CL registry, or product code was changed.

## Meaning review

- `users` binds the IdP subject to a tenant and provides tenant-qualified unique/FK targets. RLS
  is enabled and forced through the baseline migration's tenant-scoped installation loop.
- `nodes` has tenant-qualified hostname/node identity, bounded status and heartbeat sequence, and
  a partial unique certificate fingerprint that permits multiple pre-certificate enrollments.
- `node_capabilities` binds `(tenant_id,node_id)` to the owning node, prevents duplicate
  whole-host/GPU resources, constrains GPU device indexes, and after migration 0010 makes unit a
  property of kind (`millicores`, `bytes`, or `devices`). Offers and snapshots no longer repeat a
  unit that could disagree.
- `resource_snapshots` is range-partitioned, tenant-policed, and after migration 0010 has a
  composite FK to the exact `(tenant,node,capability)` triple. The service repeats the ownership
  check before insert, converts observations to canonical integral units, and uses server time.
- Enrollment and detail contracts agree with the API models for Node and Capability shape. The
  core schema's canonical copy is byte-identical in the control plane and Node agent
  (`sha256 475cc4b261f9cf153d1a4e59bed05a4b5ddeeb54bdcfbc7562358504197539fc`).
- `NodeChunkInput`/`NodeChunkResult` bind object digest, size, offset, and nonce. Runtime validation
  rejects replayed scope, invalid range, non-exact length, digest mismatch, non-canonical base64,
  and encoded input beyond the 256-KiB chunk ceiling.
- `NodeOutput` binds decoded bytes to declared size and SHA-256; ingestion also rejects duplicate
  JSON keys, unknown artifact fields, truncated output, invalid base64, and decoded stdout/stderr
  above 64 KiB.
- `inv.node_resource_snapshots` separately binds the kernel snapshot to `(tenant_id,node_id)` and
  has `ENABLE` plus `FORCE ROW LEVEL SECURITY`. This supporting kernel table does not substitute
  for S02 physical-node acceptance evidence.

## Verification

| Check | Result |
|---|---|
| Unchanged `tests/core/test_node_output.py` + `tests/core/test_node_chunk.py`, dependency-complete environment | **not run / environment blocked**. Direct collection exit 2 from CPython 3.12/3.14 compiled-wheel mismatch; coordinator dependency bootstrap did not complete. |
| Same two unchanged test bodies with only compiled import-time dependencies replaced by a temporary semantic harness | **22 passed**, exit 0. Supporting evidence only, not the authoritative focused suite. |
| Unchanged `tests/test_units.py` in an isolated temporary pytest root | **10 passed**, exit 0. |
| Canonical/core generated schema hashes | control-plane and Node-agent copies both exactly equal the canonical schema, exit 0. |
| Existing exact-head hosted Core lane | success at the same coordinator-observed checkout. This is suite-level CI evidence; it is not reported as a separately observed focused selection. |

The temporary harness replaced `jsonschema` contract loading with the exact relevant
`NodeChunkInput`/`NodeChunkResult` key, type, pattern, range, and `maxLength` checks, and replaced
unused database collaborators so the reviewed product functions could import. It does not prove
that the real dependency graph collected or ran, so the official focused result remains blocked.

## Reviewed source pins

- `0001_s02_baseline.py`: `3dd001ecf90a527c0b7366e6ca92e1532c68d2ef7786fc53bc2a30305aad3d30`
- `0010_canonical_resource_units.py`: `fe15d1e0d7204be770802e6106891a816222c8544494da4eae7d7c4f6d1470d5`
- `identity.py`: `698f1f02be02d407f8d02369782f5750daa3e40da1b45daa6a2777c16b28399d`
- `resource.py`: `0cc3432de2d22af8ee5c8916163d645c175293d5734dcfdf801db8f6c7314466`
- `nodes.py`: `bc4114596d7c399e73e1c126fec223be59813b5af422b848fac42b8dc42308b0`
- `node_chunk.py`: `9741d2540da6b8a098b9839290869d2ce537563f593e81bdd6ca039f05ecd4ae`
- `output_ingestion.py`: `e954e1ef8dcae97756a50428af66c9a328e4d362f1aee7d630588431d09b1308`
- `test_node_output.py`: `287d8ec0732a604130b12e120d2212d09826d12ba49101aac234d7b6bff740cd`
- `test_node_chunk.py`: `32cb6f068544dabd8839bd52f8ff275746ea4ece1c91b7a4223b4cef7353980e`

## Remaining evidence and handoff

1. Run the two focused tests in a supported dependency-complete CPython environment; do not infer
   their result solely from the semantic harness or broad hosted lane.
2. Finish and independently review `S01-BE`/`S01-ST` and the remaining S02 lane chain.
3. Produce live IdP/CA/DNS and five physical Node registration, capability, heartbeat/snapshot,
   cross-tenant denial, browser journey, and operational-acceptance evidence. Existing disposable
   PostgreSQL and hosted CI evidence is not that operational proof.
4. Codex remains the independent reviewer for `S02-DB`; Claude must not self-close it.
