---
doc_id: "HIST-CLAUDE-KERNEL-WRITE-AUDIT-REVIEW-001"
title: "독립 검토 — Codex 커널 쓰기면 감사(a2dada9a): 28 완전·위험 실재·replay 앵커는 무게 없음(발견)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["independent-review", "codex", "kernel-write", "control-plane", "response-contract", "vacuous-anchor", "finding"]
---

# 독립 검토 — 커널/control-plane 쓰기 계약 감사 `a2dada9a`

어젯밤 내 쓰기 응답 검토는 `saintvision` v1 범위였고 커널은 별도 트랙이라 아무도 안 봤다. Codex가 그 면을 감사(28 라우트 전수·위험 판정·앵커 보강)했고, 이를 세 기준으로 독립 검토한다: (1) 28이 전부인가, (2) 위험 판정이 맞는가, (3) 결속이 무게를 지는가. Codex 큐 밖(검토는 내 역할).

## Provenance

- 검토 대상: `a2dada9a`(코드·계약) + `f0d782b8`(SHA 기록), 통합 tip 검토 시 `5180a737`(그 뒤 "contract business lock release response"가 얹힘). 둘 다 tip 조상 확인.
- 소스 읽기 + **격리 워크트리(scratch, detach @5180a737)에서 변이 실측**. 인터프리터 `.venv/Scripts/python.exe`(py3.14.6, pytest 9.1.1), 실 PG `saintvision-lan-db`(16.14 @55440). 공유 워크트리는 세션 중 계속 이동(f0f0c790→…→0a02ada1)해 측정은 격리 트리에서 SHA 고정.

## Check 1 — 28이 전부인가 (부재 주장)

**전부다.** inv control-plane의 쓰기 메서드 데코레이터를 내가 전수 열거: `services/control-plane/src/inv/app.py`의 단일 `api` 객체에 **POST 27 + DELETE 1 = 28**, PUT/PATCH 0. `include_router`/`add_api_route`/2번째 FastAPI 앱 없음(grep 0). Codex의 28과 일치, 누락 없음.

## Check 2 — 위험 판정이 맞는가 (프런트가 실제로 부르는가)

Codex 근거("프런트가 runs·approval·workspace·terminal·node control을 직접 호출")를 apps/web에서 실측 확인:
- node drain/resume — `AdminSecurityConsole.tsx`
- runs 생성 — `DeveloperStudio.tsx`, `runApprovalObservation.ts`
- resume/prepare — `RunDetail.tsx`, `DeveloperStudio.tsx`
- terminal-tickets — `WebTerminal.tsx`, `terminalTicket.ts`
- checkouts/files — `workspaceEditObservation.ts`, `MonacoWorkspaceEditor.tsx`
- approval decision/challenge — `ApprovalReviewPanel`(진행판 기록)

즉 이 면이 내부 전용이 아니라는 판정은 옳다. **위험 이질성(정직)**: 28이 다 브라우저 대면은 아니다. 직접 호출 안 되는 것 — kill-switch, containment-approvals, git votes/apply/reconcile, bindings enqueue/reconcile/state, start/enqueue, resume/enqueue — 은 운영자 콘솔이거나 prepare 뒤 내부 연쇄다. Codex는 "새 ID/handle/전이/경로 반환 쓰기"에 고위험 기준을 **일률 적용**했다(보수적이라 방어적으로 타당). 다만 브라우저가 파싱하는 계약 위험은 위 호출 부분집합에 집중되고, 내부 연쇄분의 위험은 "다른 서비스/worker가 파싱"으로 실패면이 다르다 — 같은 무게로 뭉개면 어디를 먼저 지켜야 하는지 흐려진다.

## Check 3 — 결속이 무게를 지는가 (발견: replay 앵커는 무게 없음)

a2dada9a는 `validate_contract`를 **두 종류 경로**에 넣었다: (a) fresh 계산 결과, (b) **replay 분기**(`if prior is not None: validate_contract(...); return prior` — 저장된 이전 응답 재검증). 격리 워크트리에서 변이로 무게를 실측했다.

**baseline**(tip, 5개 서비스 통합 + 계약시험): **44 passed / 62 skipped**(skip=Linux business workspace·private storage 게이트), exit 0.

- **fresh 앵커 = 무게 있음**: `control.create`의 fresh `validate_contract("ControlRunView", result)` 한 줄을 제거하니 `test_run_creation_anchor_rejects_an_invalid_state`가 **KILLED**(DID NOT RAISE). Codex가 든 cancel-parent(`ControlRunDetail`, line 189)도 `test_parent_cancel_anchor`가 잡는다(무효 state 주입→거부). fresh 경로는 무효 응답을 초록으로 통과시키지 않는다.
- **replay 앵커 = 무게 없음(vacuous)**: `prior is not None` 직후의 `validate_contract` **12개 전부**(control create+cancel 2, containment 1, workspace_api 3, workspace_start 3, business_handoff 2, +기존 1) 제거 후 재실행 → **44 passed / 62 skipped, 그대로**. **아무 시험도 안 죽었다.** 저장된 **무효 prior**를 넣고 replay 분기가 거부하는지 확인하는 시험이 하나도 없기 때문이다. 즉 이 앵커들은 있지만 지키지 않는다.

**왜 중요한가**: 이건 오늘 내내 잡은 "있다≠작동한다"의 앵커판이고, 하필 **resume/재생·idempotency replay 분기**에 있다 — 어젯밤 재생이 검증을 우회하던 것과 같은 자리다. 앵커 자체는 계약 이전에 저장된 prior에 대한 방어로 타당하나, 기록("replay 누락 수정")과 게이트("14 bound kernel responses each have a serving-anchor test")는 이 replay 경로가 **지켜진다**고 읽히게 한다. 실제로는 replay 경로의 무게가 시험되지 않았다.

**이 호스트의 한계**: 62개가 Linux 게이트 skip이라, workspace/business의 replay 경로 상당수는 이 호스트에서 실행조차 안 된다. **Codex의 실 PG 실행도 같은 호스트면 이 갭을 닫지 못한다** — 실행이 아니라 "무효 prior를 심고 replay가 거부하는가" 시험이 없어서 생기는 갭이기 때문이다. 유효 prior만 태우는 실행은 앵커 제거와 구별되지 않는다.

**권장 수정**: 대표 서비스 하나 이상에 replay 무게 시험 추가 — ledger에 도메인 밖 상태를 담은 prior 응답을 심고, replay 분기 호출이 계약 오류를 raise하는지 단언(`test_parent_cancel_anchor`를 `prior` 경로로 옮긴 형태). 그러면 replay 앵커가 무게를 갖는다.

## Codex 실 PG 결속 결과 (대기 → 붙임)

Codex가 이 결속을 실 PostgreSQL로 돌리는 중이다. 결과가 오면 여기 붙인다. 위 예측대로 **유효 prior 실행은 replay 앵커의 무게를 보이지 못한다** — 결과가 무효-prior replay 거부 시험을 포함하는지로 판단한다.

## 판정 요약

- Check 1(완전성): **통과** — 28 전수 일치, 누락 0.
- Check 2(위험 판정): **통과, 단 이질성 주석** — 프런트 직접 호출 실재 확인, 일률 고위험은 보수적으로 타당하나 브라우저 대면 부분집합과 내부 연쇄분의 실패면이 다름.
- Check 3(무게): **발견** — fresh 앵커는 무게 있음, **replay 분기 앵커 12개는 이 호스트 실행 시험에서 vacuous**. 무효-prior replay 거부 시험 부재. 재생/replay 자리라 어젯밤 우회와 동류로 봐야 함.
