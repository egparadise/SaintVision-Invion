---
doc_id: "CLAUDE-S01-EVIDENCE-RECORD-HANDOFF-001"
title: "S01-BE·S01-ST 증거 기록 갱신 — Codex(owner) 인계 1쪽: AC-01 증거별 현재 증거(경로·SHA·run)·부족분·갱신 항목·task-registry 필드 대응 (값 미기재)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
audience: "codex"
updated: "2026-09-22T21:15:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S01", "evidence", "handoff", "codex", "AC-01", "task-registry"]
---

# S01 증거 기록 갱신 — Codex 인계

[[2026-09-22_S01-BE_S01-ST_잔여_합격조건표_Claude]] "우리 몫 1"(증거 기록 갱신, owner Codex). 목적: registry `S01-BE`·`S01-ST`(둘 다 `in_progress`, owner Codex, reviewer Claude, `evidence_required` = 계약 검증·설계 검토·인벤토리 보고, `acceptance_ids` = AC-01)의 **기록이 실제 증거보다 뒤처진 부분**을 Codex가 한 번에 갱신할 수 있게, 증거별 현재 위치와 부족분을 표로 준다. **판정·닫힘은 하지 않는다**(self-close 금지; 외부 대기 U1~U6는 그대로). 값(DSN·비밀·장비 값)은 적지 않는다.

## 1. Codex가 갱신할 기록 (무엇을·어디를)

| # | 기록 위치 | 현재 상태(stale) | 갱신 내용 | registry 필드 |
|---|---|---|---|---|
| R1 | [[Codex 잔여 개발 작업과 합격 증거]] S01-BE/DB/ST 행 | "migration head **0045**" | head **0046**(`0046_model_manifest_readiness`, `4473c7f1`); 계약 스위트·hosted 결과를 "확보" 열에 첨부(§2 표의 SHA·run) | — (문서) |
| R2 | 같은 문서 "남음" 열 | "실장비 5대·허용 폴더/자원·IdP/CA/DNS·Storage 제품 선택·peer review" | **peer review는 완료**([[2026-09-22_S01_소프트웨어_peer_review_통합_Claude]], `8b20d3e6`) → 제거; 외부 대기는 U1~U6 번호로([[S02_선행입력_체크리스트_2026-09-22]]) | — |
| R3 | `docs/task-registry.json` `S01-BE` | `next_handoff: "Claude"` | 소프트웨어 증거 검토는 끝났으므로 `next_handoff`를 **사용자 입력 대기(U2·U3·U4)** 를 뜻하는 값으로(예: `"user-input:IdP/CA/DNS"`) — 필드 어휘는 Codex/Orca 규칙에 맞춤 | `next_handoff` |
| R4 | `docs/task-registry.json` `S01-ST` | `next_handoff: "Claude"` | 동일하게 **U1·U5·U6 대기** 표기; 인벤토리 표 양식([[S01_물리노드_인벤토리_표양식_2026-09-22]]) 착지 사실을 `scope`/증거 설명에 반영 | `next_handoff`, (`scope` 설명) |
| R5 | `Codex 작업 현황` S01 카드 | — | 위 R1~R4 반영 사실 + 갱신 SHA 한 줄 | — |
| R6 | ontology | registry status 무변경이면 재생성 불필요 | status를 바꾸지 않는다(둘 다 `in_progress` 유지) → `check_ontology` 영향 0 | `status` 불변 |

`check_docs`(registry 48 tasks·DAG)와 `check_ontology`(registry 유도)를 갱신 후 돌린다. status를 바꾸지 않으므로 ontology 재생성은 필요 없다.

## 2. AC-01 증거별 현재 증거 (경로·SHA·run) — 두 과제 공통

| 요구 증거 | 과제 | 현재 증거 | SHA / run | 부족분 |
|---|---|---|---|---|
| 계약 검증 | BE | 정본 schema `contracts/v1alpha1/core.schema.json` + 생성 TS/Go/Python 동기; `tools/check_contract_bindings.py` PASS(52 fixture·17 응답 타입·20 앵커·12 replay); `export_schemas --check`·`contracts:check` 16 | tip `7e50296c`; hosted Backend success run **35723589663**(7e50296c), Core success **35719185379**(8bd53c70) / PR #59 Core **35720205341**(3100/3065/35/0) | 없음(기록만 stale) |
| 계약 검증 | ST | Contribution/DataLocation/StorageObservation 결속·좁힘, artifact-content `X-Content-SHA256` | [[2026-09-22_S03_DB_실PG증거_및_ST_정본결정게이트_Claude]] `9930195a`; Evidence `lan-storage-readiness-f2a7fbc*` | 실제 Storage 제품 왕복(U6) |
| 설계 검토 | BE | Codex 기반물 독립 검토 consolidate(쓰기응답·contribution·artifact-content·discovery tenant/자격증명·migration head·retry) | [[2026-09-22_S01_소프트웨어_peer_review_통합_Claude]] `8b20d3e6`; [[2026-09-21_운영자자격증명발급_독립검토_Claude]] `54cb7f68` | 없음 |
| 설계 검토 | ST | URI 리졸버·보존 정책·정리 도구 검토 | `2026-09-22_PITR_보존7일_정리_dry-run_실측_dev_PG_Claude.md`(PR #56, 병합 전) · [[VF-CL-04 replica 복구와 PITR 운영 runbook]] v1.2.0 | 실 아카이브 정리 실행(Tier-A 활성 후, 결정 B) |
| 인벤토리 보고 — 개발 환경 | BE | 로컬 개발환경 구성·검증 | [[2026-09-11_DEV-ENV_Codex_로컬개발환경구성과검증]] `8dd1777a`; 새 PC 이전 [[개발환경_이전_절차서]] | 없음 |
| 인벤토리 보고 — 권한 경계(소프트웨어) | BE | RLS·NOLOGIN·tenant 격리·운영자 발급 검토; 0046 DEFINER ACL 조회 | `54cb7f68`; `2026-09-22_Codex_카드2_실행Manifest관측_model-retry_F1_독립검토_Claude.md`(PR #58, 병합 전) | **실 IdP/CA 연결(U2·U3·U4)** |
| 인벤토리 보고 — 장비 5대 | ST | **표 양식만**(값 없음, 미확인 열) | [[S01_물리노드_인벤토리_표양식_2026-09-22]] (PR #55 병합, `04d42ee5`) | **U1·U5 값 전부** |
| 인벤토리 보고 — 허용 폴더/자원·Storage 제품 | ST | 계약·정책 문서만 | [[Codex Node 저장소 설정 설치와 교체 절차]] | **U5·U6** |
| 5노드 조사표의 미확인 값 명시(AC-01 기준) | BE·ST | 표 양식의 ☐/☑ 열 | 위 양식 | 값 입력 전이라 전부 ☑ — 이것이 "미확인 값 명시"의 현재 형태 |

## 3. 부족분 요약 (갱신으로 닫히지 않는 것)
- BE: U2 IdP·U3 CA·U4 DNS 실연결 → 체크리스트 §1~§3 성공 신호 실측 후에야 done 후보.
- ST: U1 토폴로지·U5 장비 5대·U6 Storage 제품 → §0·§4·§5.
- 기록 갱신(R1~R5)은 **한 일이 숫자에 잡히게** 하는 것이지 done 처리가 아니다.

## 4. 순서
R1·R2(문서) → R3·R4(registry, status 불변) → `check_docs`·`check_ontology` exit 0 → R5 → PR(reviewer Claude). 이 문서는 인계 후 Codex 갱신 커밋 SHA를 §1 표에 적어 닫는다.
