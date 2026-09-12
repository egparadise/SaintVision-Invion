---
doc_id: "HIST-LAN-RESTORE-UPGRADE-START-20260912"
title: "2026-09-12 LAN-RESTORE-UPGRADE Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T18:53:00+09:00"
source_of_truth: "Git"
---

# 실제 snapshot 복원 사본 upgrade

CX-02 Codex 무결성 지원/reviewer Claude pending, 상위 S12-ST Claude owner 유지. based0463446dfa9e37f50f982a59271ddb207af324d, agent/codex/workspace-bridge, 진행판1.0.45/Codex1.0.25, agent-delivery1.1.0/core-reliability1.0.0, ADR096.

원본 READ ONLY exported snapshot의 public/inv 행 digest와 pg_dump를 일치시켜 관측 writer를 멈추지 않고 폐기용 DB 복원/upgrade/replay를 검증한다. 원래 열의 행 보존·커널 제한 역할 DB transaction·최종 definer 정책을 확인한다. 운영 source schema/권한/Node 변경 없음. 같은 클러스터 기존 역할을 사용하는 DB 복원이며 독립 장비·PITR·영속 백업 보관·HTTP/실행 인수와 구분한다.
