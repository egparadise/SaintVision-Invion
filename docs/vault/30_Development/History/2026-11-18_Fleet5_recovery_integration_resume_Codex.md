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
