# EvidenceEnvelope 서빙 앵커 거부 시험 및 커널 잔여 감사

- **작성자:** Codex
- **검토자:** Claude pending
- **측정 기준 SHA:** `de78c295b84ad6c3c92fef1cbd227fed36b62420`
- **브랜치/워크트리:** `codex/ontology-regeneration`, `.worktrees/codex-ontology-regeneration`
- **인터프리터:** `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe` (Python 3.14.6)
- **범위:** EvidenceEnvelope 서빙 앵커의 무효 응답 거부 여부와 동일 부류의 커널 앵커 잔여

## 구현 및 검증

`tests/core/test_evidence_envelope_serving.py`를 추가했다.

- `ResultStore.prepare`에 잘못된 EvidenceEnvelope를 넣으면 실제 `validate_contract("EvidenceEnvelope", ...)`가 `DomainError`로 거부한다.
- `RunStore.complete`에 잘못된 EvidenceEnvelope를 넣으면 같은 방식으로 거부한다.
- focused 실행: `tests/core/test_evidence_envelope_serving.py tests/core/test_serving_anchors.py` → **9 passed, exit 0**.
- `git diff --check` → **exit 0**.

### 변이 대조

- `services/control-plane/src/inv/results.py`의 EvidenceEnvelope 앵커를 제거한 뒤 `test_result_prepare_rejects_invalid_evidence_at_serving_anchor` 실행 → **실패(exit 1, KeyError)**.
- 원복 후 `services/control-plane/src/inv/runs.py`의 앵커를 제거한 뒤 `test_run_complete_rejects_invalid_evidence_at_serving_anchor` 실행 → **실패(exit 1, KeyError)**.
- 두 변이를 모두 원복하고 focused 시험 9개 재실행 → **9 passed, exit 0**.

따라서 두 시험은 스키마를 직접 부르는 시험이 아니라 서빙 메서드의 검증 호출에 의존하며, 앵커 제거를 놓치지 않는다. 변이 실패가 `DomainError`가 아닌 `KeyError`인 것은 앵커가 사라진 뒤 후속 로직이 malformed dict를 직접 읽었기 때문이며, 시험이 초록으로 남지 않았다는 것이 핵심이다.

## EvidenceEnvelope 전수 대조

소스에서 확인한 앵커는 다섯 경로다.

| 서빙 경로 | 앵커 | 현재 거부 시험 | 판정 |
|---|---|---|---|
| `results.py` `ResultStore.prepare` | 있음 | 새 serving rejection 시험 | 무게 확인 |
| `runs.py` `RunStore.complete` | 있음 | 새 serving rejection 시험 | 무게 확인 |
| `shard_completion.py` `ShardCompletion.once` | 있음 | 생성 envelope 정상 경로 시험은 있으나 malformed envelope 거부 시험 없음 | 잔여 |
| `storage_commit.py` `StorageSampleStore.accept` | 있음 | 정상 PG·샘플 무결성 시험은 있으나 생성 EvidenceEnvelope malformed 거부 시험 없음 | 잔여 |
| `storage_view.py` `StorageObservationView._verified` | 있음 | 저장 기록 변조 시험은 있으나 EvidenceEnvelope 스키마 위반을 직접 넣는 serving rejection 시험 없음 | 잔여 |

마지막 세 건은 “앵커가 없다”가 아니다. 현재 정상 생성·저장·변조 경로는 시험하지만, 앵커가 실제 malformed EvidenceEnvelope를 거부하는지는 아직 직접 고정하지 않은 상태다. PG 통합 fixture를 이용한 별도 시험이 필요하다. 이번 변경에서 복잡한 DB 경로를 얕은 mock으로 대체해 완료로 표시하지 않았다.

## 도구 경계

`tools/check_anchor_weight.py`의 현재 정적 인벤토리는 프런트 대면 7개 모듈 중심이라 `results.py`, `runs.py`, `shard_completion.py`, `storage_commit.py`를 직접 세지 못한다. 현재 실행 결과는 `7 rejection-tested, 7 called-only, 0 named-only, 1 no-serving-test`로, EvidenceEnvelope 잔여를 완전하게 표현하지 않는다. 따라서 이번 판정은 도구 결과가 아니라 소스 폐포와 시험 목록을 수동 대조한 것이다.

`check_contract_bindings.py`와 기존 fixture 계약 시험은 계약 모양을 확인하지만, 이 세 경로의 malformed EvidenceEnvelope가 실제 서빙 경계에서 거부되는지까지 대신 증명하지 않는다.

## 다음 담당

- Claude: 이 세 PG 경로에 대한 독립 검토 및 시험 설계 검토.
- Codex: 승인 후 `ShardCompletion.once`, `StorageSampleStore.accept`, `StorageObservationView._verified`에 각각 malformed EvidenceEnvelope 거부 시험을 추가하고 동일한 앵커 제거 변이를 실행.
- 현재 상태: EvidenceEnvelope 전체가 닫힌 것이 아니라, 두 경로의 서빙 거부 무게만 확인됨.
