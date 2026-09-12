---
doc_id: "HIST-STORAGE-VIEW-20260912"
title: "2026-09-12 STORAGE-VIEW Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T14:15:21+09:00"
source_of_truth: "Git"
---

# 2026-09-12 STORAGE-VIEW Codex 검증보고

2026-09-12T14:15:21+09:00 / product `9d7559efb15a1f8fcbe90c74d2cd985bd1f44d0c` / base34f0a21 / agent/codex/workspace-bridge / CX-02 owner Codex, reviewer Claude pending / PR19 draft. [[2026-09-12_STORAGE-VIEW_Codex_착수]], [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.4.0 / ADR-091.

## 작업한 것

kernel 인증 경로 `GET /v1/projects/{project}/runs/{run_id}/storage-samples/{request_id}`를 추가했다. 브라우저 입력의 신원을 믿지 않고 기존 AccessTokens 검증을 사용한다. 현재 kernel can_request와 linked business project/user/member, 원 요청자와 contribution 등록 소유자를 함께 확인한다. Run SHARE→현재 grant/business 권한 SHARE→contribution SHARE 순서로 검사하여 권한 회수와 경합할 때도 중간 상태를 읽지 않는다. GET은 Node 수집이나 DB 기록을 시작하지 않는다.

기존0037 request/consumption, inv.evidence/public.storage_checks를 조회한다. 응답은 pending/expired/recorded, 발급/만료 시각 및 최소한의 observation으로 구성한다. 기록이 있으면 저장된 challenge digest, response hash, 서명/당시 인증서, 개별 표본 count, StorageCheck와 Evidence 전체 메타데이터/입출력 hash를 재검증한다. 손상된 연결이나 서명은 VERIFY-0032/409이며 Verified로 표시하지 않는다. 조회 후 raw 루트 경로·파일명·nonce·서명·인증서·사용자 subject는 반환하지 않는다. 모든 응답은 기존 Boundary의 no-store를 적용한다.

`integrityVerified=true`는 저장된 관측의 서명과 연결을 확인했다는 뜻이다. `sampleHealthy`는 관측 당시 제한된 표본 일치이고 `currentHealth=unknown`, `operationalAcceptanceAssessed=false`를 고정한다. Run이 종료되거나 Node channel/폴더가 회수돼도 **현재 프로젝트 요청 권한과 원 요청자/등록 소유자가 유지되는 경우** 과거 기록을 조회할 수 있다. 새 수집/기록은 기존0037의 더 엄격한 현재 active/channel/root/epoch 검사를 계속 요구한다. 과거 인증서의 현재 만료 여부로 이미 검증된 당시 기록을 없애지 않으며 관측 당시 인증서/서명을 검사한다. DB session timezone이 Asia/Seoul이어도 Evidence의 UTC timestamp와 의미를 맞춰 비교한다.

공통 Schema에 StorageObservationView/RecordedStorageObservation을 추가해 Python/TS/Go 및 Node wire bundle을 같은 원본에서 생성했다. recorded에는 observation이 필요하고 pending/expired에는 null만 허용한다. schema 변경은 조회 계약 추가이며 새 migration/SECURITY DEFINER/운영 DB 변경은 없다. 기존 RunResultView를 다른 구현으로 대체하지 않는다.

## 확인한 증거

| 검증 | 결과 | 근거 |
|---|---|---|
| clean9d7559e Linux 실제 Go/mTLS/파일/PostgreSQL | **153 passed/0 skipped/exit0**: view18/commit22/Node20/서명68/파일25 | [실행 SHA·개별 case·image/hash·cleanup](../Evidence/storage-view-linux-9d7559e.json) |
| Windows 실제 PostgreSQL view/control API | **25 passed/0 skipped/exit0**, 한국시간 session 포함 | [25개 case](../Evidence/storage-view-windows-9d7559e.json) |
| 이전 Windows 작업본 view/commit/contracts | 69 passed/0 skipped/exit0, timezone 보강 전 | 개발 중 검증이며 환경 간 중복 합산하지 않음 |
| git push origin agent/codex/workspace-bridge | exit0 | 제품9d7559e |
| 같은 SHA CI6개 | account payment/spending limit 때문에 job 미시작 failure | [CI IDs](../Evidence/storage-view-9d7559e-ci.json) |

실제 JWT 인증, 미인증/다른 사용자/tenant/소유권 변경, grant 회수, 읽는 동안 회수 시도 lock timeout, pending/expired 재조회 무변경, 정상·불일치 기록, terminal Run/channel 회수 뒤 과거 조회, raw 정보 비노출, signature/challenge/Evidence hash/표본 수/healthy 변조 거부를 확인했다. expired pending 시험은 issuer 시각을60초 과거로 주입했으며 실제60초를 기다린 실장비 시험이 아니다. 변조는 disposable DB owner로만 trigger를 잠시 해제해 주입했다. runtime에는 그 권한이 없다.

최초67개 중2실패: 계정 fixture의 disabled는 실제 enum이 아니어 suspended로 수정했고, 저장 서명 오류가 입력용422로 남던 것은 읽기 무결성409로 정규화했다. [[2026-09-12_STORAGE-VIEW_오류와 해결]]. 생성기의 formatter future warning과 기존 테스트 경고는 실패가 아니다. 운영 .225/기존 Studio 프로세스나 사용자 Workspace에는 배포하지 않았다.

## 이어서 할 첫 행동

- Codex: 등록 폴더와 Go --storage-policy의 경로/버전/owner 대응, 설치 receipt와 통제된 교체 절차를 구현·검증한다. 이 조회 API는 request UUID를 이미 아는 인증 호출자를 위한 것이다. 목록/수집 시작 HTTP API·운영 설치 자동화·원격7개 업무 시험은 아직 남아 있다.
- Claude:9d7559e/0037/ADR-091의 현재 인가·과거 인증서 검증·읽기 잠금/보존 계약 독립 검토. 정상 계정/운영 프로젝트와 폴더 연결은 기존 owner를 유지한다.
- Gemini: 위 GET/공통 Schema를 사용해 pending/expired/recorded를 표시하고 `sampleHealthy`를 현재 디스크 정상이나 Run 완료로 바꾸지 않는다. 노출된 raw root/키가 필요 없는 화면으로 연결한다. 운영 API 연결·브라우저 인수 증거는 별도다.

전체 성숙도 **2775/4800=57.81% 완료 /42.19% 잔여 유지**. 조회 구현만으로 CI/독립 검토/실장비 인수 gate를 완료하지 않는다. PR19 draft 및 #21→#22→#19 검토 순서 유지.

## 외부 공유본

Obsidian check에서 진행판/Gemini 작업판/History 인덱스/인계 목록4개 외부 변경을 감지해 exit1/쓰기0. [원문·hash 보존](../Evidence/obsidian-proposals-20260912-storage-view/manifest.json). Gemini b90c788의 PTY/Drain·Vitest107/smoke154/2-PC63/deploy5는 작성자 보고로 수신하며 이번 독립 검증이나 물리 운영 인수로 채택하지 않는다. 기존 Codex 이력과 검증된 공통57.81%를 유지하고 수신 요약만 반영한다. 외부 원문은 commit 후 동일 bytes를 확인하여 쓰기0 인수하고 정상 동기화한다.


전달 전 검사: check_docs.py exit0(원문24/문서324/작업48), check_ontology.py exit0, git diff --check exit0. PR19 설명을 새 인증 조회/검증 범위로 갱신하고 draft 유지. 보고 commit/push 후 보존 원문4개를 Git blob·mirror·staging hash로 대조하여 쓰기0 인수하고 Obsidian을 동기화한다.


최종 전달: 보고4bc42c9 push exit0. 외부 원문4개는 동일 bytes 쓰기0 인수. 2026-09-12T14:16:07+09:00 Obsidian601개 hash일치/pending0/conflict0, check→apply→check exit0. [동기화 영수증](../Evidence/storage-view-obsidian-20260912.json). 영수증 포함 후속 commit도 push/재동기화한다. OneDrive 클라우드 업로드 미검증. 다음 Codex는 폴더-root policy 설치·교체/receipt, Claude9d7559e 독립 검토, Gemini 인증 GET 표시 연결.
