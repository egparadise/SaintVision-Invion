---
doc_id: "CODEX-S04-C1K-EVIDENCE-CONTRACT-001"
title: "S04-DB C1-K kernel 승인 결속 Evidence 계약"
version: "1.0.0"
status: "proposed"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-30T10:32:34+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S04-DB"]
tags: ["card-158", "s04-db", "approval", "recovery-epoch", "evidence", "fail-closed"]
---

# S04-DB C1-K kernel 승인 결속 Evidence 계약

## 1. 목적과 경계

이 계약은 [[S04-DB_S08-DB_운영_판정_기준]]이 별도 collector 몫으로 남긴 C1-K를 정의한다. 대상은 kernel PostgreSQL의 승인 요청→dispatch→tool claim→delivery→execution attempt 기록 결속이다. core `public.approvals`의 C1 판정을 다시 구현하지 않으며, 전체 제품의 “승인 우회 0”은 core C1과 이 C1-K가 모두 충족되어야만 주장할 수 있다.

제품 불변식의 근거는 다음과 같다.

- `services/control-plane/src/inv/approvals.py:119`의 `_current`와 `:406`의 `dispatch`는 승인 상태·만료·recovery epoch·bound run version을 재검사한다.
- `services/control-plane/src/inv/tooling.py:71`의 `claim`은 command·action digest·policy·epoch와 scheduled run version을 다시 결속하고, `:310`에서 immutable claim을 쓴다.
- `services/control-plane/src/inv/dispatch.py:59`의 `_can_start`는 현재 claim·approval·run을 재검사하며, `:214`에서 첫 전송 예약과 execution attempt를 같은 transaction에 기록한다.
- `services/control-plane/src/inv/node_execution.py:24`의 `seal_permit`는 claim·launch·allocation을 한 payload로 서명한다.
- DB 쪽 방어선은 `services/control-plane/src/inv/migrations/0002_approvals.sql`, `0003_tool_claims.sql`, `0007_delivery_queue.sql`, `0011_results.sql`이다.

collector는 REPEATABLE READ·READ ONLY snapshot 하나만 읽는다. 공개 계약과 migration을 바꾸지 않으며 DSN, host, database 이름 원문, tenant/project/run/node/approval/command/claim 식별자, permit payload, signature, raw 오류를 Evidence에 쓰지 않는다.

## 2. 관측과 판정

필수 관측은 네 가지다.

| ID | 관측 | `MEASURED_PASS` 조건 | 0행 또는 입력 공백 |
|---|---|---|---|
| K1 | approval→dispatch→claim 기록 결속 | claim이 1건 이상이고 모든 claim의 scope·command·action digest·policy version·policy decision·recovery epoch가 연결 approval/dispatch와 일치하며, dispatch≤claim이고 claim 만료가 승인 만료를 넘지 않는다 | `NOT_OBSERVED` |
| K2 | claim→delivery permit payload 결속 | delivery가 1건 이상이고 base64/JSON object payload가 해석되며 payload의 claim exact field set이 DB claim과 일치하고 issuedAt≤notAfter다 | `NOT_OBSERVED` |
| K3 | approval→run version→execution attempt 결속 | execution attempt가 1건 이상이고 scheduled event version=`bound_run_version+1`, running event version=`bound_run_version+2`, running attempt와 run_attempt/execution_attempt가 일치하며 dispatch≤claim≤attempt다 | `NOT_OBSERVED` |
| K4 | 실행 당시 control epoch 독립 증명 | 실행 시각의 epoch history 또는 동등한 독립 producer가 있고 approval·claim·Node 실행 epoch가 모두 그 값과 일치한다 | producer 부재 시 `NOT_REGISTERED` |

K1~K3 중 하나라도 불일치·파싱 실패·중복 state event·필수 연결 누락이 있으면 해당 관측은 `MEASURED_FAIL`이다. K4는 현재 `inv.control_epoch`의 단일 현재값만으로 과거 실행 당시 값을 재구성하지 않는다. 승인과 claim의 epoch가 서로 같은 것은 K1에서 측정하지만, 그것을 실행 당시 current epoch였다는 독립 증거로 바꾸지 않는다. 그러므로 현재 구현의 전체 verdict는 위반 발견 시 `FAIL`, 그 외에는 K4 때문에 `NOT_OBSERVED`이며 `acceptanceClaim`은 false다.

서명 문자열의 base64 형식과 존재는 검사하되 공개키 provenance가 없는 snapshot에서 암호학적 검증을 주장하지 않는다. `signatureVerificationStatus`는 `RECORDED_ONLY`로 고정한다.

## 3. Fail-closed 규칙

1. producer가 제공한 verdict는 신뢰하지 않고 aggregate count와 envelope를 collector가 다시 계산한다.
2. claim·delivery·attempt 수가 0이면 PASS가 아니다.
3. 위반 사유별 count는 음수일 수 없고, aggregate `violationCount`와 합이 정확히 같아야 한다.
4. payload는 object여야 하고 duplicate key·알 수 없는 claim key·필수 key 누락·잘못된 base64/UTF-8/JSON·naive timestamp를 모두 위반으로 센다.
5. evidence의 verdict는 닫힌 observation status로 재계산하며 source commit, clean tree, collector hash, database identity, snapshot hash, DB 시작·종료 시각에 결속한다.
6. database 예외는 클래스 이름만 stderr에 남기고 내용·DSN은 버린다.

## 4. 시험과 실행

- PG-free 단일 파일은 0행, count identity, 각 K1/K2/K3 mismatch, payload duplicate/unknown/missing key, timestamp, K4 거짓 PASS, secret/redacted error, overwrite와 provenance 변이를 고정한다.
- hosted Core 실 PostgreSQL 단일 파일은 제품의 실제 `ApprovalStore`→`ToolGateway`→`persist_delivery`→`DeliveryQueue.acquire` 경로로 양성 chain 1건을 만들고 collector가 K1~K3를 `MEASURED_PASS`, K4를 `NOT_REGISTERED`, 전체를 `NOT_OBSERVED`로 내는지 확인한다.
- 실 PG 시험은 disposable DB만 사용한다. 물리 Node 전송·추가 PC·CP host·hosts 설정은 이 카드의 입력이 아니다.

S04-DB는 `review`를 유지한다. 이 collector는 물리 Node 재전송, core C1 cancel-history producer, 실행 당시 epoch history가 없으므로 AC-04 완료나 task 승격을 만들지 않는다.
