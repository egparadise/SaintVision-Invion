---
doc_id: "HISTORY-VF-CL-NEXT-CARD-20261001"
title: "VF-CL 다음 준비 카드 선택과 VF-CL-04의 ciVerified 공백 해소 — 수락 증거를 사람이 아니라 CI가 도출하게 (카드 185)"
version: "1.2.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-01T19:51:27+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "8d5a7d9b"
task_ids: ["S12-DB", "S12-ST"]
tags: ["vf-cl", "s12", "acceptance", "ci", "evidence", "fail-closed", "claude"]
---

# VF-CL 다음 준비 카드 선택과 VF-CL-04의 `ciVerified` 공백

## 0. 기준과 방법

- 기준 tree: **`8d5a7d9b`**(`coord/train8c-ci-1900`, `Merge PR #278`).
- 읽은 것: `docs/vf-cl-task-registry.json`(v1.3.1, 카드 5개) 과 `tools/check_vf_cl_registry.py`.
- 체커 실행: `python tools/check_vf_cl_registry.py` → **`"status": "every implementation claim re-derived from the tree"`**, 카드 5, `acceptedCards: 0`.
- 선택 순서는 카드 185가 준 순서를 따랐다 — storage catalog/API → `inv://` resolver → model registry/lineage → 복원·관측 → 독립 검토.

## 1. 다섯 카드의 실제 상태 (레지스트리에서 그대로)

| 카드 | implemented | locallyVerified | ciVerified | independentlyReviewed | operationallyAccepted |
|---|---|---|---|---|---|
| VF-CL-01 storage catalogue/API | Y | Y | Y | Y | **n** |
| VF-CL-02 `inv://` resolver | Y | Y | Y | **n** | n |
| VF-CL-03 model registry/lineage | Y | Y | Y | **n** | n |
| **VF-CL-04 복원·관측(replica repair, backup/PITR, metrics, runbook)** | Y | Y | **n** | n | n |
| VF-CL-05 독립 검토 | Y | Y | n/a | n/a | n |

**구현이 남은 카드는 없다.** 남은 칸은 세 종류이고 성질이 다르다 — 수락(사람), 독립 검토(검토자), 그리고 **CI 결속**.

## 2. 선택: VF-CL-04의 `ciVerified`

레지스트리가 그 칸이 거짓인 이유를 스스로 적어 두었다(`ciVerifiedNote`).

> 복원 예행 자체는 `6fc0428b`에서 **ci-verified**다(run `36521298082`). 카드의 나머지에는 거짓으로 남는다: **어떤 workflow도 `tools/collect_s12_acceptance_evidence.py`를 실행하지 않으므로**, 이름 붙은 수락 관측 `pitr-configuration-possible`과 `pitr-rehearsal-dry-run-observed`는 **사람 손으로 만들어지고 CI가 다시 도출하지 않는다.** 도구들의 단위 시험은 Core에서 돌지만, 그것을 수락으로 바꾸는 gate는 돌지 않는다.

기준 tree에서 그 진술을 다시 확인했다 — `grep -rln collect_s12_acceptance_evidence .github/workflows/ tests/ tools/` 는 **시험 두 개만** 돌려주고 workflow는 **0건**이다. 공백이 그대로 있다.

**이것을 고른 이유 세 가지.**

1. **owner가 Claude이고 외부 전제가 없다.** hosts·node4/5·CP 호스트·실 PITR 복원·GPU 중 아무것도 필요하지 않다. 필요한 것은 runner와 일회용 PostgreSQL뿐이다.
2. **순서상 "복원·관측" 자리다.** 앞의 셋(01·02·03)에 남은 칸은 수락과 독립 검토이고 둘 다 내 손의 일이 아니다(§3).
3. **공백의 성질이 내가 다른 곳에서 계속 쓰던 구별과 같다** — 측정 수단이 있는 것과 측정이 일어나는 것은 다른 일이다. 도구는 있고 CI가 그것을 돌리지 않으니, 그 두 관측은 "사람이 적은 숫자"다.

## 3. 고르지 않은 카드와 그 차단 사유

| 카드 | 남은 칸 | 왜 지금 내 일이 아닌가 |
|---|---|---|
| **VF-CL-01** | `operationallyAccepted` | 수락은 **사람의 행위**다. storage 제품 값(contribution 루트·storage-policy·아카이브, `G-20`)이 사용자 결정이고, 레지스트리의 `ACCEPTANCE_REQUIRES`는 `ciVerified`·`independentlyReviewed`만 요구하므로 이 카드는 **코드가 아니라 결정을 기다린다** |
| **VF-CL-02** | `independentlyReviewed` | 차단자 둘이 모두 **검토 미기록**이다 — `uri-trailing-and-version-slash-fix-re-review-not-recorded`, `c75201af-model-shard-resolution-not-independently-reviewed`. 이 카드의 reviewer는 **Codex**이고, 내 작업의 독립 검토를 내가 할 수 없다 |
| **VF-CL-03** | `independentlyReviewed` | 같은 성질 — `34791448-license-exact-match-adapter-not-independently-reviewed`. 앞선 차단자(`import-adapter-has-no-request-path-contract`)는 `6fc0428b`에서 **이미 닫혔다** |
| **VF-CL-05** | `operationallyAccepted` | 검토 카드다. `ciVerified`·`independentlyReviewed`는 레지스트리가 `notApplicable`로 사유와 함께 적어 두었고("a review card ships documents, not code CI executes"), 남은 칸은 수락이다 |

**즉 외부 전제로 건너뛴 카드는 VF-CL-01과 VF-CL-05**(수락 대기)이고, **검토자 소관으로 건너뛴 카드는 VF-CL-02와 VF-CL-03**이다. 구현으로 움직일 수 있는 칸은 VF-CL-04의 `ciVerified` 하나뿐이었다.

## 4. 한 일

### 4-1. `.github/workflows/s12-acceptance-evidence.yml`

일회용 PostgreSQL을 띄우고 **발행된 migration을 적용한 뒤** 수집기를 돌려 17개 AC-12 항목을 도출하고, 모양 gate를 통과시킨 뒤 증거를 artifact로 올린다.

**push trigger를 일부러 넣지 않았다.** `integration/all-agents-unified`에 push로 걸리는 workflow는 `tools/post_landing_verify.py`에 lane을 하나 빚지고(카드 178의 역방향 ratchet이 그것을 단언한다), 이 묶음은 **착지 gate가 아니다.** 사람 대신 CI가 수집기를 돌리는 일은 요청으로 하는 것이고 매 착지마다 하는 것이 아니다. 기준 tree에서 그 ratchet(`tests/core/test_post_landing_verify.py`)을 돌려 **lane 여덟이 그대로이고 212건 통과**임을 확인했다.

**migration을 적용하는 이유**: 적용하지 않으면 readiness 도구가 빈 catalogue를 읽고 모든 DB 항목이 **같은 무정보 FAIL**이 된다. 적용하면 실패하는 항목이 "운영 입력이 실제로 없어서" 실패한다.

**archive·backups는 빈 디렉터리 둘**이다. 예행은 **읽기 전용 관측**이므로 빈 아카이브와 빈 백업 집합은 관측할 수 있는 실제 상태다 — "base backup이 없다"가 답이고, 없는 것을 만들어 내는 것이 이 수집기가 피하려는 실패다.

### 4-2. `tools/check_s12_acceptance_shape.py` 와 그 시험 24건

**gate는 verdict를 판정하지 않는다.** 외부 대기가 풀리기 전의 정직한 verdict는 `FAIL` 또는 `PASS_MEASURED_PARTIAL`이고, 좋은 verdict를 요구하는 gate는 영원히 빨갛고 결국 지워진다. 그래서 gate는 **어떤 답이든 참이어야 하는 것**만 단언한다.

| 단언 | 왜 |
|---|---|
| `schemaVersion`이 `s12-db-acceptance-evidence:1` | 모르는 모양을 통과시키지 않는다 |
| `acceptanceClaim`이 **정확히 `false`** | `0 == False`이므로 **동일성**으로 비교한다. 이 묶음은 검토 입력이고 AC-12를 닫지 않는다 |
| **17개 항목이 전부 있고 각각 인정되는 status를 가진다** | **이 gate의 핵심이다.** 항목이 빠지면 scope 목록에서 FAIL 하나가 사라져 **진전처럼 읽힌다**. 질문이 사라져서 verdict가 좋아지는 것은 읽는 사람이 볼 수 없는 유일한 실패 모드다 |
| 예상 밖 항목이 없다 | 그래야 "범위가 완전하다"를 말할 수 있다 |
| 이름 붙은 두 관측이 **`source` 도구를 명시한다** | 레지스트리의 주장은 "CI가 도출한다"이고 "항목이 보인다"가 아니다. `source`가 빈 항목은 사람이 적었을 수도 있다 — 바로 그 상태가 `ciVerifiedNote`가 적은 상태다 |
| 파일에 연결 문자열·비밀번호가 없다 | 수집기가 직렬화 전에 가리고 자기 텍스트를 다시 보지만, 이것은 **실제로 올라간 파일**을 독립적으로 다시 읽는 것이다. artifact는 내려받을 수 있는 자리다 |

시험이 각 거부 경로를 하나씩 고정한다 — 특히 **17개 항목을 하나씩 빼는 17가지 전부**를 돌린다(일부만 덮는 gate는 추첨이 된다), `acceptanceClaim`의 `True`·`None`·`"false"`·`0`·`1`, JSON escape로 숨긴 DSN, 그리고 **`FAIL` verdict가 통과하는 것**.

> **위 표는 충분하지 않았다.** Codex가 r1에서 측정했다: 이 단언들만으로는 **사람이 손으로 적은 묶음**이 통과한다 — 17개 이름이 다 있으면 되기 때문이다. 무엇이 모자랐고 무엇을 묶었는지는 **§7-2**에 적는다. 이 절은 처음에 무엇을 단언했는지를 보이기 위해 지우지 않고 남긴다.

### 4-3. 기준 tree에서 실제로 돌려 보았다

로컬 실 PostgreSQL로 수집기를 돌려 **17개 항목 전부**가 도출되는 것을 확인했다 — `PASS` 3, `FAIL` 6, `NOT_OBSERVED` 1, `BLOCKED_EXTERNAL` 7, verdict `FAIL`, `acceptanceClaim: false`. 이름 붙은 두 관측이 둘 다 나왔다(`pitr-configuration-possible`은 `FAIL`, `pitr-rehearsal-dry-run-observed`는 `PASS`). 그 실제 묶음에 gate를 걸어 통과하는 것도 확인했다.

**DSN이 없으면 수집기는 거부한다**("neither INV_READINESS_DSN nor INV_PITR_DSN is set; nothing can be observed"). 그래서 lane이 PostgreSQL을 띄우는 것은 선택이 아니라 요구다 — 이것도 추측하지 않고 돌려서 알았다.

## 5. 레지스트리를 아직 고치지 않았다

`VF-CL-04.ciVerified`는 **이 PR의 lane이 기준 head에서 녹색으로 돌기 전까지 거짓으로 둔다.** 레지스트리의 `verifiedAgainst.hostedRun`이 run id와 단계 이름으로 주장을 받치는 형식을 쓰므로, 같은 형식으로 이 lane의 run을 적은 뒤에 칸을 바꾸는 것이 맞다. **플래그를 먼저 올리고 증거를 나중에 붙이는 순서는 이 레지스트리가 두 번 정정한 바로 그 실수다**(`restatedBlockers`·`localUnmeasured`가 그 기록이다).

## 6. 이 카드가 확인하지 않은 것

- **`alembic upgrade head`를 로컬에서 돌리지 않았다.** 로컬 PostgreSQL은 공용 개발 DB이고 migration을 적용하면 다른 작업에 영향이 간다. 그 단계는 **hosted에서만** 확인된다.
- **lane이 만드는 verdict를 예측하지 않았다.** migration이 적용된 빈 DB에서는 로컬과 다른 항목이 다른 status를 받을 수 있고, gate는 그것을 판정하지 않는다. 예측을 적지 않는 것이 이 gate의 설계다.
- **수락(`operationallyAccepted`)은 움직이지 않는다.** 이 lane은 수락 묶음을 **도출**하고, `acceptanceClaim`은 언제나 `false`다. AC-12는 닫히지 않는다.
- **VF-CL-02·03의 독립 검토를 하지 않았다.** reviewer가 Codex이고 내 작업의 검토를 내가 할 수 없다.
- **`web-smoke-journeys`는 `NOT_OBSERVED`로 남는다.** 수집기는 `--web-smoke-proof` 경로를 받을 수 있지만 그 증거는 다른 lane의 산출물이고, 이 lane에서 합성하지 않았다.


## 7. Codex r1 조치

### 7-1. F-R1 — lane이 migration 단계에서 죽었다

기준 head의 `workflow_dispatch` run **36847277078**이 `Apply the published migrations`에서 `ModuleNotFoundError: No module named 'psycopg2'`로 실패했다. 그 뒤 수집기·gate 단계는 skip되고 artifact가 없었다 — **그래서 이 PR에는 hosted 관측이 하나도 없었다.** 지적이 맞다.

원인은 **DSN 한 줄의 철자**다. 같은 데이터베이스를 세 이름으로 주지만 **소비자가 둘이고 철자가 둘이다**:

| 환경 변수 | 소비자 | 필요한 철자 | 왜 |
|---|---|---|---|
| `INV_READINESS_DSN` | `tools/operational_readiness.py` → `psycopg.connect(dsn)` | `postgresql://` | libpq가 읽는 문자열이다 |
| `INV_PITR_DSN` | `tools/pitr_readiness.py` → `psycopg.connect(dsn)` | `postgresql://` | 같다 |
| `INV_MIGRATION_DSN` | `migrations/env.py` → SQLAlchemy | **`postgresql+psycopg://`** | SQLAlchemy는 **scheme으로 driver를 고른다**. `postgresql://`는 psycopg2를 뜻하고, 이 프로젝트는 `psycopg[binary]==3.3.5`만 설치한다 |

`postgresql+psycopg://`는 Backend lane이 이미 쓰는 그 철자다(`.github/workflows/backend.yml`의 세 자리 전부). 추측으로 고르지 않고 설치 목록과 기존 lane을 읽어 맞췄다.

**reachability도 같이 고쳤다.** 수집기는 **원격 ref가 담지 못하는 head를 거부한다**(exit 2) — 아무도 check out 할 수 없는 증거는 증거가 아니기 때문이다. 그 판정을 `merge-base --is-ancestor` + `ls-remote` 신선도로 하는데, lane이 넘기던 `--reachable-ref`는 **base ref**였다. base는 정의상 PR head를 담지 않으므로 labelled PR 경로에서는 그 거부가 확정이었다. head ref로 바꾸고, checkout이 SHA로 fetch해 `refs/remotes/origin/*`을 남기지 않을 수 있으므로 **그 ref 하나를 명시적으로 fetch하는 단계**를 넣었다. 이 단계는 **검사를 통과시키는 것이 아니다** — ancestry와 live `ls-remote` 비교는 그대로 측정되고, branch에 없는 head는 여전히 거부된다.

### 7-2. F-R2 — gate가 가짜 PASS를 통과시켰다

Codex의 probe를 그대로 다시 만들어 **옛 gate(`50242e74`)에 걸어 보았다**: `verdict: FABRICATED_PASS`, `codeSha` 없음, `provenance` 없음, 17개 항목 전부 `PASS`에 `source: typed-by-human` — **exit 0, "shape accepted"**. 재현된다.

고친 방향은 "좋은 verdict를 요구"가 아니라 **묶음을 도출 과정에 결속**이다. 사다리로 하나씩 측정했다(각 줄은 앞 줄에 한 가지만 더한 것이다):

| 손으로 적은 묶음 | 새 gate |
|---|---|
| 1 Codex의 probe 그대로 | 거부: `pitr-configuration-possible`이 `'typed-by-human'`에서 왔다고 말한다 — 레지스트리의 주장은 `pitr_readiness`가 도출한다는 것이다 |
| 2 + 진짜 source 이름 | 거부: `verdict 'FABRICATED_PASS'`는 **수집기가 낼 수 없는** 값이다(집합은 수집기의 `EXIT_BY_VERDICT`에서 읽는다) |
| 3 + enum 안의 verdict(`PASS`) | 거부: `codeSha`가 없다 — 어느 commit을 말하는지 없는 증거는 무엇과도 맞춰볼 수 없다 |
| 4 + `codeSha` | 거부: `provenance`가 없다 |
| 5 + provenance, 다른 digest | 거부: `collectorSha256`이 **이 tree의 수집기 bytes**와 다르다 |
| 6 + 진짜 digest, 더러운 tree | 거부: `working_tree_clean_status`가 false다 |
| 7 + 깨끗한 tree, 다른 commit | 거부: 이 묶음은 `bbbb…`를 말하고 시험 중인 head는 `8d5a7d9b…`다 |
| 8 + 이 head | **통과.** 결속 전부를 만족시켜야 통과한다 |

묶은 축:

| 단언 | 왜 이것이 "모양"보다 센가 |
|---|---|
| `verdict`가 **수집기가 낼 수 있는 값**이고 **이 항목들에서 수집기 규칙이 내는 값**과 같다 | `overall_verdict`를 **import**해서 비교한다 — 주장이 "이 수집기가 이 항목들에서 내릴 결론이다"가 되고, "누가 여기 베껴 둔 규칙과 맞다"가 아니다. 없는 단어가 죽고, **FAIL 항목 위의 진짜 `PASS`도 죽는다** |
| `scope` 목록을 항목 status에서 **다시 계산**해 비교한다 | 요약이 인용하는 목록이 그것이다. 항목을 목록 사이에서만 옮기면 읽는 사람이 확인할 수 없는 주장이 된다 |
| **모든 항목의 `source`**가 수집기 catalog가 그 항목에 지정한 도구다. 이름 붙은 두 개는 **literal로 한 번 더** 확인하고 그 도구가 tree에 **파일로 있어야** 한다 | `typed-by-human`이 죽는다. 두 개를 catalog에서 읽어오기만 하면 **검사 대상에서 주장을 빌려오는 것**이 된다 |
| `codeSha` = `provenance.commit_sha` = `--expected-head` = **파일 이름** | lane은 glob으로 묶음을 찾는다. 다른 commit의 묶음이 같은 자리에 있으면 그것이 검사되고 통과했을 것이다 |
| provenance가 **깨끗하고 push된 checkout**을 말하고 **opt-out이 하나도 없다** | 수집기는 더러운 tree와 닿지 않는 head를 거부하고, 넘기면 그 사실을 기록한다. CI는 그 기록이 있어서는 안 되는 자리다 |
| `provenance.collectorSha256`이 **이 tree의 수집기 digest**다 | 묶음이 자신을 만든 bytes를 적고, gate가 그 bytes를 읽는다 |

### 7-3. 이 gate가 여전히 증명하지 못하는 것

**파일이 수집기에서 나왔다는 것을 증명하지 못한다.** 위 칸은 전부 위조하려는 사람이 계산할 수 있는 값이다(digest는 공개 파일의 해시고, provenance는 타이핑할 수 있다). 묶음을 증거로 만드는 것은 **CI가 같은 job에서 수집기와 이 gate를 head의 checkout 위에서 돌린다**는 사실이고, 결속은 위조에 **검토가 보는 코드 변경**을 요구하게 만든다. 그 이상을 주장하는 gate는 같은 실수를 자리만 옮긴 것이다 — 그래서 docstring에도 이 문장을 적었다.

**verdict가 좋은지는 여전히 판정하지 않는다.** 7-2의 단언은 "verdict가 이 항목들과 **일치**한다"이고 "verdict가 좋다"가 아니다. `FAIL` 묶음은 통과한다 — 시험의 첫 줄이 그것이다.

### 7-4. 검증

| 항목 | 결과 |
|---|---|
| gate 시험 | `tests/core/test_check_s12_acceptance_shape.py` **90 passed**(24 → 90) |
| 역방향 ratchet | `tests/core/test_post_landing_verify.py` **97 passed** — 이 workflow는 push trigger가 없으므로 lane을 지지 않는다(그대로다) |
| 실제 묶음 | 기준 head의 로컬 묶음(17항목, verdict `FAIL`)을 새 gate에 걸어 **통과**. CI가 넘기지 않는 flag 하나(`unpushedHeadAllowed`)만 CI 모양으로 맞췄다 |
| 가짜 묶음 | 위 사다리 8줄, 한 번에 한 가지씩 |
| dispatch | run **36851234615**(`76a14697`): migration·reachability 통과, 17항목 도출, artifact 생성 — 그리고 **§7-5**의 이유로 수집기 단계가 실패했다. 고친 뒤 다시 1회 돌린다. run id는 PR 코멘트에 적는다 — commit이 자기 자신의 run id를 담을 수는 없다 |


### 7-5. 첫 dispatch가 하나를 더 드러냈다 — 내가 적은 주석이 틀렸다

run **36851234615**(head `76a14697`)에서 `Apply the published migrations`는 **통과했다**(F-R1 해소). reachability 단계도 통과했고 묶음의 `remoteReachable`은 **true**다. 수집기는 **17개 항목을 전부 도출하고 묶음을 쓰고 artifact까지 올렸다** — 그리고 그 단계가 **exit 1로 실패**해서 gate 단계가 skip됐다.

원인은 내가 그 단계에 적은 주석이다: *"the collector exits 0 having recorded it."* **거짓이다.** `EXIT_BY_VERDICT`는 `FAIL`을 **1**로 보내고, `FAIL`은 오늘의 정직한 verdict다. **도구의 exit 표를 읽지 않고 도구의 모양에서 exit code를 단언했다** — 이 branch에서 내가 반복해서 지적받은 바로 그 형태이고, 이번에는 lane을 하루 더 빨간색으로 두는 값이었다.

고친 방식은 **verdict와 "측정 거부"를 구분하는 것**이다:

| exit | 뜻 | lane |
|---|---|---|
| 0 | `PASS` / `PASS_MEASURED_PARTIAL` | gate로 넘어간다 |
| 1 | `FAIL` | gate로 넘어간다 — **도달한 답이다** |
| 3 | `NOT_OBSERVED` | gate로 넘어간다 |
| 2 | 더러운 tree·닿지 않는 head·DSN 없음·덮어쓰기 거부 | **job 실패** — 판정할 묶음이 아예 없다 |

시험 `test_the_lane_continues_on_every_exit_code_that_is_a_verdict`가 workflow의 `case` 가지와 수집기의 `EXIT_BY_VERDICT`를 **양쪽에서 읽어** 비교한다. 둘이 다시 갈라지면 시험이 죽는다. `2`가 허용 목록에 **없는 것**도 같이 단언한다.

**그 run의 artifact를 내려받아 새 gate를 CI가 만든 묶음에 직접 걸었다**(gate가 CI에서 skip됐으므로): exit 0, `codeSha` = `76a14697…` = `--expected-head`, 파일 이름도 같은 head, `verdict FAIL` = 재계산값, 17항목 전부, `collectorSha256`이 이 tree의 수집기와 **일치**, `remoteReachable: true`, `working_tree_clean_status: true`, opt-out 기록 0. 묶음의 항목 분포는 로컬과 같았다(`PASS` 3, `FAIL` 6, `NOT_OBSERVED` 1, `BLOCKED_EXTERNAL` 7).

즉 **provenance 결속이 CI에서 실제로 성립한다는 것은 추측이 아니라 CI가 만든 그 묶음으로 확인했다.** 남은 것은 gate가 CI **안에서** 그 묶음을 읽는 것이고, 그것이 다음 dispatch다.

레지스트리 `VF-CL-04.ciVerified`는 **그대로 false**이고, 이 묶음은 **수락이 아니다**(`acceptanceClaim`은 언제나 `false`). r1에서 바뀐 것은 lane이 실제로 돌게 된 것과 gate가 손으로 적은 묶음을 거부하게 된 것뿐이다.
