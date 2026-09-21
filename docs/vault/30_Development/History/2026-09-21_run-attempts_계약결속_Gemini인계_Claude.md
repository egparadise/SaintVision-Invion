---
doc_id: "CLAUDE-RUN-ATTEMPTS-CONTRACT-GEMINI-HANDOFF-001"
title: "run-attempts(RunAttemptList) 계약 결속 — Gemini 프런트 배선 인계 + 드리프트 4종"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
frontend_owner: "Gemini"
updated: "2026-09-21T18:40:00+09:00"
timezone: "Asia/Seoul"
integration_tip_at_write: "d438db8"
source_of_truth: "Git"
tags: ["contract-binding", "run-attempts", "gemini-handoff", "drift"]
---

# run-attempts(RunAttemptList) 계약 결속 — 내가 한 것 + Gemini 인계

run-result/run-logs와 **동일 패턴**. 계약+fixture+Python+양방향 Ajv까지 내가, **프런트 배선은 Gemini**.

## 내가 결속한 것 (검토 SHA d438db8)
- `contracts/fixtures/run-attempt-list.json` — 커널 `attempts()` "출력 있음" 케이스(envelope 5필드 + attempt 1건, 아이템 8필드 전부).
- `tests/core/test_run_attempt_contract.py` — **4 passed**: fixture↔커널계약(`validate_contract("RunAttemptList")`; 커널 `result_view.attempts()`의 `_checked` 그 검증) · envelope 5필드 load-bearing · **attempt 8필드 load-bearing**(계약 richness가 여기 있음) · source const.
- 변형 **양방향**: Python `validate_contract`(VAL-0002) + 일회용 Ajv(`#/$defs/RunAttemptList`) 둘 다 envelope 5 + 아이템 8 + source const 위반 거부.

## 정정 (추측→실측)
이전 인계에서 "agentEngine/recoveryEngine이 라이브 소비 → run-logs보다 위험"이라 적었으나 **오판**이다. 그 grep 매치는 **주석의 단어 'attempts'**뿐이었다. 실측: `RunAttemptList`/`RunAttemptItem` 타입은 `types.ts`에 **정의만 있고 사용처·fetch 어댑터 없음**(RunLogView와 동일 dormant). 즉 지금 당장 오동작은 없고, 소비 배선 시점에 계약이 잠긴 상태가 된다. — 규칙: `empty-output-is-not-evidence` / 소비처 없음도 "무엇에 대한 없음"인지 실측으로 확정.

## 실측 드리프트 — 종류별 (각각 다르게 깨진다)
프런트 수기 `RunAttemptList`(types.ts:584)·`RunAttemptItem`(:573) vs 계약 `RunAttemptList`·`RunAttemptObservation`.

**(a) const 무력화** — 아무 문자열 허용:
- `source: 'execution-kernel' | string` → `| string`이 const 제약을 죽임. (RunAttemptList)

**(b) required → optional** — 계약은 항상 존재, 타입은 없어도 TS 통과(모의가 필드 빠뜨려도 안 걸림):
- envelope `nextCursor?:` (계약 required)
- item `commandId?:` `stopReceiptId?:` `exitCode?:` `reason?:` `evidenceId?:` (계약 5개 모두 required)

**(c) 필드 누락** — **이 종류 없음**(계약 필드가 전부 타입에 존재). "없음"의 범위: RunAttemptList/RunAttemptObservation 필드 전수 대조 기준.

**(d) nullability 좁힘 — 역방향, 가장 위험** — 계약은 `null` 허용(+required)인데 타입은 non-null:
- item `startedAt: string` ↔ 계약 `Timestamp | null`
- item `nodeId: string` ↔ 계약 `NodeId | null`
→ 백엔드가 정당하게 null 반환(시작 전 attempt=startedAt null, 노드 미배정=nodeId null)하면 **프런트 자기 타입이 위반**되어 string 가정 코드가 오동작/크래시. (b)는 프런트가 느슨해 백엔드 계약이 거부하는 방향, (d)는 **프런트가 부당히 엄격해 실제 null에 깨지는** 방향 — 반대다.

(부가) 이름 갈림: 계약 아이템은 `RunAttemptObservation`, 프런트는 `RunAttemptItem`(같은 shape, 다른 이름).

## Gemini 인계 (프런트 배선)
1. `types.ts`의 `RunAttemptList`/`RunAttemptItem`을 계약과 일치: `source` const, `nextCursor`/`commandId`/`stopReceiptId`/`exitCode`/`reason`/`evidenceId` required로, **`startedAt`/`nodeId`를 `| null`로**(가장 중요 — 실제 null 대응). 또는 생성 타입(`packages/contracts-ts`) re-export.
2. `/attempts` 소비 어댑터 신설(현재 부재). run-result 어댑터 형태.
3. 프런트 Ajv 계약 시험: `run-attempt-list.json`을 `#/$defs/RunAttemptList`에 대조 + envelope/아이템 필수필드 음성대조.
4. **고치기 전 통과 / 고친 뒤 실패 양쪽을 보일 것**(특히 (d): 프런트에 `nodeId:null` 케이스를 넣어 수정 전 타입이 못 잡고 수정 후 잡는지).

## 겹침/담당
- Codex worktree(execution/result-observation/runtime-completion) attempt 관련 dirty 없음 — 비겹침. attempts는 result-observation = 내 레인.
- 공유 진행판 담당 기록은 Gemini 편집 중(dirty)이라 미기입 — **run-attempts=Claude(계약)/프런트=Gemini** 항목 Gemini 착지 후 반영 요.

관련: [[2026-09-21_run-logs_계약결속_Gemini인계_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
