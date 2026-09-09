---
doc_id: "DEV-APPROVAL-BOUNDARY-001"
title: "Codex 승인 경계 개발 과정"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-09T22:25:39+09:00"
source_of_truth: "Git"
---

# Codex 승인 경계 개발 과정

TaskCard: approval-boundary; owner Codex; reviewer Claude; branch agent/codex/approval-boundary.
base SHA `33833dda70207cee39e73fb097140f9ad8abf3ad`. core-foundation PR #1의 Core/Documentation CI는 success, 독립 review는 확인 시 없음.

입력: GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001/PLAN-DB-001/PLAN-S04 v1.0.0, ADR-INDEX-001 v1.1.0, CORE-CONTRACT-001 v1.0.0. Skill agent-delivery/core-reliability v1.0.0. 사용자 지시: 후속 개발 및 critical 외 기존 승인 자동 진행. 실제 운영 권한을 새로 확대하지 않는다.

목표→증거→계약→작업: OUT-04/AC-04(승인 전 실행 요청 0, 중복 dispatch 0) → 실제 PostgreSQL 승인/nonce/동시성/rollback/RLS 시험 → ApprovalRequest·Decision·Dispatch → S04-BE/DB의 승인 계약 준비. S01·S02·S03 통합이 미완료이므로 S04 done/ready로 승격하지 않는 별도 사전 계약 검증 TaskCard다.

scope: core 승인 라이브러리, 0002 migration, additive JSON Schema/생성 타입, 관련 tests/CI/docs. 제외: 실제 명령 실행, 공개 mutation API, IdP 선택·연동, Node mTLS, 운영 배포, 다른 Agent 업무 코드.

합격 증거: distinct approver와 requester 자기 승인 차단; 내용 digest·scope·expiry·epoch 고정; nonce 원문 미저장·한 번 소비; 동시 재시도 단일 dispatch; 승인/audit/outbox/Run 전이 rollback; grant 취소 반영; migration·기존 66개 시험 회귀·생성 계약 검사.

선행 조건: base 코어와 격리 CI PostgreSQL 시험 환경 사용. 신원·project grant는 신뢰된 adapter/운영 projection 입력이며 브라우저의 actor 문자열을 인증으로 취급하지 않는다. reviewer 수신 pending. Windows sandbox 실패로 승인된 외부 실행을 사용한다.

결과와 명령·exit·CI ID·Obsidian hash는 후속 검증 보고에 연결한다.

## 2026-09-09T22:59:31+09:00 로컬 검증

python tools/generate_contracts.py exit 0; pytest 첫 수집 exit 1(동명 모듈 충돌), 수정 후 exit 0(63 passed/38 PostgreSQL skipped); check_docs.py/check_ontology.py/test_sync.py/git diff --check 모두 exit 0. sync_obsidian.py --check exit 0, 102 managed/11 pending/0 conflict(추가 계약 문서 작성 전 시점). DB 검증은 CI 격리 PostgreSQL로 이어간다. 오류·해결은 [[ERR-APPROVAL-001 승인 테스트 수집 충돌]]과 [[RES-APPROVAL-001 테스트 모듈 분리와 재검증]].

## 2026-09-09T23:03:51+09:00 구현 CI 검증

코드 `73e8774035a6a8677e5dfd317b444c6fa60a331f` commit/push exit 0. Core #34360662284 / Documentation #34360662521 success. 원본 JUnit 101 tests/0 failures/0 errors/0 skipped 확인. 보고서 [[2026-09-09_23-03-51_KST_APPROVAL-BOUNDARY_Codex_검증보고]]. 독립 검토 pending.
