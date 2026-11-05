---
doc_id: "EVIDENCE-FLEET5-20261105-WORKER-READINESS-ERRORS-CODEX"
title: "FLEET5 read-only measured failures and collector corrections"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-05T14:52:00+09:00"
source_of_truth: "Git"
---

# Measured failures remain failures

Task FLEET5-20261105-WORKER-READINESS / task_4cfe9dbaa805. These outcomes do not change the actual read-only delivery scope or turn missing operational evidence into success.

| Failure | Observed exit and scope | Correction / remaining action |
|---|---|---|
| Worker3 ordinary Docker version |1 at14:44:30KST; successful SSH0 | Later authorized diagnosis: daemon active, current user's socket permission denied; serverAPI remains unmeasured |
| Worker3 `sudo -n` Docker version |1 at14:50:34KST; interactive-authentication-required markers | No password/retry; operator chooses reviewed runtime route, no blanket human-account grant |
| Worker3 user Docker service query |4/inactive at14:47:51KST | Separate from active system daemon0; rootless runtime support not claimed |
| Current inventory lint |1/BLOCKED,74 missing fields,0 invalid,5 slots | Keep blanks; reconcile worker4/CP and policy/certificate/profile inputs |
| System Python inventory-lint import |1: Python3.10 lacks StrEnum | Supported existing Python3.14.7 re-executed the inventory lint and returned real BLOCKED1; no protected environment install |
| Initial UTF-8 documentation reads |1 for Python piped non-ASCII paths; later one stdout encoding exception | Set PowerShell OutputEncoding and PYTHONIOENCODING=utf-8; reread required current sections correctly; no repository source changed |
| Overbroad private source discovery |30s bounded subprocess timeout; local discovery only, no SSH | Narrowed to existing project inventory/state and top-level historical coordinator message; exact worker3 mapping recovered, no account guesses |
| Initial process-result projection |1 TypeError because a one-row PowerShell JSON result was an object | Normalize object to one-element list; readback confirmed tunnel15408 and absent previous helper PIDs; no process action |

Raw stderr and receipts remain ignored under `.work/fleet5-readiness`; only safe classifications/digests are published. The measurements, Linux procedure and exact next owners are in [[2026-11-05_FLEET5_worker_readiness_Codex]].
