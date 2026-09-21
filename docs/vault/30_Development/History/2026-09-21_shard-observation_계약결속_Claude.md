---
doc_id: "CLAUDE-SHARD-OBSERVATION-CONTRACT-001"
title: "ShardObservation 계약 결속 — VF-GM-04 관측/합성 구분 기준 (앵커 없음: Codex flag)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
frontend_owner: "Gemini"
updated: "2026-09-21T20:10:00+09:00"
timezone: "Asia/Seoul"
bound_at_sha: "2c473f4"
source_of_truth: "Git"
tags: ["contract-binding", "shard", "VF-GM-04", "anchor-gap"]
---

# ShardObservation 계약 결속 (shard 우선 — VF-GM-04 언블록)

내 범위 = node·shard·workspace View/Result 응답(사용자 지정). shard 우선. terminal은 Codex(보안 경계).

## 3점 확인 (앵커·소비·겹침)
- **소비(엄격, 호출경로)**: `apps/web/src/features/runs/RunDetail.tsx:93,150`이 `fetchShardObservation(...).then(shardRows)`·`shardRefreshNotice(result)`를 **실제 호출**(import/주석 아님). 엔드포인트 `/v1/projects/{p}/runs/{runId}/shards`.
- **앵커(코드 확인)**: `app.py:466 → control.py:151 shards() → shards.py ShardRuntime._status()`가 응답을 만든다. **`_status`는 `validate_contract("ShardObservation", ...)`를 호출하지 않는다** → run-result류와 달리 **백엔드 앵커 없음**. (control.shards는 입력 RunId만 검증.)
- **겹침**: shard 계약 결속은 내 지정 범위. `shards.py`는 ShardRuntime 복구·동시성 런타임(Codex 고난도 레인)이라 **그 파일은 수정하지 않음** — 결속은 fixture+시험만 추가.

## 내가 결속한 것 (SHA 2c473f4 위)
- `contracts/fixtures/shard-observation-response.json` — "succeeded" 관측(parent 있음, shard 1, resultManifest present)에 충실. (fixture 검증이 내 실수 포착: `resultManifest[].objectId`는 스키마 `format:uuid` — uuid로 정정.)
- `tests/core/test_shard_observation_contract.py` — **5 passed**: fixture↔계약 · **envelope 13필드 load-bearing** · **ShardObservedMember 6필드 load-bearing** · **ShardResultMember 6필드 load-bearing** · member.state는 RunState enum 강제.
- 양방향: Python `validate_contract`(VAL-0002) + 일회용 Ajv(`#/$defs/ShardObservation`) 3레벨 전부 + enum 거부.

## VF-GM-04 (Gemini): 무엇이 관측된 것인가
계약이 **관측 shape를 확정**한다 — UI가 지어내면 안 되는 경계:
- `ShardObservedMember`가 주는 것: `index, runId, nodeId, phase, state, evidenceId(nullable)` **그게 전부**. **per-member attempt·resource-release·healthy replica·복제본 목록은 이 응답에 없다**(shardObservation.ts 주석도 "not supplied by this view"). `shardRows()`가 `verified`/`physicallyStopped`를 phase/state/evidenceId에서 **파생**하는 건 관측이 아니라 계산이다 — 관측 안 된 복제본/샤드를 합성하지 말 것.
- `evidenceId`가 **null이면 미관측**(계약상 nullable+required). null을 "healthy"로 합성 금지.
- **미미한 TS 드리프트**(정렬은 대체로 양호): 프런트 `ShardObservation`에 계약에 없는 초과 필드 `items?`/`total?`(계약 additionalProperties:false → 백엔드가 절대 안 보냄, 참조하면 항상 undefined); `ShardObservedMember.phase`를 3값(`queued|uncertain|stopped`)으로 좁힘(스키마는 string) — 백엔드가 다른 phase 보내면 타입 위반. 정리 권장.

## 인계
- **Codex**: `ShardRuntime._status()`가 서빙 응답을 `validate_contract("ShardObservation", result)`로 검증하지 않음(앵커 갭). shards.py(복구·동시성)는 Codex 레인 — 그 return 직전에 앵커 추가하면 run-result류 양면 결속 완성. 이 문서의 fixture가 그대로 회귀 기준.
- **Gemini**: 위 VF-GM-04 경계 기준. 필요 시 `shard-observation-response.json` 프런트 Ajv 시험 추가.
- 공유 진행판에 범위 기록(node/shard/workspace=Claude, terminal=Codex) — 이 커밋에 함께.

관련: [[2026-09-21_수기타입_계약_드리프트_전수훑기_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
