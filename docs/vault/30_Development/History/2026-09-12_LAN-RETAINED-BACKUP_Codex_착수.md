---
doc_id: "HIST-LAN-RETAINED-BACKUP-START-20260912"
title: "2026-09-12 LAN-RETAINED-BACKUP Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T19:44:22+09:00"
source_of_truth: "Git"
---

# 보관 파일을 사용한 실제 DB 복원

CX-02 Codex 무결성 지원 / Claude reviewer pending, 상위 S12-ST Claude owner 유지. base4ef821b15b1763bbf41f08bbf429617091505397, agent/codex/workspace-bridge, 진행판1.0.46/Codex1.0.26. agent-delivery1.1.0/core-reliability1.0.0 적용.

기존 exported snapshot 리허설에 명시적 새 private backup directory 옵션을 추가한다. dump/manifest를 배타 생성하고 flush/fsync 및 저장 hash를 재검증한 bytes로 복원한다. 원본 dump를 Git/Obsidian/public로 내보내지 않는다. 로컬 서버 보관이며 외부 매체/암호화/PITR/독립 역할 복원을 주장하지 않는다. 운영 migration·Node 교체는 이 작업 범위 밖이다.
