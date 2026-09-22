# EvidenceEnvelope 서빙 앵커 거부 시험 및 다중 앵커 감사

- **작성자:** Codex
- **검토자:** Claude pending
- **기준/브랜치:** `codex/ontology-regeneration`
- **인터프리터:** `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe` (Python 3.14.6)
- **실 PostgreSQL:** 소유 라벨 `ai.saintvision.owner=codex-evidence-envelope`, PostgreSQL 16 disposable container, host port 55441. 검증 후 제거 확인.

## EvidenceEnvelope 다섯 경로

| 경로 | 시험 | 결과 |
|---|---|---|
| `results.py` `ResultStore.prepare` | malformed envelope core serving rejection | 통과; 앵커 제거 변이에서 실패 |
| `runs.py` `RunStore.complete` | malformed envelope core serving rejection | 통과; 앵커 제거 변이에서 실패 |
| `storage_commit.py` `StorageSampleStore.accept` | 실제 PG에서 생성 envelope의 잘못된 `payload_sha256` 주입 | 통과; 앵커 제거 변이에서 시험 실패 |
| `storage_view.py` `StorageObservationView._verified` | 실제 serving subroutine에 malformed persisted envelope를 주입하는 core 시험 | 통과; validator 호출 기록이 없으면 시험 실패 |
| `shard_completion.py` `ShardCompletion.once` | aggregate completion에서 digest 변이로 malformed envelope를 만드는 PG 통합 시험 | 시험 추가 및 수집 확인. Windows 호스트의 Linux Node 런타임 조건으로 실행은 skip |

최종 실행:

- `tests/core/test_evidence_envelope_serving.py tests/core/test_serving_anchors.py tests/integration/test_storage_commit.py::test_generated_evidence_envelope_is_rejected_before_storage_commit` → **11 passed, exit 0**.
- storage commit과 storage view의 앵커 제거 변이는 각각 시험을 실패시켰다.
- `test_shard_parent.py::test_parent_completion_rejects_malformed_evidence_envelope`는 **1 test collected**이나 Linux Docker Node 조건 때문에 이 호스트에서는 실행하지 못했다. 이는 PG 부재가 아니라 Node 런타임/OS 조건이다.
- 별도 PG baseline에서 storage commit 정상 evidence 경로도 통과했다. 보호 컨테이너는 건드리지 않았고 disposable 컨테이너는 제거했다.

`storage_view`의 실제 DB 테이블은 `evidence_envelope_check` 제약으로 malformed envelope 저장 자체를 거부했다. 그래서 DB 제약을 제거하는 파괴적 시험 대신, 실제 `_verified` 서빙 분기를 fake row와 실제 validator로 구동하고 호출 기록을 확인했다. 이는 “DB가 먼저 막는 것”과 “서빙 앵커가 검증하는 것”을 섞지 않기 위한 범위 구분이다.

## 다중 앵커 계약 감사

소스의 `validate_contract`/`_checked` 호출을 타입별로 세어, 두 곳 이상에서 앵커되는 계약을 추렸다. 다중 앵커는 다음과 같다.

- `EvidenceEnvelope`: 5곳 — `results`, `runs`, `shard_completion`, `storage_commit`, `storage_view`
- `ApprovalDecisionInput`: 2곳
- `ApprovalId`: 3곳
- `AuthorizedCommand`: 2곳
- `NodeChunkInput`: 2곳
- `NodeExecutionPermit`: 2곳
- `NodeId`: 4곳
- `NodeProbeInput`: 2곳
- `NodeResourceSnapshot`: 2곳
- `NodeStorageChallenge`: 2곳
- `PolicyDecision`: 3곳
- `ProjectId`: 5곳
- `RunId`: 4곳
- `TerminalFrameInput`: 2곳
- `WorkloadSpec`: 6곳
- `WorkspaceId`: 4곳

이 목록에는 응답 계약뿐 아니라 입력·식별자·내부 도메인 값도 포함된다. 따라서 “다중 앵커=동일한 serving rejection 위험”으로 일괄 판정하지 않았다. 이번 우선 감사 대상은 여러 저장/서빙 경로가 같은 **EvidenceEnvelope 응답 계약**을 생성·조회하는 경우였다.

정적 test 이름 대조는 다중 앵커 중 한 모듈만 시험해도 타입 전체가 보호된 것처럼 보일 수 있다. `check_contract_bindings.py`의 타입 단위 집계와 `check_anchor_weight.py`의 7개 프런트 대면 모듈 인벤토리는 이 경로별 차이를 표현하지 못한다. EvidenceEnvelope는 이제 시험이 다섯 경로에 존재하지만, shard 경로는 이 호스트에서 실행 증거가 없으므로 **5개 모두 실행 검증 완료로 세지 않는다**.

## 남은 범위

- Linux Node 런타임이 있는 CI/새 PC에서 shard aggregate malformed-envelope 시험을 실행하고 앵커 제거 변이를 재현해야 한다.
- 다중 앵커 중 `WorkloadSpec`, `NodeResourceSnapshot`, `NodeStorageChallenge`, `NodeExecutionPermit` 등 실제 응답으로 쓰이는 계약은 다음 별도 카드에서 경로별 rejection weight를 확인한다. 입력·ID 계약은 응답 계약과 같은 기준으로 합산하지 않는다.
- `check_contract_bindings.py`의 타입 단위 결과를 경로별 결과로 확대할지는 별도 도구 설계 항목이다. 이번 작업에서 도구를 바꾸지 않았다.
