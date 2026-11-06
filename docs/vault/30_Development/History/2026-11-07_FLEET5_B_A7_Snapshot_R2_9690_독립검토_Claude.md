---
doc_id: "HISTORY-FLEET5-20261107-B-A7-SNAPSHOT-R2-9690-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 B A7 snapshot R2 9690 좁은 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T07:54:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "969030dbc7716b9cadf75bd314713005306ed34c"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105", "FLEET5-B-A7-SNAPSHOT-R2-20261107"]
tags: ["fleet5", "independent-review", "b-contract", "a7", "claude"]
---

# B A7 snapshot R2 9690 좁은 delta 독립 검토

Orca `task_c2de6e9fd486` / dispatch `ctx_36ec44cc8ca0`에서 한 실제 독립 검토다. 직전 작업 `task_a152e893e6de/ctx_06f0718be774`(D04 f2c1 CODE 검토)가 succeeded/settled/exited/released인 것을 확인한 뒤 시작했다. 그 검토는 A7 밖이고 다시 열지 않는다.

- owner: Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`.
- pending 질문: `msg_649487e8b552`.
- Root 수정 허가: `msg_e051a19e0010`.
- helper와 두 번째 검토자는 쓰지 않았다.

대상과 범위:

- 대상: `969030db`, 직접 부모 `1550453d`.
- 추가 125개(R2 Evidence 124, History 1), 수정·삭제 0, 그 두 경로 밖 변경 0.
- 제품 기준 `72028cba`는 그대로다.

먼저 읽은 것:

- 실제 R1 검토 `7a8012f4`의 History, review.json, commands.json, driver(PATCH 포함), 49행 결과를 그 commit에서 직접 읽었다. 해당 반례는 SPAN/BODY/CENSUS/GUARD_ONLY 네 행이다.
- 이어서 Root 허가(`.work/a7r2-root-fix-cut.txt`)와 spec을 읽었다.
- Root 보드는 read-only로 읽었다: `8c7f6e6e`, Index 1.0.486, Claude board 1.2.130.

사전 확인 (owner 명령은 다시 돌리지 않았다):

- manifest `a69dc820…`를 다시 계산했다.
  - 파일 123개, producer·상속 의존 34개, History hash가 commit된 bytes와 모두 같다.
  - proof-final04 3개, docs-publish01 8개, publication check 1개 모두 exit 0이다.
  - 명령 전후 producer hash가 manifest와 같고, raw log hash도 맞다.
- red-original01: `r2_tests.py --exact-only`. 기대대로 exit 1이고, 전후 a7_inventory는 `6910ddfd`다. raw log는 `MISSING_OR_INEXACT_NEW_CENSUS_DELTA`, censusAdded `[]`로 끝난다.
- `red-a7_inventory.py.txt`는 1550 R1 blob과 byte가 같다. R1→R2 diff는 12줄이고, `inventory-delta.patch.txt`와 같다.
- R2 디렉터리의 R1 검토 사본 10개(`actual-review-*`)는 7a80 blob과 byte가 같다.
- 작성자의 commit 이후 API/게시 영수증은 추적되지 않는 파일이라 후보 입력으로 쓰지 않았다.

**판정: PARTIAL_STATIC_EVIDENCE_ACCEPT_L1_CLOSED_KEEP_HOLD.**

- A7R-L1은 닫혔다.
- **I3 oracle: I3_ORACLE_CLOSED.** oracle만 고쳤고 purpose predicate는 그대로다.
- HIGH/MEDIUM/LOW는 없다. 새 INFO는 2건(I5, I6)이다. I1/I2/I4는 그대로 명시해 둔다.
- 이 수락은 census guard 배치, parsed==audited, R2 회귀·대조군에만 해당한다.
- 전체 A7, caller closure, runtime, source 포함, port는 부여하지 않는다.
- 상세: `docs/vault/30_Development/Evidence/fleet5-b-a7-snapshot-9690-review-20261107-claude/review.json`.

## A7R-L1 닫힘 근거

변경 내용:

- census가 파싱한 모든 경로에 같은 guard 두 개를 `if not relevant: continue`보다 먼저 건다.
  - `ra.audit(f, PROTECTED)`
  - `u.module_uses(source, path, instances=True, factories=(), parameter_context={})`
- 인자, predicate, obligation code는 그대로다.
- 보존 필터(retention)는 그 아래의 selectedSources와 생성자/snapshot/carrier 분류만 정한다.
- 새 family, resolver, allowlist, 우회는 없다.

coverage 독립 확인:

- 검토자가 72028에서 같은 pattern으로 git grep 했다. `.py`는 30개다.
- 각 Git blob을 hash한 dict가 다음 모두와 같다.
  - census sourceFiles
  - guards의 sourceSHA256
  - 따로 계산되는 `reflection.sourceSHA256`와 `useSites.sourceSHA256`
  - sidecar의 guardCoverage
- 즉 개수만이 아니라 경로와 bytes가 30=30으로 같다.
- 새로 검사된 18개는 깨끗하다(hit 0, error None).
- R1 inventory는 12개만 guard한다. 빠진 집합은 정확히 그 18개다.

frozen 불변:

- 실제 72028에서 R2와 R1 census는 다음이 모두 같다: sourceFiles, 생성자 10, snapshot 10, other receiver, carrier, census obligation.
- 전체 prove() obligation은 양쪽 모두 19건이고 JSON이 같다. forwarding도 같다.

정확한 회귀의 red/green (같은 process, 같은 입력, inventory만 다름):

- 입력: frozen `6e2bfb2d`에 R1 driver의 literal PATCH를 붙인 `node_certificates.py`. 결과 hash는 `19c2e14e`다.
- 선택된 body는 그대로이고 `bodyAccepted=true`다. body 거부가 아니다.
- GREEN: census와 전체 prove 모두 기준 multiset 전체 대비 정확히 1건이 늘고, 줄어든 것은 없다.
  - code: `A7_FULL_MODULE_USE_SITE_GUARD`
  - path: `node_certificates.py`
  - subject: `DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:WRITE_USE:inv.node_channels.NodeChannels.snapshot`
  - multiplicity 1, retainedForCallClosure false.
- RED: R1 inventory는 0건이 늘고, 그 경로의 guard 행도 없다.
- 위치: 검토자가 같은 인자로 직접 replay하면 첫 거부 node가 [76,0,76,22]다. AST Store node `_ReviewerA7NC.snapshot`과 같다.
  - 이 위치는 진단용일 뿐이다. 판정은 `module_uses`의 error가 한다.
- 작성자 oracle(`r2_tests.py`)도 확인했다.
  - 기준 전체 대비 code/path/span/subject/multiplicity의 정확한 Counter를 요구한다.
  - 기존 19 blocker로는 이 oracle을 만족시킬 수 없다.
  - red exit 1, green exit 0으로 인과가 맞다.

## 검토자 대조군 (AST 전용, 직렬 1 process)

- 실행: owner `measured_run.py`, 07:47:35~07:50:53 KST.
  - exit 0, peak 146444288 B, 196 s. 단일 process 관측값이고 quota가 아니다.
- 첫 시도(07:43~07:47)는 exit 1이었다. 검토자 harness 버그다.
  - 마지막 case의 자체 precheck가 새 파일에 `frozen_source`를 불렀다.
  - 그 전의 행은 모두 log에 남아 있다.
  - helper만 고쳐 다시 돌렸고, 두 log를 모두 commit한다.

| 대조군 | GREEN (R2) | RED (R1) | 의미 |
| --- | --- | --- | --- |
| 같은 PATCH, 다른 비보존 후보 capacity.py | +1 WRITE_USE, [107,0,107,22] | +0 | node_certificates만 특별 취급하지 않는다 |
| 비보존 `importlib.import_module('inv.node_channels')` | +1 `A7_RELEVANT_REFLECTION`, +1 use-site | +0 | reflection guard도 비보존 파일에 걸린다 |
| 비보존 module 속성 저장 (`assert_channel`) | +1 WRITE_USE assert_channel | +0 | 기존 predicate가 거부한다. 새 family가 아니다 |
| 비보존 capacity.py 주석 | +0, guard 행 있음, hit 0 | +0 | 무조건 거부하지 않는다 |
| 보존 observation.py 같은 PATCH | +1 [154,0,154,22] | 같은 +1 | 보존 경로는 R1에도 있었다. R2는 범위만 넓혔다 |
| I3 `observation_only=foreign` | +purpose [17,16,17,70] 'foreign', +INSTANCE:proof | 같은 두 key | purpose predicate는 그대로다 |
| 새 제품 파일 | CalledProcessError | 같음 | frozen 경로가 없으면 fail-closed다. 성공도 resolver도 아니다 |

## INFO (판정에 영향 없음)

- **I1 (유지):** lexical binding을 감싸는 문장 전체의 source segment로 식별한다. 같은 엄격함이 I3 입력에서도 보인다(observation.py [17,8,17,13]의 일반 `INSTANCE:proof` use-site key, red와 green 모두). text 독립이라고 부르지 않는다.
- **I2 (유지):** remote_git.py:285와 workspace_git.py:167은 git snapshot receiver다. 닫힌 NodeChannels가 아니다.
- **I4 (유지):** BoundDatabase는 인증된 `inv.db.Database`가 아니다. 기존 owner/root 미해결 obligation 아래에 남는다. 새 일반 resolver는 필요 없다.
- **I5 (신규, 진단용):** census guard obligation의 source는 span 없는 경로 문자열이다. R2 oracle의 span은 census 인자로 `audited_nodes`/`key_for`/`baseline_sites`를 replay해서 얻는다.
  - 이 replay는 `module_uses`의 `builtins.globals` NAMESPACE 분기를 생략한다.
  - 그 분기에서 거부가 나면 `guard_location`이 AssertionError로 실패한다. 통과하지 않는다(fail-closed).
  - 검토자가 span을 독립적으로 재현했다. 수정할 필요는 없다.
- **I6 (신규, 범위 한정):** I3 oracle은 기준에 없는 새 purpose key를 정확히 요구한다.
  - 다만 observation.py의 세 code(purpose, use-site, forward)라면 다른 추가 key도 허용한다. 정확한 전체 delta를 요구하지는 않는다.
  - 실제 전체 delta는 결과에 남아 있다. 조여도 되지만 선택 사항이다.
- 참고: 코드 안의 parsed==audited assert는 같은 iteration의 같은 source로 만들어진다. 그래도 guard 앞의 skip이 다시 생기면 경로 집합이 달라져 잡아낸다. 검토자는 Git blob과 독립 SHA field로 따로 확인했다.

## 실패 기록, 남는 HOLD, 하지 않은 것

보존된 실패:

- development-failures.json은 네 event를 원래 exit와 raw log로 보존한다.
  - 준비 codec `utf8-sig` 오타
  - final01-3: tuple과 JSON 비교
  - final02-3: 중첩된 red 영수증 읽기
  - docs-final03-1: UTF-16 transcript
- 모두 harness/verifier/encoding 층의 문제다. guard나 predicate는 바꾸지 않았다.
- R1 실패 기록도 남아 있다.
- Root가 적은 07:15 canonical bracket의 이전 sealer는 단계 사이의 sealer 변경일 뿐이다. 최종 proof 입력이 아니고, 검토자는 이에 의존하지 않았다.

남는 HOLD:

- 상태는 `SOURCE_STATIC_UNRESOLVED_RUNTIME_PENDING`이다.
  - body는 조건부(bodyAccepted true)다.
  - callerClosureAccepted false.
- 원래 blocksGrant 19건이 모두 남는다: NodeDelivery purpose 1, Database owner 10, 역방향 root 8.
- runtime B 0, real binding NULL/HOLD, A1~A16 PENDING.
- 다음은 그대로다. Root가 검증했고, 검토자는 다시 계산하지 않았다.
  - 12 entry, 19 edge(16/3).
  - 598/757/1071/21/573 outside/218.
  - model, lifecycle, stage/final order.
- A7은 열세 번째 entry가 아니다.

하지 않은 것:

- owner proof/docs/seal 명령.
- 이전 33/49 corpus, 523 assembler, 3485 plan, 전체 B, model/recovery.
- 수락된 R1 body/경로 표/import/DB lock 재검토.
- 제품·mutant import나 실행, PG/네트워크/crypto/host 작업.
- Obsidian apply/adopt/resolve/state 쓰기, 공유 보드·registry·ADR·workflow 수정.

canonical CHECK와 gate:

- 작성 전 CHECK: exit 0, conflict 0. state는 `00c27e0c…`에서 변하지 않았다.
- 작성 뒤 local gate 8개는 `local-doc-gates.txt`에 실제 exit와 state hash로 남긴다.
- D04 f2c1 a967 CODE 수락과 Core 42300147891은 A7 밖이다.

## 다음 (Root에게)

- 다음 첫 행동: Root가 이 좁은 L1·I3 닫힘을 Root 보드에 기록하고, 작성자의 `msg_649487e8b552`에 답한다. A7은 19 blocker로 PARTIAL/HOLD를 유지한다. 담당은 Root다.
- 검토자는 다음 범위를 시작하지 않는다.
