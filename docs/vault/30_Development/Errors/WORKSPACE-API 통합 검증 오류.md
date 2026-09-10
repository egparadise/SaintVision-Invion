---
doc_id: "ERR-WORKSPACE-API-001"
title: "WORKSPACE-API 통합 검증 오류"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T12:18:00+09:00"
source_of_truth: "Git"
---

# WORKSPACE-API 통합 검증 오류

Task WORKSPACE-API, owner Codex, reviewer Claude pending. 해결은 [[WORKSPACE-API 통합 검증 해결]] 및 [[Codex Workspace 공개 API와 실행 커널 통합 계약]]을 따른다. 실패한 실행을 성공으로 변경하거나 합계에서 숨기지 않는다.

## 최초 통합 SHA 4a60a15

2026-09-10 KST. Core push 34432003897, PR 34432020749의 Workspace 선행 시험은 18개 중 17 pass/1 failure/0 error/0 skip이었다. 마지막 `test_unapproved_enqueue_is_not_dispatched`가 기존 AUTH-0031의 실제 403을 409로 기대했다. 미승인 실행이 허용된 실패가 아니며 프로덕션 거절 동작은 유지했다. 선행 단계 실패로 전체 Core 시험/최종 package는 실행되지 않았다.

Backend push 34432003957 및 PR 34432020755에서 Python 3.12/3.14의 기존 migration 시험이 tuple 부모를 인정하지 않고 모든 revision이 일렬이라고 가정했다. 3.12 로그는 453 pass/2 failure다. 실제 merge revision의 양쪽 선행 head를 검증하도록 시험과 graph 도구를 수정한다. 공개된 0018 Workspace/0010 자원 단위 migration의 부모를 다시 쓰지 않는다.

Frontend push 34432003882 및 PR 34432020781은 Vitest 90개를 통과했지만 TypeScript build가 실패했다. App의 미사용 인증 import/상태 변수/매개변수와 존재하지 않는 PlacementEvaluationResult 타입이 원인이다. 원래 정의된 PlacementExplainResult를 사용하고 미사용 참조를 정리했다. 이 수정이 실제 브라우저·Node 연동 완료를 의미하지 않는다.

## 자체 경계 검토

초기 공개 enqueue는 현재 requester/approver 권한과 지정된 Node를 확인했으나 별도의 `project_nodes` 소속을 요구하지 않았다. 기존 내부 worker가 받은 Node 권위를 새 공개 경계에서 그대로 사용해서는 안 된다. e9dd341에서 소속 preflight와 Node lock 뒤 최종 소속 lock을 추가하고, 관측 중 소속 회수 시 전체 admission rollback을 시험한다. 이는 Codex 자체 검토 결과이며 Claude의 독립 review라고 기록하지 않는다.

## 동기화

Obsidian check가 Gemini 보고서/History 인덱스 두 파일을 외부 변경으로 감지해 exit 1로 중단했다. 정규화 비교 결과 내용은 완전히 같고 CRLF/LF만 달랐다. 원본 bytes·SHA를 `Evidence/workspace-api-sync-line-endings.json`에 보존하고 검토한 hash만 sync state에 반영했다. 후속 check/apply/check는 exit 0이며 알 수 없는 문서 내용을 덮어쓰지 않았다.
