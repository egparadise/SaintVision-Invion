---
doc_id: "HIST-CODEX-FE-REVIEW-MAP-20260922"
title: "S02-FE~S12-FE 검토 증거 지도와 착수 순서"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Codex"
updated: "2026-09-22T10:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# 판정 범위

S01-FE가 `done`으로 이동한 뒤 남은 `review` 11개를 검토자 관점에서 다시 분류했다. 예전 Gemini 기록의 Vitest 수는 구현·대역 증거로만 취급했다. `review`를 `done`으로 바꾸지 않았고, 이 문서도 독립 검토 승인으로 간주하지 않는다.

현재 확인된 실제 브라우저 능력은 Gemini의 Chrome 153 `ApprovalReviewPanel` 보고(`2026-09-22_ApprovalReviewPanel_비동기전이와_Chrome153_실측수용_Gemini.md`)에 한정한다. 그 보고는 승인 검토 8개 시나리오의 Chrome 실행을 증명하지만 다른 스프린트의 API·DB·장비·배포 증거를 대신하지 않는다.

## 과제별 분류

| 순서 | 과제 | 요구 증거 | 현재 가장 가까운 증거 | 지금 만들 수 있는 것 | 남는 전제·차단 |
|---:|---|---|---|---|---|
| 1 | S02-FE | 실제 API·브라우저 여정·인증 실패 | 기존 노드 상태 테스트와 프런트 계약/상태 시험 | Chrome에서 로그인·노드 목록·상세·오류 여정의 브라우저 절반. 실제 HTTP를 붙인 시나리오 골격 | 실제 IdP 로그인, CA/mTLS, DNS, 5대 노드와 Heartbeat. S02 전체는 S01-BE/ST와 함께 열림 |
| 2 | S03-FE | 허용·거부 로그·exit code·증거 ID | Workspace/결과 DOM·계약 시험 | Chrome에서 모달·결과/오류 표시와 실제 HTTP 왕복을 만들 수 있음 | 실제 sandbox·Tool Gateway 실행, 허용/금지 명령 로그, 자원 회수와 증거 ID. S02 전 영역 선행 |
| 3 | S04-FE | 만료 승인·취소·중복·재전송 통합 결과 | Chrome 153에서 승인 검토 8개 시나리오와 challenge/decision roundtrip 확인 | 승인 패널·타임라인·오류·중복 UI의 브라우저 증거를 확장할 수 있음 | 실제 만료/취소/SSE 재연결/전송 재개와 DB 상태. S03 전 영역 선행 |
| 4 | S09-FE | golden eval·분류별 성적·금지 행동 시험 | `agentEngine` 및 Vitest 기록 | 외부 장비 없이 고정 SHA에서 100건 golden eval과 누출/금지행동 변이 증거 재생산 가능 | 실제 모델/도구 호출이 없는 합성 평가라면 제품 인수 증거가 아님. fresh SHA·입력/출력 원본 필요 |
| 5 | S10-FE | adapter conformance·lineage query·배포 digest | adapter 계약 시험과 모델 화면 시험 | 계약 적합성·실패 분류·digest 계산의 로컬 증거 | 실제 lineage 저장소/query와 배포 승인·digest의 서버 왕복. lineage 데이터가 미노출이면 화면은 미검증으로 남음 |
| 6 | S05-FE | 경합 테스트·snapshot/weight/policy 버전·Explain | 배치 시뮬레이터/Explain Vitest | 단일 입력 Explain과 상태 표시를 Chrome에서 확인 가능 | 50개 동시 예약·P95 2초·실 snapshot/weight/policy 및 DB lease. 부하 환경 필요 |
| 7 | S06-FE | 소스 commit·WS/PTY·restart·restore | Monaco/xterm/diff 단위·DOM 시험, PTY 계약 | 브라우저 편집·터미널 오류·계약 경계 | 실제 WS/PTY ticket, CP 재시작, 저장 snapshot 복구와 hash. 로컬 서버는 가능하지만 아직 해당 통합 증거 없음 |
| 8 | S07-FE | Node 중단·분할·late result·cache 경합 | stale/fencing 단위 시험 및 복제본 배선 | 상태 전이와 stale 표시의 브라우저 대역 증거 | 실제 Node 중단/네트워크 분할/late write와 다중 DB 경합. 물리 또는 Linux 네트워크 환경 필요 |
| 9 | S08-FE | 보안 시나리오·GPU capability·복원 보고 | 소켓 경로·kill-switch·합성 GPU 코드 시험 | 권한 오류·소켓 차단·관리 화면의 Chrome 증거 | 실제 GPU capability, Docker 격리, backup restore와 보안 실행. GPU/장비·복원 환경 필요 |
| 10 | S11-FE | E2E·부하·복원·보안·접근성 결과 | 접근성/릴리스 UI 시험, Chrome 실행기 | WCAG와 릴리스 후보 UI의 Chrome 증거 | 부하·복원·보안 시나리오와 실제 릴리스 후보. CI/운영 환경 필요 |
| 11 | S12-FE | Release manifest·사용자 인수·웹 smoke·복구 Evidence | 배포 화면/manifest 단위 시험 | 로컬 HTTPS smoke 골격과 manifest 일관성 검사 | 5노드 내부망, TLS/Nginx 실제 배포, 사용자 인수·복구. 장비·운영 인수 필요 |

## 착수 순서와 닫힘 조건

1. **S02-FE**: Gemini가 먼저 실제 Chrome에서 로그인·목록·상세·인증 실패를 만들되, IdP/CA/DNS/노드가 없는 경우 브라우저 대역 증거로 표시하고 `done`으로 올리지 않는다. 실제 API 응답과 401/403 기록이 생겨야 닫힘 후보가 된다.
2. **S04-FE**: 이미 Chrome 실행기가 있고 승인 검토 roundtrip도 실측됐으므로 S03의 실제 실행 결과가 준비되는 즉시 만료·취소·중복·SSE 재연결을 확장한다.
3. **S09-FE**: 외부 환경이 없어도 가능한 가장 작은 독립 카드다. 단, 고정 SHA·입력 집합·실행 수·skip 0을 기록하고 합성 평가를 실제 모델/운영 인수로 과장하지 않는다.
4. **S10-FE**: S09 다음 계약 적합성·lineage 경계를 닫는다. lineage query와 배포 digest가 실제 서버에 없으면 그 부분은 사용자 결정/백엔드 선행으로 남긴다.
5. S05~S08, S11~S12는 각각 부하·장비·GPU·복구·배포 증거가 필요한 순서로 외부 전제가 충족될 때 진행한다.

`S02-FE`부터 `S12-FE`까지 모두 기존 구현과 로컬 시험은 있으나, 요구 증거 전체를 충족해 `done`으로 닫힌 것은 없다. 브라우저 능력은 실행 증거를 새로 만들 수 있게 했지만 IdP·장비·DB·부하·운영 인수를 대체하지 않는다.

