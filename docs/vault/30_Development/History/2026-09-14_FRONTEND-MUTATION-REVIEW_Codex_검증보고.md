---
doc_id: "HIST-FRONTEND-MUTATION-REVIEW-REPORT-20260914"
title: "2026-09-14 FRONTEND-MUTATION-REVIEW Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T20:50:38+09:00"
source_of_truth: "Git"
---

# 판정: 경로 정렬만으로 통합 승인 불가

Frontend 작성 Gemini, 독립 검토 Codex. 검토 대상 integration/all-agents-unified70ea3fb, kernel16a894a; 재현 시험 b95ab27 commit/push 완료. [원본 파일 SHA](../Evidence/frontend-mutation-source-70ea3fb.json). 아래 위치는 해당 frontend SHA 기준이다. 화면 코드 수정은 아직 수행되지 않았다.

## 발견 사항과 Gemini 수정 조건

| ID/우선순위 | 근거 | 영향 및 수정 조건 |
|---|---|---|
| FE-M01/P1 승인·반려 입력 | App.tsx:342–365,405–439; ApprovalDetail.tsx:67 | 목록은 nonce를 제공하지 않는데 빈 문자열로 채워 decision으로 보낸다. actionDigest를 버리고 challenge 호출도 없다. 반려는 reason을 보내지만 nonce/actionDigest가 없고 reason은 정본에 없는 필드다. 현재subject의 POST challenge `{}`에서 nonce를 받고, 조회한 actionDigest와 decision만 POST한다. 승인·반려 모두 Idempotency-Key를 사용하며 실패를 성공으로 바꾸지 않는다. ApprovalItem 매핑에서 actionDigest를 보존한다. |
| FE-M02/P1 취소 실패를 취소 완료로 표시 | App.tsx:446–468 | `{reason}`은 expectedVersion이 없어422다. catch가 화면 state를 cancelled로 바꾼다. 직전 부모 Run 조회 version으로 `{expectedVersion}`만 보내고, 서버 오류 시 마지막 확인 상태를 보존하며 오류/재조회 상태를 표시한다. 미확인 상태를 성공으로 합성하지 않는다. |
| FE-M03/P1 샤드 취소·수동회수의 구형 경로 | RunDetail.tsx:121–175 | 부모cancel에 reason만 보내고 Idempotency-Key가 없다. 실패하면 flat shards/cancel-all로 재전송한다. reclaim-resources 버튼도 남아 있다. 부모 정본cancel과 expectedVersion/key를 사용하고 다른 경로로 mutation fallback하지 않는다. 수동 회수는 제거하고 실제 receipt 기반 resourceReleasePending 상태 재조회로 바꾼다. |
| FE-M04/P1 관측 화면이 실제 자료를 보존하지 않음 | App.tsx:339–382, Header onlineNodesCount={5} | 빈 approvals items는 적용하지 않고 flat fallback한다. 이전승인이 남고 scope오류가 숨겨질 수 있다. 선택 프로젝트의 실제ID를 사용하고 빈목록도 그대로적용,401/403을 표시하며 flat fallback 제거. 임의 workspace/node/command/budget 기본값을 실측처럼 표시하지 않는다. online5 고정값을 실제 현재 관측 집계로 바꾼다. |
| FE-M05/P2 샤드 성공 조회 후 로딩 유지 | RunDetail.tsx:75–114 | 성공분기 return이 두번째 try의 finally를 건너뛰어 setIsLoadingShards(false)가 실행되지 않는다. 전체 조회에 공통 finally를 둔다. 성공/빈목록/실패/Run변경의 상태를 검증한다. |

독립 검토 결과는 위 scope에서 **changes requested**다. Gemini가 보고한 정적 미서빙0건과 smoke181/2-PC67은 위 요청 body와 실패 처리 합격 증거로 인정할 수 없다. 브라우저 시험 자체의 실행을 부정하는 것이 아니라 검증 범위의 차이다.

## 실제 재현과 수정 방향 대조

`python -m pytest -q tests/integration/test_frontend_mutation_contract.py`를 새 Docker PostgreSQL16의 임시 포트/난수 시험 계정으로 실행했다. **6 passed/12.71s,2 warnings,exit0**. [비밀값 없는 증거](../Evidence/frontend-mutation-http-review.json). 실제 커널 FastAPI HTTP·RLS DB이며 JWT issuer/subject는 합성이다. 원격Node/운영SSO/브라우저 시험이 아니다.

승인·반려 현재body2개는422이며 승인조회 전후 동일. 일반·부모샤드 취소 reason body2개는422이고 Run조회 전후 동일. 각 사례의 expectedVersion 정본취소는200/cancelled. 별도 승인·반려2개는 조회→challenge→nonce/actionDigest decision으로200. 부모샤드 실제 원자취소는 기존 PROJECT-OBSERVATION 시험이 근거이며 이번6개는 payload 경계 검증이다. 소유 시험 cluster 정리 완료,운영DB/공유frontend수정 없음.

## 다음 작업

Gemini owner: FE-M01~05 수정과 브라우저 성공/422/401/403/네트워크실패·빈목록 회귀 증거를 새 SHA로 제공. Codex reviewer: 새 SHA를 정본 kernel과 재검토. Claude: 재현 시험 자체 검토 및 운영 인증 입력. 새로운 API 추가나 커널의 엄격한 입력검사를 완화할 필요가 없다. 전체성숙도57.81% 유지, CI/운영인수 별도.

동일SHA CI6건은20:50:47 KST billing 제한으로job시작전실패. [CI 증거](../Evidence/frontend-mutation-ci-b95ab27.json). 실제진행하지않은CI/브라우저를통과로표시하지않는다.

최초 sync는 공통/Gemini 진행판 외부편집2개로exit1/쓰기0이었다. [원문 보존](../Evidence/obsidian-proposals-20260914-frontend-review/manifest.json) 후 경로정렬 보고와 이번payload검토를 구분해 정본에 합쳤다.
