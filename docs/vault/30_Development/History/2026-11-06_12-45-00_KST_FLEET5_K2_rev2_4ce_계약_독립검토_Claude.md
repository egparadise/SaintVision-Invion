---
doc_id: "HISTORY-FLEET5-20261106-K2-REV2-4CE-CONTRACT-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 K2 rev2 4ce 계약 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T12:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "4ce63e8ee78d957aa91e813f6ee226cc21abb52a"
task_ids: ["FLEET5-K2-TRUSTED-PRODUCER-CONTRACT-20261106"]
tags: ["fleet5", "independent-review", "k2", "design", "claude"]
---

# K2 rev2 4ce 계약 delta 독립 검토

Orca `task_f8b0caa87c81`, dispatch `ctx_f0eed1630fd5`다. owner는 Codex `task_a95ef3d8ccce / ctx_ed23b4a777d0`다.

- Root 질문 `msg_ca431d7c508f`는 Root의 실제 결정 전까지 pending이다.
- 직전 실제 검토는 `5623dc00`/Docs `42150131952`다. 판정은 REVISION_REQUIRED(K2-M1·M2·M3, L1–L5)였다.
- Root 선택 `msg_6df22674ff19`와 결정 파일(sha256 `01b207cc…`)을 읽었다.
- 공유 정본 vault는 `d17ea2d3`의 후손 `aed226c2`에서 읽었다. Index 1.0.436, Claude 작업판 1.2.130이다.

**판정: BOUNDED_DESIGN_ACCEPT_FOR_K2A_TRUST_HISTORY_READINESS_ONLY.**

- rev2는 5623의 실제 지적을 닫았다. Root는 기본 거부 port를 쓰는 작은 read-only K2A-TRUST/HISTORY grant를 결정할 수 있다.
- **D-OBSERVATION attempt 계약은 아직 인수하지 않는다.** K2R2-M1(Medium)을 고친 뒤 따로 실제 검토해야 한다.
- K2A-CURRENT·ASSEMBLY, K2B effect, 설치, 운영도 인수하지 않는다.
- 검토자는 아무 grant도 하지 않았다. 실제 binding은 모두 NULL/HOLD다.
- **기계 판독 결과:** `Evidence/fleet5-k2-rev2-4ce-review-20261106-claude/review.json`
- **명령·exit·hash:** 같은 폴더의 `commands.json`, `local-doc-gates.txt`

## 대상 확인

- **대상:** `4ce63e8e`, branch `agent/codex/fleet5-k2-trusted-producer-contract-rev2-20261106`, parent `551d7312`.
  - remote ref가 같은 SHA다.
  - 추가 파일 50개다. 49개는 owner `rev2/` 아래, 1개는 owner History다. 551d 대비 수정·삭제는 0이다.
  - eb32 대비 services·packages·.github·tools·contracts diff는 0이다.
- **owner Docs:** `42155660700`, job `127689080244`.
  - exact head와 ref, `workflow_dispatch`, `.github/workflows/docs.yml`, attempt 1을 확인했다.
  - job은 docs 하나이고 success다. gh API로 읽기만 했다.

## 지적별 닫힘

- **K2-M1 — 명시 HOLD로 닫힘.**
  - PRESENT head에서 M2가 121초 지났거나 없으면 `ERR[OBSERVATION_AUTHORITY_HOLD]`다.
  - "K1 current where available" 문구는 rev2 MD에서 사라졌다.
  - ObservationRefreshAuthorization은 CurrentView와 분리된다. migration-observe와 terminal normal:3-observe는 parent가 다르다.
  - normal:3는 MigrationOperationID로 cast하지 않는다. 그런 요청은 `ERR[NORMAL3_K1_CURRENT_UNSUPPORTED]`다.
  - 현재 slot key는 eb32 원본과 같다. 원본 history는 다시 쓰지 않는다.
  - 한쪽 member라도 UNKNOWN이면 양쪽 모두 막힌다. lease 만료는 takeover가 아니다.
  - 순환 의존이 없다. stale M2는 권한도 아니고 거부 근거도 아니다.
  - **잔여:** K2R2-M1.
- **K2-M2 — 닫힘.**
  - MigrationOperationID는 이제 P08(원본 plan/history)에 있다. P12는 live Operations만 다룬다.
  - owner scratch를 재현했다.
  - 검토자 음성 사례 4개를 더 돌렸다. 네 경우 모두 Verify와 Current가 함께 거부한다.
    - current ID를 history에 복사
    - facts와 ctx 둘 다 current로 변경
    - 원본 history lease hash 변경
    - 원본 history fence 변경
- **K2-M3 — 닫힘.**
  - 40개 ID와 원래 key 값이 design 8874(`e671501c…`)와 byte 단위로 같다. 40개 모두 NOT_RUN/null이다.
  - 읽기 전용 작업은 K2A, 생산·effect 작업은 K2B·기존 producer로 나뉘었다.
  - A32는 이미 인수된 M2 v2를 다시 쓴다. eb32 `peer_floor.go`에 `servingExecutableSHA256`가 있다.
- **K2-L1 — 조건부 증명으로 닫힘. CLOCK_MECHANISM_HOLD는 유지된다.**
  - 12개 pin이 일치한다. Now selector는 11줄에 15개다.
  - 모든 시간 술어를 source에서 다시 읽었다.
  - readback 후보가 여러 개여도 하한은 공유된다. 그래서 합집합도 convex다.
  - Go 1.27.0 x509 hash를 재현했다. Report에는 evaluated-at field가 없다.
  - 검토자가 fixture 시간을 1초 간격으로 훑어 보았다. Verify와 Current 모두 [t0, t0+59s] 한 구간만 통과했고, 출력은 그 구간 안에서 같았다.
  - 실행 중인 stdlib와 clock source가 확인되지 않았으므로 HOLD다.
- **K2-L2 — 닫힘.**
  - 39개 code catalog를 기준으로 했다. `ERR[...]` 32건이 모두 catalog 안에 있다. 예외는 문법 placeholder인 `ERR[CODE]`다.
  - 옛 별칭과 bare code는 0이다.
- **K2-L3 — eb32 기준으로 닫힘.**
  - owner census를 다시 build했다. 결과가 13/73/0으로 같다. G01–G08은 실제 shape 변화다.
  - **잔여:** K2R2-L1.
- **K2-L4 — 미래 경계 설계로 닫힘.**
  - eb32에서 migrationverify를 import하는 비테스트 파일은 여전히 0이다.
  - **잔여:** K2R2-L3.
- **K2-L5 — 설계로 닫힘.**
  - `/proc/self/exe` 측정, 설치 receipt, 산출물 X와 실행 Y의 불일치 거부를 계약에 넣었다.
  - measurement port는 null/HOLD다.

## 새 지적

- **K2R2-M1 (Medium).** D-OBSERVATION 계약 인수 전에 고쳐야 한다. K2A-TRUST/HISTORY는 막지 않는다.
  - 문제: permit 하나는 method 하나를 쓴다. 그런데 같은 attemptId에서 method만 바뀌어도 COLLISION이다.
  - 한 attempt는 challenge 발급에서 ExecCreate/Start로 넘어가야 하고, UNKNOWN 정리도 같은 attempt를 RECONCILE해야 한다. 두 경로가 모두 이 규칙에 걸린다.
  - 반례: CHALLENGE_ISSUE 다음 EXEC 요청은 COLLISION이다. 새 attempt는 NOT_TERMINAL이다. RECONCILE은 COLLISION이다.
  - 결과적으로 진행도 정리도 할 수 없다.
  - 수정 방향:
    - attempt body와 단계별 permit을 나눈다.
    - key를 (attemptId, method, step)으로 정한다.
    - 닫힌 상태 기계를 둔다.
    - create와 start 사이에 만료되는 경우를 정한다.
    - normal 모드의 slot key를 정한다.
  - Root에게 물을 문제가 아니라 owner가 계약을 고칠 일이다.
- **K2R2-L1 (Low).** grant에서 만들 gate에 반영한다.
  - census가 named non-struct type의 underlying 변화를 놓친다. 재현: R01 map, R02 slice, R03 func 변화가 UNDETECTED였다.
  - trust.go 한 파일만 읽는다. stub이 parameter에서 도달 불가능한지도 확인하지 않는다.
  - eb32 결론에는 영향이 없다. 입력 named type은 모두 struct다.
- **K2R2-L2 (Low).** 표기 문제다. 의미는 바뀌지 않는다.
  - contract.md 456–481줄에 `+` 접두가 남아 있다. 그래서 grant 표가 표로 렌더링되지 않는다.
  - 479줄에 `A01?A40`이 깨져 있다.
  - §6 AuthorizeEffect 서명이 gates.json과 다르다. precedence 규칙으로 해소된다.
  - P08 onFailure와 selector 전용 code의 우선순위를 적어야 한다.
- **K2R2-L3 (Low).** grant 범위 문제다.
  - import gate는 repo의 모든 Go module을 검사해야 한다.
  - current 계열 함수는 stub이 아니라 아예 없어야 한다.
  - measurement port가 null일 때 쓸 refusal code를 grant가 하나로 정해야 한다.

## Root grant 판단용 다음 범위

- **후보:** K2A-TRUST/HISTORY. owner는 Codex, 실제 검토는 Claude through Root다.
- **파일:** node-agent 아래 새 internal migrationcontext package다. 아직 존재하지 않는 미래 경로다.
  - errors, ports, policy, history, clock evaluator
  - `k1_bridge.go`: migrationverify의 유일한 production importer다.
  - 테스트, stdlib go/types boundary 테스트
- **기본 거부:** port가 null이면 모두 거부한다.
  - TRUST_UNKNOWN_OR_PIN_MISMATCH
  - HISTORICAL_BINDING_UNKNOWN
  - CLOCK_UNTRUSTED / CLOCK_MECHANISM_UNPROVEN
  - PUBLICATION… / CERTIFICATE…
  - selector 불일치: K1 이전에 ORIGINAL_PLAN_OPERATION_MISMATCH
  - K1 거부: K1_VALIDATION_REFUSED
- **제외:**
  - current 계열 API(없어야 한다), K2B 전부
  - entrypoint, 측정, 설치
  - go.mod, schema/pin, workflow, K1 변경
- **테스트:**
  - null-port 거부와 zero-effect static gate
  - DTO 위조 불가
  - repo 전체 import allowlist
  - underlying까지 보는 census: G01–G08, R01–R03
  - selector 음성 사례
  - synthetic ClockPort 경계
  - synthetic key만 사용, exact SHA에서 새 CI
- **HOLD 유지:**
  - 실제 binding 전부
  - D-OBSERVATION(K2R2-M1 포함), D-PREPUBLICATION, D-COHORT-FENCE
  - K2A-CURRENT, K2B
  - A01–A40 NOT_RUN
  - 물리 5대, 전체 프로그램

## 재현 증거와 한계

- **owner validator:** scratch 사본에서 실행했다. exit 0, stdout `88904c39…`가 owner gate-01·final log와 같다.
- **owner scratch:** archive `878d6b9e…`에서 10 PASS / 0 fail / 0 skip이다.
  - 실행된 owner test의 hash는 commit된 LF 파일의 CRLF 형태다.
- **보존:** 551d, 5623, eb32, f28, 191b와 옛 56651 실패를 그대로 두었다.
  - 원본 40건과 28 pin, manifest `a0a05427…`, e50 packet도 그대로다.
- **하지 않은 것:**
  - CI, native proof, archive 재실행
  - PG, Docker, SSH, VM, OS clock, Node, key, PKI 접근
  - Obsidian apply
- **owner gate:** receipt를 argv·exit·log로 읽었다. 직접 다시 실행한 것은 rev2 static validator뿐이다.

다음 첫 행동: Root가 이 판정을 읽고 K2A-TRUST/HISTORY grant 여부를 정한다. Codex는 grant와 별도로 K2R2-M1을 고쳐 observation 계약 revision을 준비한다.
