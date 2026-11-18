---
doc_id: "HIST-FLEET5-A1-CEREMONY-INSPECT"
title: "Synthetic A1 ceremony inspection"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-19T07:23:40+09:00"
source_of_truth: "Git"
---

Codex task_725811f0bfaf on review base cfbd678c, agent/codex/fleet5-runtime-a1-986a845b. Synthetic ceremony classification and exact replay inspection. Claude independent review pending.

Starting boards INDEX-PROGRESS-001 v1.0.554 and WORKBOARD-CODEX-001 v1.0.511. Review cfbd678c preserves findings against bdf737d8.

An explicit stable synthetic custody observation represents zero keys. A missing ledger yields absent evidence. A key and a subset of planned leaves yield a partial log. Any positive evidence contradicting a zero attestation holds the epoch indefinitely. A caller that loses an acknowledgement must replay the identical event ID, subject and fingerprint. An early planned leaf can be reconciled by replaying that tuple after the planned key commits. Inspection lists both the original refusal and the match. Legacy conflicts without ordering provenance stay unresolved.

Storage errors map to DB readback required and stale ownership to writer fence. Within a fenced snapshot, a zero contradiction or CA conflict takes custody precedence, then a foreign leaf, then duplicate leaf evidence. Other unresolved or coherent snapshots stay on custody HOLD. Strict legacy readback still rejects all refused observations, including an inspector-reconciled early leaf. All observations remain synthetic and scoped to the local fence. Root owns signer custody and integration. Claude should independently replay the restart, contradictory evidence and fencing cases.

Gate command results are in the scoped Evidence directory fleet5-a1-ceremony-inspect. Hosted CI and independent acceptance are recorded separately.
