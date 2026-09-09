---
doc_id: "CODEX-REMAINING-001"
title: "Codex 잔여 개발 작업과 합격 증거"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T02:30:12+09:00"
source_of_truth: "Git"
---

# Codex 잔여 개발 작업과 합격 증거

현재 제품은 5대 PC의 자원을 내부망 웹에서 안전하게 사용하는 개발·실행 환경을 목표로 한다. 코드/CI가 존재하는 kernel과 제품 전체 합격을 구분한다. baseline registry v1.0.0의 48 task와 12 Outcome은 선행·실장비·독립 검토 조건 없이 done으로 올리지 않는다. 이 표는 미구현을 숨기거나 다음 세션에 작업 승인을 다시 받기 위한 목록이 아니다.

owner Codex / reviewer Claude / task control-integration follow-up. 입력 GUIDE-001, PLAN-BACKEND/DB/STORAGE-001 v1.0.0, ADR-INDEX-001 v1.6.0. 현재 구현 HEAD는 이 문서와 연결한 History 검증 보고서로 고정한다. 작성자 자기 검증과 peer review를 혼동하지 않는다.

| 배정 task | 현재 확보한 kernel/증거 | 남은 구현 또는 합격 증거 |
|---|---|---|
| S01-BE/DB/ST | 정본 Schema, migrations 0001~0006, 강제 RLS, ID/권한/오류·trace 계약, package/CI/ontology | 실장비 5대·허용 폴더/자원·IdP/CA/DNS·Storage 제품 선택 및 운영 연결, peer review |
| S03-BE | 사전 승인 policy, 일회 ToolGateway, signed permit, Linux Docker 격리·정지 receipt | 업무 Workspace adapter, Windows driver/ACL, 운영 profile 및 실제 사용자 여정 |
| S04-BE/DB | 권한 있는 승인 challenge/decision·cancel API, 원자 ledger/outbox, bounded SSE/cursor, Node control cancel | workflow plan/approval request/dispatch daemon과 UI 통합, 오류·취소의 종단 자동 진행 |
| S04-ST | checksum/path 검증 함수, 합성 bytes 시험 | 제품 object storage의 resumable multipart, 중단/재개/동시 finalize/실제 checksum 검증 |
| S05-BE/DB/ST | deterministic ranking, locked Lease/Allocation/fencing, scope 검증 | quota/프로젝트 pool/실제 locality·전송비용 연결, 5노드 50동시 요청과 P95 실측 |
| S06-BE/DB/ST | Run 상태·attempt 경계와 Node durable intent/관찰 재개 | Git/PTY 권한·backpressure, durable Step/session/checkpoint, object snapshot 원자 publication과 실제 복원 |
| S07-BE/DB/ST | 현재 epoch/channel 검사, cancel/observation, heartbeat nonce·순서·timeout, Lease 물리 반환 | 자동 poll/sweep/reconcile/재스케줄 worker, drain 여정, 복제/cache pin/quota/GC 경합 |
| S08-BE/DB/ST | CPU sandbox와 독립 PID1 deadline, RLS, immutable audit/outbox, 기본 secret redaction | ROOF kill switch control·BuildKit·GPU/Windows 실측, secret provider, 안전한 retention GC, off-site backup/restore |
| S09-BE | bounded repair/policy·버전 및 RO 추적 kernel | 실제 Context/LLM adapter 연결, 100 Prompt/30 coding task의 근거 있는 eval·누출 시험 |
| S11-BE/DB/ST | Linux/PostgreSQL/Docker 합성 concurrency·crash·mTLS·권한 시험 | 장시간/부하/분할·스토리지 손상/용량·운영 migration/restore/rollback과 조건별 SLO 집계 |
| S12-BE | 설치 가능한 Python package, portable Node 빌드, 명시적 시작 config | 실제 설치·upgrade·rollback·5대 종단 여정·운영자 교육/인수 및 모든 선행 reviewer 승인 |

## 이어서 실행할 순서

1. 현재 control-integration을 같은 SHA의 CI·원본 Evidence·Obsidian 보고·draft PR로 전달한다. [[Codex 교차 코드 검토 - 인증과 실측 Evidence 정합성]]의 P1은 원 owner 수정 대상으로 유지한다.
2. Codex는 durable dispatch queue와 crash 뒤 observation 전환, 자동 cancel/reconcile의 권한·무결성 경계를 구현한다. 원격 실행 여부가 불확실하면 자동 재실행하거나 Lease를 반환하지 않는다.
3. Storage publication/pin/GC 및 Step/checkpoint 복원 계약을 확장한다. backend product 선택과 업무 adapter는 owner와 명시적으로 연결한다.
4. Claude/Gemini는 검토 오류 수정과 실제 API 연결을 각각 소유한다. UI의 고정 SLO·교육·Smoke·인수 flag는 개발 fixture이며 합격 Evidence로 승격하지 않는다.
5. 실제 IdP/CA/DNS/장비/저장소 값이 확인되면 실장비 검증을 실행한다. 현재 조회하지 못한 값을 임의 CA·IP·GPU 정보로 대체하지 않는다.

운영 정보와 타 Agent 독립 검토 없이 모든 Sprint done을 선언할 수 없다. 기존 사용자 승인 아래 로컬 구현·시험·commit/push/report는 계속 수행 가능하다. 운영 배포·자격 증명 변경·기존 데이터 파괴 작업은 실제 대상과 영향이 확정됐을 때 별도 critical 경계로 판단한다.


## Durable dispatch 후속 반영

[[2026-09-10_02-47-29_KST_DURABLE-DISPATCH_Codex_검증보고]]에서 claim/permit 원자 queue와 자동 전달·취소·관찰 worker를 구현/CI 검증했다. 위 S04/S06/S07의 dispatch daemon 항목 중 이 경계는 확보했으며 workflow enqueue adapter·heartbeat poll/sweep·Storage/Checkpoint·실장비 및 독립 검토는 남아 있다. 실제 운영 구성에 필요한 5대 PC 접속/IdP/CA/DNS/Storage 정보는 사용자에게 비밀을 제외한 값으로 요청했다. 답변 전 임의 운영 값을 만들지 않는다.
