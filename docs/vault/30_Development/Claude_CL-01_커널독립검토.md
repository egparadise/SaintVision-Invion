---
doc_id: "REVIEW-CLAUDE-CL01-001"
title: "Claude CL-01 커널 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-09-11T20:40:00+09:00"
source_of_truth: "Git"
---

# Claude CL-01 — Codex 최신 커널 독립 검토

카드: [[Claude 작업 현황]] CL-01. owner Claude / reviewer Codex. 부모 task S01-DB, S04-DB, S06-BE, S06-DB, S08-DB.

## 검토 대상과 방법

| 항목 | 값 |
|---|---|
| branch | `agent/codex/workspace-bridge` |
| 검토 SHA | **d14db0a** (카드가 지정한 `c5f2154`를 포함한 현재 head) |
| migration head | `0033_workspace_bridge_merge` (mergepoint) |
| 검증 환경 | 로컬 PostgreSQL 16, 컨테이너 `saintvision-lan-db-bff1a31d` |

카드가 지정한 범위 그대로 본다: 0028~0033의 적용 함수·grant, reservation/출력, PTY ticket/frame, Git dispatch/current scope.

**작성자의 시험 기록을 승인으로 옮겨 적지 않는다.** 아래 "확인함" 항목은 내가 실제로 조회하거나 실행한 결과이고, finding은 코드 위치와 재현 절차를 함께 둔다. 모든 소스 줄의 보안 감사는 아니다.

CI는 세 Agent 공통으로 계정 결제·한도 문제로 실행 전에 차단되어 있다. 아래는 전부 로컬 실측이며 CI 통과와 동등하지 않다.

## Finding

### F1 — 적용된 제공량이 기록된 제공량보다 조용히 작아질 수 있다 (중간, 재현함)

**위치**: `migrations/versions/0031_resource_offer_integrity.py`, `public.apply_capability_offer`
**관련**: `services/control-plane/src/inv/leases.py:293` `release()`

함수는 lease 총량을 **두 번, 서로 다른 snapshot에서** 읽는다.

1. 모든 `inv.resources` 행을 `FOR UPDATE`로 잠근 뒤 `total_leased`를 한 번 합산하고,
2. 분배 loop 안에서 자원별 `held`를 다시 읽는다.

그 사이에 `release()`가 끼어들 수 있다. `release()`는 **lease 행만 잠그고 자원 행은 잠그지 않으므로** 함수가 잡고 있는 자원 잠금을 기다리지 않는다. 반대 방향(신규 lease)은 자원 잠금에서 막히므로 발생하지 않는다.

결과: `remaining = p_offered - total_leased`는 낡은(더 큰) 값으로 계산되고, loop는 줄어든 `held` 위에 그만큼만 채운다.

**재현** — 함수 자신의 문장 순서를 그대로 두 session으로 재생했다. 자원 2개(각 capacity 2000), 미반납 lease 100:

```
A holds every resource lock for this node; total_leased = 100
B released the lease and committed, without waiting
requested 1000, written 900, undistributed remaining = 0
sum(offered) = 900, and the function returns applied=true with reason NULL
```

같은 seed의 경합 없는 실행은 `sum(offered) = 1000`으로 일치한다.

**주의**: `remaining`이 0으로 끝나므로 loop 끝의 `IF remaining <> 0 THEN RAISE` 같은 보호는 이 경우를 **잡지 못한다**. 차이는 분배 실패가 아니라 낡은 `total_leased`를 뺀 데서 온다.

**영향**: `public.resource_offers`는 1000을 기록하고 커널은 900을 제공한다. API는 `appliedToKernel: true`를 돌려준다. 이후 예약은 운영자가 1000이라고 믿는 용량에서 `RES-0001 Insufficient offered capacity`로 거절된다. 방향은 항상 보수적(과다 제공 아님)이고 다음 offer 기록 시 스스로 복구되지만, **기록과 실제가 말없이 달라진다.**

**제안**: capacity와 자원별 held를 한 문장(예: `inv.resources LEFT JOIN inv.resource_leases … GROUP BY`)으로 한 snapshot에서 읽고, `total_leased`를 그 합으로 쓴다. 또는 `release()`가 해당 자원 행을 잠그게 한다.

### F2 — PTY frame이 Node에서 실행된 뒤에야 sequence 감사가 이뤄진다 (중간)

**위치**: `services/control-plane/src/inv/terminal.py` `frame()` — Node 호출은 `runtime.client.terminal_frame(...)`, 감사는 그 **다음** transaction의 `inv.terminal_frame_audit` INSERT/비교.

`frame()`은 Node 호출 **전** transaction에서 `_current`·`_connection`으로 권한을 다시 확인한다. 그러나 `sequence`의 중복과 digest 일치는 호출 **후**에만 본다.

같은 `sequence`로 내용이 다른 frame을 다시 보내면:

1. Node에서 두 번째 내용이 **실제로 실행되고**,
2. `INSERT … ON CONFLICT DO NOTHING`은 아무것도 넣지 못하며,
3. 기존 행의 digest와 다르므로 `AUTH-0070`으로 거절된다.

즉 감사 행은 첫 번째 내용의 digest를 유지하고, `inv.terminal.frame` event는 `if inserted`일 때만 남으므로 **두 번째로 실행된 내용에 대응하는 event가 아예 없다**. 권한 상승은 아니다(호출자는 이미 현재 요청자이고 일회용 ticket을 redeem했다). 그러나 이 시스템의 전제는 Evidence가 실행된 것을 기록한다는 것이고, 여기서는 실행된 것과 기록된 것이 어긋날 수 있다.

**제안**: sequence 예약(INSERT)과 digest 비교를 Node 호출 **전** transaction — 이미 존재하는 `frame()`의 첫 블록 — 으로 옮긴다.

### F3 — 폐기된 SECURITY DEFINER 함수가 grantee 없이 schema에 남는다 (낮음)

`0029_run_outputs`가 `public.run_committed_outputs`를 만들고 `inv_app`에 EXECUTE를 준 뒤, 바로 다음 `0030_provisioning_integrity`가 같은 함수를 `PUBLIC, inv_app`에서 REVOKE한다. `0031`은 `public.apply_resource_offer`를 같은 방식으로 회수한다. head의 `pg_proc.proacl` 실측:

```
apply_resource_offer         postgres=X/postgres
run_committed_outputs        postgres=X/postgres
apply_capability_offer       postgres=X/postgres inv_app=X/postgres
…
```

두 함수는 소유자만 실행할 수 있으므로 지금은 도달 불가다. 다만 **RLS를 우회하는 정의가 사용되지 않은 채 남아 있다**. 이후 누군가 광범위한 GRANT를 하면 폐기한 경로가 조용히 되살아난다. 폐기가 확정이라면 `DROP FUNCTION`이 맞다.

### F4 — `.git` 제외 규칙이 두 곳에서 다르다 (정보)

`services/control-plane/src/inv/remote_git.py`의 `export_snapshot`은 `path.split("/")[0]`만 보고, `git_files`는 `portable_path`의 **모든** segment를 본다. 따라서 중첩된 `sub/.git/config`는 걸러지지 않고 `SEC-0020`으로 export 전체가 거절된다. 닫히는 방향이라 결함으로 보지 않지만, docstring("never part of a remote file commit")은 제거를 말하고 코드는 거절을 한다. 둘 중 하나를 맞추는 편이 낫다.

## 확인함 (실제 조회·실행 결과)

- **0029 `run_committed_outputs`**: 처음부터 tenant binding이 있다(`p_tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid`). `search_path=pg_catalog` 고정, `PUBLIC` REVOKE 후 `inv_app`에만 GRANT. GUC 미설정 시 NULL 비교로 행이 없어 닫히는 방향이다.
- **0030 `subject_kernel_link`**: binding에 더해 `u.external_subject = s.subject_id`를 요구한다. 0026의 교차 tenant 누수를 막는 정의가 head에 있음을 실측으로 확인했다.
- **`inv.account_provisioning_events`**: RLS `ENABLE` + **`FORCE`**, USING/WITH CHECK 양쪽, `immutable_record()` trigger, `PUBLIC/inv_app/inv_kernel` 전부 REVOKE, tenant를 포함한 복합 FK. 설계와 일치한다.
- **잠금 순서**: offer 경로(`public.nodes` → `public.node_capabilities` → `inv.nodes` → 정렬된 `inv.resources`)와 lease 경로(`lock_resources`, `leases.py:32` — 정렬된 node → 정렬된 resource)가 공유 구간에서 같은 순서다. 주석의 주장은 코드와 맞는다. 두 경로 모두 public → inv 방향이라 순환은 보이지 않는다.
- **분배 산술**: 경합이 없을 때 `sum(capacity - held) ≥ p_offered - total_leased`이므로 loop는 항상 전량을 분배하고 `sum(offered) = p_offered`가 된다. 경합 없는 실행에서 실측으로 일치했다.
- **definer 함수 9개 전수**: head DB에서 `pg_proc`를 읽어 판정했다. 9개 모두 tenant scope에 묶여 있고 `search_path`가 고정돼 있으며 `pg_temp` 선순위도 없다 — **unsafe 0, 오탐 0**. (판정 도구는 `tools/check_definer_functions.py` + `tools/_definer_rules.py`, `dee31e5`에서 문자열 대조를 코드 판독으로 교체한 판이다.)
- **PTY `_current`**: 요청자 동일성, run 잠금, `can_request` grant, business handoff scope, containment, run 상태와 recovery epoch, attempt 승계, Node 상태와 epoch, 마감 5초 여유, lease 생존과 epoch까지 확인한다. Node 호출 **전후 두 번** 수행된다.
- **PTY ticket**: 정확한 Origin 일치, 32바이트 난수의 sha256만 저장, 만료는 `min(now+30s, not_after-5s, 신원 만료)`, redeem에서 consumed/만료/Origin/epoch/session/workspace 전부 대조, `terminal_connections`를 `FOR UPDATE`로 단일 접속 강제, `UPDATE … WHERE consumed_at IS NULL RETURNING`으로 일회성 보장. 접속 임대는 5초로 갱신된다.
- **`TerminalText`**: cursor 연속성(`cursor == 자신의 cursor + len(data)`), frame 4096바이트·행 65536바이트 상한, 완전한 행만 방출, private key 블록 상태기, OSC/CSI 제거 후 남은 제어문자 제거. 상한 초과는 예외로 닫힌다.
- **Git**: `_actor`가 `operator_grants`의 enabled·person_id·`can_git`(투표 시 `can_approve`)와 프로젝트 grant를 함께 요구하고, `_locked`가 요청자와 다른 주체일 때 `voting=True`로 전환해 4-eyes를 만든다. `_fresh`는 phase·만료·recovery epoch·`tenant_controls.version`에 더해 snapshot sha256과 payload digest를 검증한다.

## 검토 결론

카드가 지정한 네 영역을 모두 보았다. 인가·격리·일회성 경계는 내가 확인한 범위에서 견고하다 — 특히 PTY의 전후 이중 권한 확인과 Git의 4-eyes 전환은 우회 경로를 찾지 못했다. definer 함수는 9개 전수 tenant 결속을 실측으로 확인했다.

**승인으로 표시하지 않는다.** F1은 기록과 실제 제공량이 어긋나는 재현된 결함이고, F2는 실행된 것과 기록된 것이 어긋날 수 있는 경로다. 두 건 모두 원래 owner가 Codex이므로 수정은 Codex가 하고, 해결 SHA가 나오면 내가 다시 확인한다.

## 남은 것과 다음 첫 행동

- F1·F2를 Codex에 인계한다. 해결 SHA 확인은 Claude.
- 이번 검토에 **포함하지 않은 것**: 모든 소스 줄의 보안 감사, Node 런타임이 필요한 통합 시험, 실제 2대 이상에서의 PTY/Git 여정. 후자는 원격 설치(.225)가 선행이다.
- CI 차단 상태에서의 검토이므로, CI가 복구되면 회귀는 별도로 확인해야 한다.
