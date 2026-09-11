---
doc_id: "HIST-PERMISSION-SNAPSHOT-ERROR-20260912"
title: "2026-09-12 PERMISSION-SNAPSHOT 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T02:08:57+09:00"
source_of_truth: "Git"
---

# 2026-09-12 PERMISSION-SNAPSHOT 오류와해결

[[2026-09-12_PERMISSION-SNAPSHOT_Codex_검증보고]]의 후속 기록.

- d63717f P1 프로젝트 범위가 없는 직전 비교: tenant/project/user/contract 범위로 수정, A→B→A [null,null,false] 실제 확인.
- d63717f P1 disabled 운영자를 승인 가능으로 표시: enabled/person/subject/capability 관측과 현재 인가 null 분리. 실제 DB 회수 전후 시험 통과.
- d63717f P2 읽은 뒤 다른 시점 기록·동시 비교: 대상 lock 이후 일관 snapshot/기존 기록 서비스 호출, 같은 observedAt 보존·rollback·clock 역행 거부. 최초 개발 중 session advisory lock 선택을 transaction advisory lock으로 보완하여 transaction-mode 연결에서도 lock 수명은 열린 transaction에 고정한다.
- ade5bb8의 metadata만으로 evidenceComplete=true: 원본4개 실제 재현. 만료/목표/criterion 검사 및 catalog/operating 범위 분리로 수정, CLI text/JSON 공통exit 검증.
- CI9755c60: 동일 SHA6개 모두 billing/spending 제한으로 job 미시작. 로컬74/55를 CI 성공으로 쓰지 않는다.
