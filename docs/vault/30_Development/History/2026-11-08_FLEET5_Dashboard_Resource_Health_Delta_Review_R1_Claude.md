---
doc_id: "HISTORY-FLEET5-DASHBOARD-RESOURCE-HEALTH-DELTA-REVIEW-R1-20261108-CLAUDE"
title: "DASH-RESOURCE-01 and DASH-HEALTH-02 dashboard delta review R1"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-08"
source_of_truth: "Git"
---

Task DASH-RESOURCE-01 / DASH-HEALTH-02 delta review (Orca task_0e409ca1e4bb). Claude is the actual independent reviewer, the author is Codex task_e04bfe8c6446, and Root is the sole APPLY owner. The delta runs `e4e07bfd6b94e57edc64d158e208df01b9319deb` → `abb7074e3da0d547ac81d3da33dce347d5c656af` (through `1dc73940`), the backend stays `96afd799`, and the Root checkpoint is `ff7e21d075b1b032ea6db0374b0ad51c9621c24b`. Review branch: `agent/claude/fleet5-dashboard-resource-health-delta-review-r1-20261108`, created from my prior head `20d9bf8622a0f0624a323b92acaeb33cea91fb9e`. Pins and per-area reasoning are in [review](../Evidence/fleet5-dashboard-resource-health-delta-review-r1-20261108-claude/review.json). The e4e07, CR-CSP-02 and CR-905-01 acceptances are inherited, and CR-CSP-02 and CR-905-01 remain CLOSED.

**Verdict: ACCEPT_DASH_RESOURCE_AND_GATEWAY_HEALTH_DELTA_KEEP_REAL_DEPLOYMENT_AND_MANUAL_GATES, mandatory defects 0.** Both source findings are closed at the source.

**DASH-RESOURCE-01**
- **Identity first:** the App publishes the real three-field node identities (status and heartbeat) first, so a hung or failed usage read can no longer hide them. It then joins the existing scoped `resource-usage` read with 4 workers, at most 64 reads per poll, a 4 s child deadline and the existing 10 s poll timeout.
- **Fences:** credential, session, project, request order and abort checks guard every update. Logout and project switch clear the cache, and a cached value is reused only for the same project.
- **Validation:** strict closed-shape, source, node, unit and calendar-timestamp checks reject bad responses. A malformed or duplicate row removes only its own dimension.
- **Stale handling:** stale, last-good and failed values are shown explicitly and never counted in current totals.
- **Freshness:** the real recorded `observedAt` equals the heartbeat time and was about 2 s old when captured, so the 60 s window will not mark the live CP as stale.
- **Units:** 500m/64 MiB per node and 1500m/192 MiB in total are labelled as execution-kernel offered/reserved/spare, not physical capacity, OS utilization or admission.
- **Unknowns:** missing GPU, storage and OS stay unobserved. Unknown OS no longer becomes Windows, and a placement preference fails closed against it.

**DASH-HEALTH-02**
- **Header:** it uses `/gateway-healthz` with credentials omitted and no-store. It reports healthy only for an exact 200 with `application/json` and `status:"ok"`.
- **Vite dev/preview proxy:** maps only an exact GET/HEAD to the CP `/healthz` and strips auth/cookie.
- **Portal Nginx:** keeps TLS verification, CA, SNI and Host as in `/v1`, passes the raw upstream status/body/MIME through, strips credentials, adds no-store, and rejects a query (400) or another method (403). Portal `/healthz` stays process liveness.
- **Root adapter:** Root's loopback/SSH adapter must add the `/healthz`-bearing `proxy_pass` replacement. Without it the header fails closed and never fabricates health.

**Tests and harnesses**
- **New tests:** the 29 new cases replay the actual Root wire inputs and are meaningful.
- **Existing tests:** the two existing tests change only their URL.
- **1dc corrections:** the type alignment, the removed optional border and the once-only isolated login mock do not weaken any test.
- **Dashboard replay:** fixes only Date, keeps cards and badges mounted for 30 s, and checks the partial, last-good-excluded and CP html/text/503 transitions.
- **Nginx smoke:** runs against real TLS, and its upstream returns 500 if credentials leak.

**Note for Root's frame check (not a defect):** every poll briefly shows the intentional line "자원 관측 확인 중 · 이전 관측 유지" on each card, while totals keep their previous values.

Checks I ran: source reads of every changed product, tool and test path; object ID comparisons for the protected list (all equal to e4e07); Root input SHA-256 pins at ff7e21d0, including the delivery.json LF/CRLF reconciliation (121,334 B as an LF blob, 124,119 B / `d678419c` as CRLF); and `gh run view` of Frontend 42410996328 (21 + 16 steps), Docs 42410998999 (19), AC11 42411001237 (14) and the retained first-candidate failure 42410597855. Local docs gates are in [local gates](../Evidence/fleet5-dashboard-resource-health-delta-review-r1-20261108-claude/local-gates.json), and the full canonical comparison is in [sync state](../Evidence/fleet5-dashboard-resource-health-delta-review-r1-20261108-claude/sync-state-comparison.json). I ran nothing on Main.

Retained gates:
- Root's adapter replacement and exact-abb PC3 redeploy, with a real login/resources check and the 30 s frames/no-blink check.
- AC11 manual user-device acceptance. The report is still MEASURED_FAIL with manualAcceptanceMissingCount 1.
- Genuine votes and Run/output/audit.
- PC1 key, PC5 RAM/Node, GPU/storage, all five PCs, and renewal/reconnect/reboot.

Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN unchanged, and wholeProgramComplete is false.
