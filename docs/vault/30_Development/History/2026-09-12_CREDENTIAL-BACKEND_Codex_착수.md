---
doc_id: "HIST-CREDENTIAL-BACKEND-START-20260912"
title: "2026-09-12 CREDENTIAL-BACKEND Codex 착수"
version: "1.0.1"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T00:55:42+09:00"
source_of_truth: "Git"
---

# CREDENTIAL-BACKEND 착수

사용자의 모든 과정 계속 진행 지시에 따라 이번 backend 구현 단위 owner를 Codex로 인수한다. reviewer Claude pending. 기존 정본 Protocol/39개 suite를 사용하며 두 번째 resolver를 만들지 않는다. base408cb5470992689ea206e31ca6bdcea56e5e862b, branch agent/codex/workspace-bridge, CX-02 / S01-BE·S08-ST.

진행판1.0.20, Codex1.0.6, 운영계약1.1.0, conformance1.0.0, agent-delivery1.1/core-reliability1.0. Claude 최신dcad652에는 credential 구현이 없으며 0031/recovery_drill의 미커밋 변경은 건드리지 않는다. Claude5995b8b readiness/dcad652 Context 변경 검토는 후속으로 추적한다.

Linux 파일 descriptor/hash/권한 보호와 PostgreSQL tenant/project/subject/run/purpose/destination 및 회수 registry를 구현한다. runtime에는 SELECT만 허용한다. 실제 파일/DB conformance39개와 파일 교체·회수 장벽·권한/복원/upgrade 회귀를 수행한다. 운영 secret/DB/Node를 변경하지 않는다. 실제 provider 호출/모델/운영 입력은 별도다.

## Context·readiness 통합 후속

2026-09-12T01:08:17+09:00 기준 Claude dcad652 Context를 35c88e0으로 cherry-pick했고 5995b8b의 readiness 도구·전용 시험만 선별 반영했다. Claude의 미커밋 0031/recovery 변경과 오래된 migration graph 시험은 반영하지 않았다. 코드 리뷰에서 Context 오류의 raw item_id/cause_ref와 metadata 비밀 노출, readiness의 실행 가능 단정·DSN 명령행 전달을 확인하여 Codex가 보완한다. 공통 agent-delivery/core-reliability 적용. 수정 작성자 Codex, 독립 reviewer Claude pending. 합격 기준은 공개 오류 무노출·저장 전 거부·진단과 권한 구분·실제 PostgreSQL 및 Linux 회귀다.
