---
doc_id: "HIST-INDEPENDENT-RESTORE-START-20260914"
title: "2026-09-14 INDEPENDENT-RESTORE Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:46:57+09:00"
source_of_truth: "Git"
---

# 별도 클러스터의 보관백업 복원

CX-01/S12-ST 지원(Codex owner, Claude reviewer pending), basedced84bedb1a8725328543142a6fe6a1634f5f50, agent/codex/workspace-bridge. agent-delivery1.1.0/core-reliability1.0.0. 이전 검증은같은cluster의role에의존했다. 기존보관snapshot SHA256 361c4f32a211e2029a4d38370d086d913afa58ccfb5eb9e7f32476b602ee9c5c를별도 Docker PostgreSQL에복원하고schema/모든행hash/0037upgrade/replay/definer/runtime을검증한다. 원래DB에접속하거나운영credential을재사용하지않는다. bootstrap은안전한NOLOGIN그룹과검증전용난수login을명시한다. source백업/운영Node/schema/profile보존,일회cluster만정리. off-device/PITR/전원차단증거는아니다.
