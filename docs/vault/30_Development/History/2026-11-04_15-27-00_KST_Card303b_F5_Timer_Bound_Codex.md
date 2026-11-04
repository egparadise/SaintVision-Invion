---
doc_id: "HIST-20261104-CARD303B-F5-TIMER-CODEX"
title: "Card 303b F5 stale 관측 타이머 종료와 지연 상한"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-11-04T15:27:00+09:00"
updated: "2026-11-04T15:27:00+09:00"
source_of_truth: "Git"
---

# Card 303b F5 stale 관측 타이머 종료와 지연 상한

- Task `task_8010a604e690`, dispatch `ctx_7bbe143f2c3d`, owner Codex, reviewer Claude pending for this successor. Coordinator reports Claude independently source-accepted base `deef98ad67c90549ce64563d442ac916d9c6c8e9`; that verdict is not a review of this follow-up.
- Existing owned PR #406 / branch `agent/gemini/c303b-frontend-evidence`, checkout `D:/Project/SaintVisionI-Invion/supervision-gemini-20261104`, clean base above, KST start observation `2026-11-04T15:24:54+09:00`. Final exact corrected SHA and push result are sent in the worker delivery receipt. Read progress `INDEX-PROGRESS-001` v1.0.380 and own board `WORKBOARD-CODEX-001` v1.0.342; earlier loaded agent-delivery/core-reliability/frontend-delivery skills and governance remain applicable. Shared boards and unrelated root changes are outside this dispatch.
- Prior implementation and Gemini attribution: [[2026-11-04_15-14-00_KST_Card303b_F5_Certificate_Freshness_Codex]].

`nextNodeCertificateTransition` now returns null once `now > observedAt + 60000`. The inclusive `age == 60000` still schedules the `+60001` transition. App caps any scheduled delay at `2147483647` milliseconds. A stale 90-day certificate therefore cannot schedule a distant renewal timer that overflows the browser timer range. Canonical validation, microsecond expiry ordering, and project/session/request fences are unchanged.

The new actual App/adapter/DesktopShell/ResourceExplorer fake-clock case starts healthy with 90-day expiry and leaves refreshes pending. At exactly 60000ms it resolves the latest pending request with another valid observation bearing the original `observedAt`, forcing timer reinstallation at the inclusive limit. It checks visible healthy at 60000, unknown at 60001, helper null when stale, per-node unknown, no out-of-range timeout, and no further timeout scheduling after staleness. This distinguishes `>` from the incorrect `>=` stale guard.

Direct console evidence on base plus the three enumerated edited files (`App.tsx`, `nodeCertificateObservation.ts`, `app-node-certificate-freshness.test.tsx`), Windows PowerShell / Node v24.10.0 / npm 11.6.1 / Vitest 4.1.11 / Vite 6.4.5:

| Command | Observed result |
|---|---|
| Before source fix: `npm --prefix apps/web test -- tests/app-node-certificate-freshness.test.tsx -t '90-day'` | 1 failed, 8 intentionally filtered/skipped, direct exit 1; assertion reproduced a timeout delay above 2147483647 at 15:25:44 KST |
| After source fix: `npm --prefix apps/web test -- tests/app-node-certificate-freshness.test.tsx tests/node-certificate-observation-contract.test.ts tests/auth-app-oidc-integration.test.tsx tests/node-cert-trust-expiry.test.tsx` | 4 files / 63 passed, 0 failed/skipped, direct exit 0 at 15:26:19 KST; includes strict microsecond contract and existing scope/session cases |
| `npm --prefix apps/web run lint` | 0 warnings/errors, direct exit 0 |
| `npm --prefix apps/web run build` | TypeScript plus production build pass, 297 modules, direct exit 0 |
| `git diff --check` | direct exit 0 |

The focused DOM run still logs localhost health HTTP 500, and Vite reports its large-main-chunk warning (1295.52 kB). Neither is live API/browser or operational acceptance evidence. The prior full suite and independent mutations belong to the base SHA, not this local follow-up.

Implementation and affected local verification are complete; independent review, final hosted same-SHA CI, integration, aggregate reports, and Obsidian apply remain coordinator-owned. No hosted CI dispatch, shared-board write, or Obsidian apply is performed by this worker. Pre-push documentation/ontology/sync check exits and remote head readback accompany the exact SHA in the final receipt. Next owner Claude: review this small successor diff and the actual App boundary case; coordinator: freeze the corrected head and run final hosted CI.
