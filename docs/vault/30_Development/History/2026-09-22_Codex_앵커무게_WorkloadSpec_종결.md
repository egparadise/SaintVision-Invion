# WorkloadSpec 앵커 무게 재검토

- 문서 ID: `HIST-CODEX-2026-09-22-WORKLOADSPEC-ANCHOR-WEIGHT`
- 작성자: Codex
- 독립 검토: 대기
- 작업 브랜치: `codex/ontology-regeneration`
- 기준: `e9a786c7` 이후 Codex 작업 트리
- 실행 환경: Windows, Python 3.14.6, `C:\Python314\python.exe`
- 실행 시각: 2026-09-22 KST (각 명령의 종료 코드와 결과를 이 문서에 기록)

## 판정

소스 전수 대조에서 `WorkloadSpec`은 6개 모듈, 12개 호출 지점에서 사용된다.
입력 경계의 잘못된 값을 실제로 거부하는 독립 시험은 5개 모듈에 추가했고, 모두
통과했다. 5개 앵커를 하나씩 제거한 되돌림 변형은 각각 해당 시험을 실패시켰다.
따라서 5/6은 앵커와 거부 시험이 함께 무게를 가진다.

여섯 번째 `shard_recovery.py`의 명시적 내부 검증 호출은 별도 앵커로 세지 않았다.
`prepare()` 진입부가 `ShardRecoveryPrepareInput`을 먼저 검증하고, 생성 모델의
`ShardReplacementIntent.workload`가 `WorkloadSpec`으로 중첩되어 있기 때문이다.
잘못된 중첩 workload는 내부 호출에 도달하기 전에 거부된다. 내부 호출만 제거해도
새로운 허용 경로가 생기지 않으므로, 이를 독립적인 앵커 무게라고 중복 집계하지
않는다. recovery 자체의 DB/실행 검증은 별도 범위다.

## 추가한 경계 시험

`tests/core/test_workload_spec_input_anchors.py`에서 빈 workload를 DB·해시·런타임
접근 전에 주입했다.

1. `ApprovalStore.request`
2. `ModelRuntimeStore.prepare`
3. `sandbox.compile_launch`
4. `ToolGateway.claim`
5. `WorkspaceResume.prepare`

정상 실행: `5 passed` (exit 0).

각 검증 호출을 제거한 변형의 결과:

- approvals: 잘못된 workload가 다음 정책 검증으로 진행되어 시험 실패 (exit 1)
- model runtime: `tenantId` 접근으로 진행되어 시험 실패 (exit 1)
- sandbox: `resources` 접근으로 진행되어 시험 실패 (exit 1)
- tooling: workload 필드 접근으로 진행되어 시험 실패 (exit 1)
- workspace resume: `tenantId` 접근으로 진행되어 시험 실패 (exit 1)

EvidenceEnvelope 및 replay 회귀와 함께 실행한 선택 모음은 `25 passed` (exit 0)였다.
이는 WorkloadSpec 전체 경로의 실 PostgreSQL 또는 Linux 런타임 실행을 뜻하지 않는다.

## 오늘 밤 앵커 무게 누적

- **Run replay 12개**: 저장된 무효 prior를 심는 거부 시험을 추가해 replay 앵커가
  실제로 무게를 갖도록 했다. 앵커 제거 변형이 실패한다.
- **EvidenceEnvelope 5개 모듈**: 다섯 서빙 위치를 분리 집계했다. results, runs,
  storage_commit, storage_view는 실행 증거가 있고 shard_completion은 시험이
  수집됐지만 이 Windows 호스트의 Linux Node 전제 때문에 실행하지 못했다.
- **WorkloadSpec 6개 모듈/12개 호출 지점**: 다섯 입력 경계는 독립 거부 시험과
  변형 대조를 완료했다. shard recovery의 내부 호출은 중첩 정본 입력 계약이
  이미 같은 거부를 보장하므로 중복 앵커로 세지 않았다.

이 집계는 타입 개수가 아니라 **앵커 위치와 실제 거부 증거**를 세는 방식이다.
Claude의 `check_anchor_weight` 수정은 타입 단위와 위치 단위를 분리하는 후속 작업이며,
그 수정은 아직 독립 검토 대기다.

## 남은 범위

- `shard_completion`의 EvidenceEnvelope 경로: 시험은 존재하지만 이 환경에서
  Linux Node 런타임이 없어 미실행. 새 PC 또는 CI에서 실행해야 한다.
- WorkloadSpec 다섯 경계의 이번 시험은 핵심 입력 거부를 고정한 로컬 core 시험이다.
  모든 DB 통합·실행 경로를 실 PostgreSQL로 재실행한 것은 아니다.
- 타입 단위 게이트의 위치별 한계: Claude의 게이트 수정 및 독립 검토 대기.
- 이 기록 자체의 독립 검토 대기. 작성자 실행과 독립 검토를 합산하지 않는다.
