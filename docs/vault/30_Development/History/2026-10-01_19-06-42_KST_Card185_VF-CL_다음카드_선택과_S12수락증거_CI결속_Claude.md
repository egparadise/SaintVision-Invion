---
doc_id: "HISTORY-VF-CL-NEXT-CARD-20261001"
title: "VF-CL 다음 준비 카드 선택과 VF-CL-04의 ciVerified 공백 해소 — 수락 증거를 사람이 아니라 CI가 도출하게 (카드 185)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-01T19:06:42+09:00"
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

시험 24건이 각 거부 경로를 하나씩 고정한다 — 특히 **17개 항목을 하나씩 빼는 17가지 전부**를 돌린다(일부만 덮는 gate는 추첨이 된다), `acceptanceClaim`의 `True`·`None`·`"false"`·`0`·`1`, JSON escape로 숨긴 DSN, 그리고 **`FAIL` verdict가 통과하는 것**.

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
