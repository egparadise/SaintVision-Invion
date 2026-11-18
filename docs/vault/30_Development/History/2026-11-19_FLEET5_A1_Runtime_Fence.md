---
doc_id: "HISTORY-FLEET5-A1-RUNTIME-FENCE"
title: "Interrupted A1 runtime fence prerequisite"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-19T03:18:00+09:00"
source_of_truth: "Git"
---

## Disposition and ownership

Codex, task_09ed06df2d02, branch agent/codex/fleet5-runtime-a1-986a845b, base 986a845b. Start 2026-11-19 03:17 KST. Input boards INDEX-PROGRESS-001 1.0.545 and WORKBOARD-CODEX-001 1.0.506. The independent review accepted proposed R2 v1.2.0 at 37660421. Its hosted CI receipts apply only to that candidate. [[2026-11-19_FLEET5_376604_Independent_Review]]

## Recovery path and implementation boundary

In tools/lan_pilot.py the partial and fully expired leaf recovery preparation functions validate the existing batch. Stage and commit update channels and shared leaf material. The worker install, finalize and rollback commands in deploy/lan/worker_leaf_rotation.py handle leaf bundles. These paths supply neither replacement-CA ceremony evidence nor a shared monotonic A1 fence governing every signer. Reusing the leaf journal or its host file lock would leave a second writer unconstrained.

The pilot CLI now exposes inspect-interrupted-a1. It opens an existing private local SQLite fence ledger read-only and always exits blocked. Missing, corrupt or mismatched ownership yields HOLD_WRITER_FENCE. Matching ownership yields HOLD_CUSTODY_UNRESOLVED. The local prerequisite serializes competing ownership transfers and persists generation changes. Provisioning and transfers have no pilot commands.

## Handoff

Activation stays off. Independent reviewer requested: Claude via coordinator. Review stale writers, concurrent transfer and the CLI HOLD exit. Root must establish one authoritative fencing domain across signers, enforce generation at the mutation commit, and integrate durable custody, ceremony log, DB epoch and the R2 output inventory before enabling recovery. Restoring a copied ledger can rewind its generation. A local ledger cannot establish fleet exclusivity. No fleet, signing, deployment, external publication or shared vault export.

## Verification

Windows, repository Python 3.14.7 environment, disposable fixtures. All ten commands in Evidence/fleet5-a1-runtime-fence/local-gates.json exited zero. Pytest passed 498 cases including the real CLI subprocess and competing local writers. R2 matched 113 expected verdicts. Obsidian check reported zero conflicts. The first CLI test used Python 3.10 and failed importing the existing StrEnum dependency, then passed on 3.14. This branch has no hosted CI or independent implementation review. Coordinator retains publication and handoff.

The fully expired preparation path calls _load_external_ca, enforces current root and intermediate validity, and compares the chain digest with the stored pilot pin. It cannot serve as a new-authority executor. Inspection consumes an expected writer identity supplied by the caller solely to select a HOLD reason.
