---
doc_id: "REPORT-FLEET5-RECOVERY-INTEGRATION-RESUME-20261118"
title: "Fleet5 recovery integration readiness resume"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-18T21:07:45+09:00"
source_of_truth: "Git"
---

# Candidate hardening and read-only preflight

Task FLEET5-EXPIRED-POLICY-INTEGRATION-HARDENING-AND-READONLY-PREFLIGHT-R1 began on d47630d730278aa9e49b15a63cd221696da8dc00. Codex owns implementation. Claude review and operating acceptance are pending. Root544 records the expired CA. Real authority replacement and release require a separate reviewed contract.

The independently provisioned public role binding is a fixture image input. Its verification binds three Node certificate fingerprints and both recovery roles to the same tenant and epoch. Unknown history stays on HOLD. The proposed v2 proof, checkpoint and record carry both role hashes. The existing authorization, operator and acknowledgement domains retain their definitions. Archived v1 checkpoints remain evidence. A v2 helper refuses them before allocation. The candidate retains the safe-integer filesystem metadata limit and refuses out-of-range unsigned values before conversion.

The local workspace uses Git, document checks and source metadata only. Hosted proof and the post-CI receipt are pending. Root retains custody of live inputs.

## Read-only operator procedure

Root verifies the source SHA and artifact integrity on each authorized host. Root supplies a descriptor with schema `sv-readonly-cohort:1`, the verified sourceSHA, canonical tenant and epoch UUIDs, project ID, exact three Node IDs, expected caDER and cpDER SHA-256, ownerLabel and ownerValue, trusted databaseRole and maxAgeSeconds (1 through 300). Each Node entry contains a full cid, image SHA-256 without prefix, absolute config and state bind paths, and the expected public argv array. Transport, source provenance, the selected database and descriptor authenticity remain operator responsibilities.

Run `python -B tools/recovery_preflight/node.py` locally on each authorized Linux host with a JSON object containing descriptor and node on standard input. Use the pinned local Docker daemon and existing access. The collector inspects only the named CID. Private key and lock observations use metadata-only file descriptors. A serving Node may continue running. No journal lock or quiescent observation is obtained.

On PC3 run `python -B tools/recovery_preflight/cp.py` with descriptor and a private connection string on standard input. Use a previously authorized login with tenant context established on connection and reviewed visibility into schema revision, scope, memberships, channels, channel audit, resources and outstanding work. An inaccessible revision, unrecognized tenant policy, hidden membership or unknown epoch yields HOLD. Database connection material stays out of argv and evidence.

Supply descriptor and the four public observations to `python -B tools/recovery_preflight/join.py` via standard input. Exit zero indicates all observation sources were present and matched. Inspect holds even after exit zero. CA_TERMINAL requires separately reviewed authority replacement. Policy expiry, expired leaves, unknown custody and outstanding work retain independent dispositions. The snapshots do not authenticate normal M2, establish no-serving status, authorize business approvals or allocate counters. Unknown operation outcomes require forward reconciliation. Expired PREPARED retains its original signed operation and counter. Full P5 publication and the five-instance barrier remain pending.

## Hosted fixture checkpoints

The initial Core build caught two existing history-test calls that still passed paths after the directory-handle change. Run 44302282769 preserves the compiler diagnostics at source 85f10188fe2e226787a0be3d01757057a1ae9b60. The corrected Docker and cryptographic fixture on source 4baf857c084bc066b64ee0f2fa8125b02ebae04e completed both cycles and all 52 negative controls, including the original 37. All three public collector observations measured zero changed files. Later source changes require their own exact-SHA results.

The candidate requires Linux amd64 or arm64 with openat2 and a custody filesystem supporting unnamed temporary files. No-cross-mount access protects the fixture image authority anchor. Node collection also checks the live kernel bind source against the held host directory on both sides of each observation. An unsupported host or mismatched mount returns HOLD. The production role anchor, authoritative prepared-operation adapter, publication, barrier and budget remain pending.

The following receipt directory contains separate post-CI source, board and history addenda. Root may reconcile the reviewed evidence after both dispatched workers release. No full-vault export occurred.
