---
doc_id: "CLAUDE-S01-SOFTWARE-PEER-REVIEW-CONSOLIDATION-001"
title: "S01 소프트웨어-범위 peer review 통합 (reviewer Claude) + S01-DB 증거 체크리스트 (owner Codex 기록용)"
status: "review"
version: "1.0.0"
author: "Claude (reviewer)"
owner: "Codex"
scope: "SOFTWARE ONLY — 운영(실 IdP/CA/DNS)·물리 장비·hosted CI·실 PostgreSQL 실행은 이 검토 범위 밖"
based_on_tip: "93d2f506 (origin/integration)"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S01", "peer-review", "consolidation", "software-scope", "evidence"]
---

# S01 소프트웨어-범위 peer review 통합

> **⚠ 범위 경계 — 전체 승인 아님.** 내가 검토한 것은 **소프트웨어**다: 소스·계약·시험(내 손 실행분과 구조 열람분). **검토하지 않은 것**: 실 IdP/CA/DNS 연결, 물리 장비(5대) 인수, hosted CI 실제 가동, 실 PostgreSQL 실행(아래 명시된 곳 외). 이 문서를 **S01 전체 done 근거로 읽지 말 것** — S01 DoD의 운영·장비·실PG 부분은 별도 증거가 필요하다. (오늘 밤 내내 지킨 규율: 확인한 것보다 넓게 말하지 않기.)

S01 과제(BE/DB/ST)의 요구 증거 중 하나가 **설계 검토(peer review)**인데, 오늘 밤 내가 Codex 기반물을 여러 번 검토한 결과가 History 여러 문서에 흩어져 한자리에 없어 S01 증거로 안 잡혔다. 여기 묶는다. **실제로 한 것만, 각 문서의 확인/미확인 경계 그대로, 새로 넓히지 않는다.**

## 오늘 밤 검토 (내 손) — 확인한 것 / 확인 안 한 것
1. **쓰기응답 재판정 + PG 실측 거동** ([[2026-09-22_Codex_쓰기응답_재판정과_PG검증_독립검토_Claude]])
   - 확인: 부재 주장(상위 미결 없음) 성립 — saintvision /v1 쓰기면 **전수 열람**(origin 참조); 비-DB 계약시험 **33 passed(내 손)**; 거부시험이 `status_code==500` 단언 구조 = response_model 없으면 깨짐(무게); 착지 앵커 존재(nodes.py:49, storage.py:68); PG-skip 보호 **배선** 확인(conftest CI-fail + junit no-skip, addopts `-ra` 가시).
   - **확인 안 함**: 실 PG 실행(오늘은 Codex 일회용 컨테이너로만); CI 실제 가동(gh 미인증); 범위=saintvision /v1(커널/control-plane 쓰기면은 별도 트랙).
2. **contribution lifecycle 비대칭 + workspace tool 결속** ([[2026-09-22_Codex_contribution_lifecycle_workspace_tool_결속_독립검토_Claude]])
   - 확인: activate/revoke가 register와 같은 모델로 결속(대칭 회복); workspace tool 모델이 내 좁힌 타입 재사용·readiness=`Literal["unknown"]` 정직; 모델↔return 본문 일치; **65 passed(내 손)**; 무게(거부시험 구조).
   - **확인 안 함**: 실 PG 경로(DSN 부재); 프런트 소비자(검색상 없음).
3. **Run 재시도 부재 감사 + 저위험 쓰기 7결속** ([[2026-09-22_Codex_재시도부재_및_저위험7결속_독립검토_Claude]])
   - 확인: 재시도 부재 성립 — 상태기계(0001_core·0018)에 `failed→*` 전이 없음(failed 종단), ModelRetry/ShardRecovery 제품 미배선(**내 손 grep**), 갈래 distinct, 놓친 표면 없음; 저위험 7 결속 정확+무게(**19 passed 내 손**, anchor invariant가 detach 감지); 내 저위험 분류 확인.
   - **확인 안 함**: 실 PG 실행(skip); DB-경로 되돌림(Codex 보고 수용); CI live; 정적 감사라 외부 배포 wrapper 미확인.
4. **규칙 7 후속** — 성격 정정: 이건 **내가 Codex 코드를 검토한 게 아니다.** Codex가 내 canon 규칙 7에 반대(외부/확장 코드값 예외)를 냈고 **내가 정본을 수정**한 것이다(양방향). peer-review-of-Codex-code로 세지 않는다. 기록: [[검증규칙과_세축_canon]] 규칙 7(v1.2.1).

## 이전 세션 소프트웨어 검토 (문서 있음 — 여기서 재요약/재승인 않음, 링크만)
아래도 내가 실제로 수행해 문서화한 S01-기반 소프트웨어 검토다. **여기서 내용을 재특성화하지 않는다**(넓히지 않기) — 각 문서의 경계가 정본:
[[2026-09-22_Codex_artifact_content_결속_독립검토_Claude]] · [[2026-09-21_discovery_tenant_enforcement_독립검토_Claude]] · [[2026-09-21_운영자자격증명발급_독립검토_Claude]] · [[2026-09-21_Codex착지_마이그레이션head_Legacy제거_node결정_독립검토_Claude]] · [[2026-09-22_Codex_appliedToKernel_신선도시각_독립검토_Claude]].

## 종합 (소프트웨어 범위)
위 검토들에서 **소프트웨어 결함으로 미해소된 것 없음**(각 건 승인, 경미 잔여는 착지·인계 완료). 단 이는 **소프트웨어 판정**이며, 실 PG 실행·운영 연결·물리 장비·hosted CI 인수는 **내 검토에 포함되지 않았다**. S01 done은 그 별도 증거가 서야 한다.

---

# S01-DB 증거 체크리스트 (owner Codex 기록용 — 내가 그 doc은 안 고침)
S01-DB는 **물리 장비 의존이 없어** 셋 중 닫기에 가장 가깝다. 요구 증거(계약검증/설계검토/인벤토리보고)별 있음·어디·없음:

| 증거 | 있음? | 어디 | 없는 것 |
|---|---|---|---|
| 계약 검증 | ✅ 소프트웨어분 | tests/core 계약시험 · `export_schemas --check`(56) · `check_contract_bindings`(46/12) · `contracts:check`(16) · CI-스코프 백엔드 **1622 passed @`0b7d51ed`** | **실 PG 실행 증거**(로컬 skip 1008). ← **사용자 대기 아님**: Codex 현재 실PG 복제본 전이 작업 + CI 첫 실행이 채움 |
| 설계 검토 | ✅ 소프트웨어분 | 마이그레이션 **단일 head 0045**(`migration_graph.py`, reversible-tail) · 상태기계/DB CHECK 도메인 전수(retry 검토) · ID 스킴(`new_id`) · **이 peer-review 통합 문서** | 전용 **ERD 문서 없음**(설계는 contract_ref "DB 최종 개발 계획"에). DoD가 standalone ERD를 요구하면 그건 미작성 |
| 인벤토리 보고 | ✅ | schema·ID·state 인벤토리(위 소스·문서) | — |
| (기록) | ⚠ stale | Codex 합격증거 doc의 `migrations 0001~0006` | **실제 0045로 갱신 필요**(내가 그 doc 안 고침 — owner 기록) |

**S01-DB 닫는 길**: (a) 위 기록 갱신(0001~0006→0045, 오늘 계약 스위트 첨부) + (b) 이 peer-review 통합 + (c) **실 PG 실행 증거**(Codex 현재 PG 작업·CI 첫 실행 — **사용자 물리 입력 대기 아님**). ST와 달리 **장비 값 없이 닫힘 경로가 있다.** closing은 (c)가 서면 **Codex(owner)가 절차대로.**

## Codex 실 PostgreSQL 실행 증거 (2026-09-22)

- **대상**: `tests/test_pools.py` 전체 34건. 앞서 DSN 부재로 34건이 skip 되었던 S05/S07 배치·lease 경로를 실제 PostgreSQL에서 재실행했다.
- **기준**: integration 작업 트리 `codex/integration-merge`, 실행 HEAD `a8c979d0e87262a3cf215ddc5d136ec7c6d14cf6`, 워킹 트리 clean 확인 후 실행.
- **명령**: `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe -m pytest -q tests/test_pools.py --tb=short`
- **실행 시각(KST)**: 2026-09-22 08:27:11 시작, 08:27:33 종료. **인터프리터**: `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe`. **exit code**: `0`.
- **결과**: `34 passed, 0 failed, 0 errors, 0 skipped` (21.07초). Alembic 경고 1건은 실패가 아닌 deprecation warning이다.
- **환경**: 소유 라벨 `ai.saintvision.owner=codex`, 작업 라벨 `ai.saintvision.task=s05-pools-pg`를 붙인 일회용 `postgres:16` 컨테이너를 사용했다. 데이터 디렉터리는 anonymous volume 대신 tmpfs였고, synthetic 자격증명은 실행 환경에만 주입했다.
- **정리**: 실행 전후 Docker 자원은 containers 48→48, volumes 79→79, networks 11→11이었다. 라벨을 JSON inspect로 확인한 뒤 해당 컨테이너만 제거했으며 잔여 컨테이너는 0개다.
- **범위**: 이 결과는 `test_pools.py`의 실제 PostgreSQL 경로가 현재 SHA에서 통과했다는 증거이며 S01-DB의 실 PG 증거 공백을 채운다. 독립 검토, hosted CI 실행, 운영 인수 및 물리 장비 검증까지 완료했다는 뜻은 아니다.

관련: [[2026-09-22_S01_기반셋_왜안닫혔나_검토_Claude]] · [[Codex 잔여 개발 작업과 합격 증거]] · [[사용자_결정대기_브리프_2026-09-22]].
