---
doc_id: "GOV-DOC-CHECK-COVERAGE-001"
title: "check_docs 커버리지와 갭 — 오늘 겪은 문서 문제의 자동화 가능/사람 몫 분류 + single-source 검사 신설(report-only)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
mapped_at_tip: "ed7e51b4"
updated: "2026-09-22"
source_of_truth: "Git"
tags: ["governance", "check-docs", "doc-quality", "automation", "single-source"]
---

# check_docs 커버리지와 갭

오늘 우리가 고친 모든 것은 한 경로를 거쳤다: 고치면 같은 형태를 전수로 찾고, 검사로 바꾸고, 그 검사도 양방향으로 판정했다(하드코딩·계약 미결속·읽기쓰기 비대칭·합성데이터·죽은 방어). **문서만 그 경로를 안 거쳤다.** 오늘 문서에서 겪은 문제를 그 경로에 넣는다.

## check_docs가 지금 검사하는 것 (tip `ed7e51b4` 소스 확인)
1. `docs/sources` 원본 해시 불변(source-manifest).
2. 비밀 DSN 미노출(문서·`.env.example`·deploy 스크립트).
3. 위키링크가 **존재하는 대상**을 가리키는지(파일명/stem 매칭).
4. `doc_id` 유일성.
5. 프런트매터 필드 **존재**: title·version·status·author·**updated**·source_of_truth.
6. task-registry 무결성: 48/12 baseline(하드코딩), 필수 필드, self-review, owner 유효, Frontend 소유, status enum, contract/skill 참조 존재, acceptance 추적, 의존 DAG(순환), outcome 매핑, sprint별 area 커버리지.

즉 **레지스트리 무결성 + 프런트매터 존재 + 링크 해소 + 비밀 + 원본 해시**에 두껍고, **문서 본문의 내용 정합엔 얇다.**

## 오늘 겪은 문서 문제 → 잡히나?
| 문제 | check_docs가 잡나 | 분류 |
|---|---|---|
| (b) `updated` 필드 누락 | **잡힘**(프런트매터 필드 존재 검사) — 오늘 그래서 보완이 필요했다 | 이미 커버 |
| (a) 정정이 인계 섹션에 반영 안 됨(같은 결론이 갈라짐) | 못 잡음(링크 해소만, 내용 정합 아님) | **갭** |
| (d) 미검증 항목이 두 문서에 흩어짐 | 못 잡음 | **갭**((a)와 같은 뿌리=rule 5) |
| (c) 문서가 주장하는 숫자가 실제와 다름(워크트리 46 vs 47) | 못 잡음(숫자가 무엇을 세는지 모름) | **갭** |
| 링크가 대상의 실제 내용과 안 맞음 | 부분(존재는 잡음, 내용은 못 잡음) | **갭** |

## 자동화 가능 vs 사람 몫 (판정 근거)
- **(a)/(d) 같은 결론 중복 → 자동화 가능(단 report-only)**: "같은 문장이 여러 곳"은 텍스트로 찾을 수 있다. **신설했다**(아래). 하드 게이트 불가 이유는 측정으로 확정: 이미 살아있는 문서에 실질 중복 라인 ~111개가 있고, 대부분 **의도적 구조**(agent 작업 현황 계열이 전체 개발 진행 현황·검증 상태 지도에 상태를 복사)다. 게이트로 하면 기존 백로그에서 즉시 실패하고, 순수 텍스트로는 정당한 인덱스 요약과 분기 위험 복사를 못 가른다. → **advisory(사람 triage)**.
- **(c) 숫자 vs 실제 → 자동화 불가(일반)**: 숫자가 무엇을 세는지 알아야 한다. 워크트리 개수는 저장소에 있지도 않다(`git worktree`는 런타임 상태). 좁은 부분집합(레지스트리에서 셀 수 있는 "48 tasks" 등)만 가능하나 취약·저가치. → **사람 몫**(작성 시 실측 대조). 오늘 46 vs 47은 Claude가 우연히 잡음 — 그 우연을 규칙으로 못 바꾼다.
- **링크 내용 정합 → 자동화 불가(일반)**: 대상 내용의 의미 이해 필요. 존재-검사는 이미 있음. → **사람 몫**.

## 신설: `tools/check_doc_single_source.py` (report-only) — (a)/(d) 대응
- **무엇**: 살아있는 vault 문서(날짜 스냅샷·검증보고·frozen sprint 제외)에서 **실질 라인(≥80자, 프런트매터·헤딩·표·인용·코드·링크footer 제외)이 2개 이상 문서에 그대로 복사된 것**을 찾아 **doc-pair 단위로 요약**한다("A ↔ B: N개 공유 → 통합하거나 인덱스 요약임을 확인"). **항상 exit 0**(advisory, CI 안 세움).
- **왜 report-only**: 위 측정(기존 ~111 중복, 구조적)이 근거. dead-contract WARN과 같은 등급 — 탐지는 확실하나 해소는 사람 판단(통합 vs 인덱스 요약 수용).
- **양방향 확인(오늘 기준)**: `tests/test_doc_single_source.py` 5통과 — 복사된 라인을 **잡고**(117자 planted), 고유·짧은·boilerplate·날짜제외·프런트매터 라인은 **안 잡는다**. report-only도 무게를 져야 한다.
- **실 vault 결과(advisory)**: 111 중복 라인, **18 doc-pair가 ≥3 공유**. 최상위: `Codex 작업 현황 ↔ 전체 개발 진행 현황`(45), `Codex VF 작업 현황 ↔ Codex 작업 현황`(43), `검증 상태 지도 ↔ Codex 작업 현황`(19). = 정확히 오늘 (a)/(d)의 형태(상태 문서 계열이 서로 복사 → 하나 갱신 시 나머지 분기). 소유자 triage 대상.
- **배선**: docs.yml에 `check_contract_bindings`/`check_frontend_integrity`와 함께 추가하면 되나 **YAML은 Codex 소관** — report-only라 게이트 안전. 문안: `- run: python tools/check_doc_single_source.py`.

## 남은 사람 몫 (자동화 불가, 명시)
- (c) 문서 숫자 vs 실제: 작성 시 실측 대조(예: "워크트리 N개"는 `git worktree list`로 확인 후 기재). 규칙화 불가.
- 링크가 대상 내용과 맞는지: 정정 시 대상 문서까지 열어 확인(rule 3).
- 인계/다음-행동이 이미 완료된 것을 가리키는지(intra-doc staleness): 세션 종료 시 인계 섹션 갱신(rule 5 자기적용).

관련: [[2026-09-21_유도처방_한계_내산출물_재점검_Claude]] · [[계약검증_자동화대판단_검사목록]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
