---
doc_id: "HIST-APPROVAL-REVIEW-SNAPSHOT-REPORT-20260914"
title: "2026-09-14 APPROVAL-REVIEW-SNAPSHOT Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T23:29:42+09:00"
source_of_truth: "Git"
---

# 다이제스트 결속 승인 검토 서버 후보

제품024a817, branch agent/codex/workspace-bridge, base3d479bd. commit/push 완료. owner Codex/reviewer Claude 대기, Gemini UI 인수 대기. 공유integration/main 및 운영 미반영.

- migration0038은 `inv.approval_review_snapshots`를 추가한다. tenant RLS/FORCE, 기존 approval 복합 FK, SELECT/INSERT만 inv_kernel 허용, UPDATE/DELETE 불가 trigger. workload·policy·policy hash를 승인 생성과 같은 transaction에 보존한다. 요청 replay가 행을 중복 생성하지 않는다.
- GET `/v1/projects/{project}/approvals/{approval_id}/review`: can_approve 권한, 같은 tenant/project, 현재 epoch/Run 상태·버전/만료를 확인한다. pending/approved에서만 검토 가능하며 별도 상세응답은 Cache-Control:no-store. 기본 ApprovalView/목록은 변경하지 않아 명령을 노출하지 않는다.
- 저장된 workload의 action digest와 policy hash·decisionId·requester·tenant/project·requiredApprovals·만료를 검증한다. 응답은 `ApprovalReviewView`: approval, workload, riskLevel, policyDigest. JSON Schema 정본에서 Python/TS/Go 및 Node 검증 schema를 재생성했다.
- approve와 dispatch에도 동일 snapshot 검사를 적용한다. 내용 변조/스냅샷 누락은409로 거부, nonce/vote 변경 없음. snapshot 없는 이전 승인 요청도 approve/신규dispatch 불가다. 자동 backfill하지 않는다. 기존 기록에 대한 반려는 가능하며 완료된 idempotent 요청의 응답 재조회는 기존 동작을 유지한다.

검증: 격리 PostgreSQL16의 신규 DB에서 실제 Alembic head0038 upgrade, 비소유자 runtime/RLS, FastAPI HTTP 및 합성 JWT. `python .work/test_approval_review.py`의 본 시험은 test_approval_review/test_approvals/test_project_observation/test_control_api 총 **48passed**, exit0,34.44s. 새7개는 실제 action 조회·401/403/다른tenant/project404·권한회수·immutable/replay·workload/policy/missing 거부·nonce보존/반려·취소Run409. 이 wrapper는 전용 라벨을 확인하고 생성한 임시 컨테이너만 제거했다. [시험 증거](../Evidence/approval-review-postgres-024a817.json).

첫 실행45passed/3failed는 시험 owner 쿼리가 이전 fixture의 tenant행까지 집계한 오류였다. 업데이트/삭제/집계를 tenant+approval ID로 한정한 후 새 격리클러스터에서48통과. 오류를 제품 통과로 숨기지 않았다. 기존 Starlette/FastAPI TestClient 경고2개는 남았다.

`pytest -q tests/core/test_approval_contracts.py`:10passed/0.59s,exit0. `go test ./...` in packages/contracts-go:exit0(시험파일 없음, 생성 타입 컴파일만 확인). `tools/generate_contracts.py`:exit0, 생성기 formatter 미래변경 경고. `git diff --check`:exit0.

운영 DB0038 upgrade·이전 대기승인 전환·실IdP·원격 Node 시험은 미수행. 신규 DB upgrade만 시험했으며 retained backup0037→0038 업그레이드 리허설은 아직 없다. 원본 command가 승인 검토자에게 보여야 하는 계약이며 별도 검토경로 외 목록/오류/감사에는 스냅샷을 넣지 않는다. 정책 발행 권한은 기존 trusted boundary에 의존하며 이 작업이 정책 서명 체계를 새로 만든 것은 아니다.

다음 Codex: frontend b0ecb5e에 명시적 review fetch를 연결하고 사용자가 확인한 actionDigest와 결정 payload가 동일함을 보장한다. UI에서 command 배열/자원·image·timeout·resume/start 정보와 위험도를 표시하고, 늦은 응답/다른 안건/다이제스트 변경/미지원 서버를 거부한다. 현재 UI 승인은 계속 보류된다. Claude: snapshot 보존·RLS·구버전 이행 독립 검토. Gemini: 통합 후 실제 브라우저 확인. 전체57.8125%(2775/4800), 남음42.1875% 유지.

동일 SHA CI6건(Backend/Core/Docs 각2)은23:29:51KST 결제/한도 제한으로 job 시작 전 실패. [CI 증거](../Evidence/approval-review-ci-024a817.json). 문서401개/48task·ontology exit0. CI/독립검토/운영인수 완료 아님.

외부편집3개로 최초sync exit1/쓰기0. 원문 보존·수신 검토 후 재동기화한다. [[2026-09-14_APPROVAL-REVIEW-SNAPSHOT_Codex_오류해결]] 참조.
