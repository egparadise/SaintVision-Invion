---
doc_id: "HIST-VF-REGISTRY-AUTHORITY-REVIEW-001"
title: "frozen registry 권한을 approval·dispatch·admission에 결속(e2908a5) 독립 검토 (Claude)"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-19T09:00:00+09:00"
branch: "agent/claude/vf-cl-cx01"
task: "VF-CX (model registry binding)"
source_of_truth: "Git"
tags: ["saintvision", "independent-review", "model-registry", "cas", "admission", "security", "codex-authored"]
---

# frozen registry 권한을 approval·dispatch·admission에 결속(e2908a5) 독립 검토 (Claude)

CLAUDE.md 핵심 역할로 Codex의 `e2908a5`("Bind frozen registry authority to model approval dispatch and admission")를 독립 검토했다. 이 커밋은 사용자가 예고한 "frozen workload·승인·dispatch 결속" 산출물이며, merge `b378785`로 integration에 착지하면서 내 R2–R5 커밋(71fc9f5~d59b8a6)도 함께 착지했다. **판정: sound — 실제 결함 없음.** 실제 수행한 검증만 기록한다.

## 변경 표면

신규 `model_execution_registry.py`(+38), `model_runtime.py`(+30), `approvals.py`(+6), `db.py`(+8), 신규 시험 `tests/core/test_model_execution_registry.py`(+51)·`tests/integration/test_model_registry_runtime.py`(+145). 기존 `model_registry_binding.py`의 `revalidate`(transaction-scoped, 선행 커밋)를 활용.

## 결속 구조 (sound)

registry 권한을 frozen 바이트에 CAS로 결속하는, channel/source 패턴과 동형의 계층:

- **동결(freeze)**: `_scope`가 `current_registry(...)`로 `ModelRegistryBindingStore.revalidate`를 호출해 binding을 계산하고 튜플에 포함. `prepare`가 `if registry is not None: contents[REGISTRY_FILE]=canonical(registry)`로 스냅샷에 `model/registry.json`을 기록하고, idempotency payload에 `registryVersionId`를 넣어(sourceMode와 동일 원리) provider/authority 재생 차단.
- **admission(approved_model)**: 함수 말미에서 `frozen_registry(...)`가 스냅샷의 REGISTRY_FILE을 읽어 현재 registry를 revalidate하고 `encoded != canonical(current) → rejected()`. approved_model은 승인 **request(approvals.py:230)·grant(:435)·claim** 모두에서 호출되므로 registry 권한이 세 gate 전부에서 재검사된다.
- **idempotent replay**: `_registry_replay`가 저장 스냅샷/workload를 다시 읽어 workload 일치 확인 후 `frozen_registry`를 재실행 — 캐시된 commitment을 재생해 이후 은퇴/정책변경된 registry를 우회할 수 없다.
- **쓰기 재scope CAS**: 쓰기 트랜잭션의 `self._scope(...) != captured`가 이제 `registry`를 포함하므로 네트워크/캡처 사이 registry 변경이 커밋을 막는다(TOCTOU).

## 권한 검사의 실체 (`_current`/`revalidate`)

- `_current`: registry_version_id(str,len30)·manifest_hash(64hex) 검증 → `permission(...,linked=True)`(매 재사용 사업 권한 재확인) → manifest_sha256 일치 → `manifest_copy`(불변 계약) → **`(licensePolicy,classification) in policy.allowed`**(operator 정책 gate) → `public.model_registry_snapshot(...)`로 registry 잠금 후 **lifecycle 전수 검사**(`stage=='released'`, content/size 일치, `verified_at<=now`, `pinned_until>now`). 하나라도 어긋나면 `rejected()`.
- 반환 binding은 **안정 식별자와 정책 해시만** 담고(`registryVersionId`, manifestHash, contentHash, licensePolicy, classification, `bindingPolicyHash`, `executionAuthorized:False`, `requiresExecutionRevalidation:True`) **volatile 타임스탬프(verified_at/pinned_until)를 포함하지 않는다** — 정상 re-pin이 binding을 바꾸지 않아 유효 실행을 깨지 않으면서, lifecycle는 매 호출 `_current`가 신선하게 검사한다.
- `revalidate`: `_current` 재계산 후 저장 binding과 **byte 일치 CAS**(`saved['binding'] != binding → 409`), 생성·커밋·권한부여 없이 registry SHARE 잠금을 호출자 트랜잭션까지 유지 — TOCTOU 안전.

## 무downgrade·정책 결속 (대칭)

- policy None + registry None → None(legacy). 한쪽만 설정 → MODEL-0008. 둘 다 → revalidate.
- 정책 설정 상태에서 스냅샷에 REGISTRY_FILE 결여 → `current_registry(...,None)`이 MODEL-0008(legacy freeze를 정책 하에서 실행 불가). 반대로 정책 제거 후 registry-bound 스냅샷 → 역시 MODEL-0008. 양방향 downgrade 불가.
- binding에 `bindingPolicyHash` 포함 → 정책 변경(version/hash) 시 `saved!=fresh`로 무효화, 재바인딩 요구.

## 500 누출 점검

- `_registry_replay`가 쓰는 `bound_input`은 model_runtime.py:37 정의(manifest_sha256 재검증 포함)이고 binding 키(project_id/model_id/model_version/manifest_sha256) 전부 실재 — NameError/KeyError 없음.
- `frozen_registry`는 `json.loads`/`registryVersionId`/타입 오류를 `except (ValueError,TypeError,KeyError): rejected()`로 수렴. `_current`/`revalidate`는 모든 불일치를 DomainError/`rejected()`로 처리.
- **관측(결함 아님)**: `frozen_registry`의 `decode_snapshot(raw,...)`는 try 밖이라 손상 스냅샷이면 이론상 raise. 그러나 admission 경로는 직전에 `bounded_snapshot`으로 raw를 검증하고, replay 경로는 시스템이 freeze로 기록한 스냅샷을 읽으므로 실무상 안전 — 형제 코드(frozen_sources/approved_model)의 저장-스냅샷 신뢰 모델과 동일.

## 시험 커버리지 (non-vacuous)

- offline: frozen registry drop/change 거부, 정책 없는 registered input 불생존(무downgrade), BoundDatabase 정책 전파.
- 실 PG: 정상 launch; **은퇴 during-read → freeze 거부(TOCTOU)**; **은퇴 registry가 replay/approval/dispatch/claim/delivery 전 gate에서 거부**; 정책 removed/changed → claim 거부; 정책 설정 시 registry_identity 필수; 정책 활성화가 legacy freeze 재생 불가. 결속의 모든 gate와 무downgrade 양방향을 덮는다.

## 방법과 한계

- integration의 e2908a5 diff, 신규 `model_execution_registry.py` 전문, `model_runtime.py`/`approvals.py`/`db.py` delta, `model_registry_binding.py`의 `revalidate`/`_current`, 두 신규 시험을 정독·상호 대조. binding dict가 volatile 필드를 포함하지 않음을 직접 확인.
- 이 스위트는 `pytest.mark.postgres`+무거운 의존이라 **내 환경에서 실행하지 않았다**(정직 기록). Codex의 실 PG 증거(test_model_registry_runtime-coord-pg.json 등)가 첨부돼 있고, 나는 코드 경로·계약·정책/lifecycle 검사로 검증했다.

## 결론·인계

registry 권한 결속은 freeze(canonical binding 기록)→admission(revalidate+byte-CAS, request/grant/claim)→replay 재검증→재scope CAS의 계층이 일관되고, TOCTOU 안전(SHARE 잠금 유지), 무downgrade 양방향, 정책·lifecycle를 admission에서 신선하게 재검사하며, binding은 실행 권한도 volatile 필드도 담지 않는다. 500 누출·권한 우회가 없다. **finding 없음.** Codex에 sound 판정을 인계한다. 실 PG 실행 확인은 Codex 증거/CI가 수행했다.

## 후속 — 11e9f44 "Connect strict operator registry policy to configured control plane" 독립 검토 (2026-09-19)

e2908a5의 `RegistryBindingPolicy`를 operator config에서 제어평면에 연결하는 후속 커밋. 변경: 신규 `model_registry_config.py`(+21), `app.py`(+10), 시험 `test_model_registry_config.py`(+71). **판정: sound, finding 없음.**

- **operator-only 신뢰 경계**: `configured_registry_policy`는 `INV_API_CONFIG`(operator 파일, `trusted_file`+`strict_object`)에서만 온다. docstring "never accepted from a workload"가 코드와 일치 — 요청/workload가 정책을 주입할 수 없다.
- **엄격 검증**: top-level 키 `{"version","allowed"}` 정확 일치, entry 키 `{"licensePolicy","classification"}` 정확 일치(추가 키 차단), allowed 1..64, 각 str 1..256, 중복 pair 거부(`frozenset` 조용한 축소가 아니라 명시 거부). version 타입/길이는 `RegistryBindingPolicy.__post_init__`가 검증.
- **fail-closed·무유출**: 잘못된 present 정책 → factory `create_configured_app`의 `except Exception → RuntimeError('configuration unavailable')`로 **서비스 미기동**(legacy None으로 fallback 안 함), 원본 예외 대체로 **config 값 미유출**. 부재 → 명시적 legacy None(e2908a5 current_registry 로직과 정합).
- **시험 non-vacuous**: 16 거부 케이스(None/False/{}/추가키/version 타입·경계/allowed 빈·과다·중복·잘못된 part 타입·257자/**`executionAuthorized` 몰래 넣기**) + factory가 정책을 공유 Database에 전달·legacy None 유지·잘못된 정책 시 미기동/미fallback/**sensitive-sentinel 미노출**을 실증.
- **한계**: 이 시험은 DB/Docker 불필요(startup 검증)라 내 환경에서 실행 가능하나, 착지 회귀는 Codex/CI 몫으로 두었다. 코드 경로·계약으로 검증.

결론: operator 정책 config-wiring이 엄격·fail-closed·무유출이며 e2908a5 registry 권한과 정합한다. **finding 없음.** Codex에 sound 인계.
