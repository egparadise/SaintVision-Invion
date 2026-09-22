# Claude `check_anchor_weight` 독립 검토

- 문서 ID: `HIST-CODEX-2026-09-22-CLAUDE-ANCHOR-WEIGHT-REVIEW`
- 검토자: Codex
- 대상 커밋: `9f96a541` (`check_anchor_weight` 범위·단위 명시 수정)
- 검토 기준 작업 트리: detached `9f96a541`, Windows, Python 3.14.6
- 작성자와 검토자를 같은 실행으로 취급하지 않음

## 결론

Claude의 수정은 승인한다. 도구가 먼저 스캔 범위를 출력하고, 타입 단위와 fresh/replay 분기
한계를 명시하며, 범위 밖 replay 앵커를 별도 보고하도록 바뀌었다. 따라서 출력 숫자를 전체
앵커 숫자로 읽는 위험은 크게 줄었다.

다만 이 도구는 위치별 무게 집계기가 아니다. `check_anchor_weight`의 권위 있는 숫자는
도구가 스캔한 **서빙 모듈 안의 타입 수**이며, 실제 앵커 위치 수나 전체 입력 계약 수가 아니다.

## 같은 SHA에서의 실행 결과

### 기본 범위

명령:

```text
python tools/check_anchor_weight.py
```

결과: exit 0, 다음을 출력했다.

- 7 rejection-tested
- 7 called-only
- 0 named-only
- 1 no-serving-test
- 합계 15개 **in-scope 타입**
- 범위 밖 replay 앵커는 `check_contract_bindings.py (2b)`가 권위 있고, 별도 negative-prior 시험이 런타임 무게를 담당한다고 출력

### 자기 시험

커밋에 포함된 도구 자기 시험은 `4 passed` (exit 0)였다. rejection 시험을 recorder로
변형했을 때 `rejection-tested`에서 `called-only`로 바뀌는지와 범위 밖 replay를 출력하는지를
확인한다.

### 확장 범위 측정

같은 도구에 다음 10개 모듈을 명시해 별도로 실행했다.

```text
--modules results,runs,shard_completion,storage_commit,storage_view,approvals,model_runtime,sandbox,tooling,workspace_resume
```

결과: exit 0, 7개 in-scope 타입에 대해 5 rejection-tested, 1 called-only, 1 no-serving-test.
`EvidenceEnvelope`는 다섯 모듈(`results`, `runs`, `shard_completion`, `storage_commit`,
`storage_view`)에 걸쳐 있지만 타입 하나로 출력됐다. 이것은 도구의 타입 단위가 실제로
위치 단위가 아님을 보여주는 대조다.

## 수동 집계와 자동 집계의 관계

| 계약 | 수동으로 센 위치/호출 | `check_anchor_weight`에서의 의미 | 판정 |
|---|---:|---|---|
| EvidenceEnvelope | 서빙 위치 5개 | 확장 실행에서 타입 1개, 위치 목록은 출력의 `anchors in [...]`에만 표시 | 불일치가 아니라 타입/위치 단위 차이 |
| WorkloadSpec | 입력 모듈 6개, 호출 지점 12개 | 서빙 응답 거부 도구의 범위 밖 | 입력 계약이므로 이 도구 숫자에 합산하지 않음 |
| ProjectId | 위치 5개 | 식별자/입력 계약이므로 범위 밖 | 응답 앵커와 같은 위험으로 합산하지 않음 |

`WorkloadSpec`과 `ProjectId`를 도구의 응답 타입 숫자에 넣지 않은 것은 누락이 아니라
의도적인 범위 분리다. 입력 계약은 별도 경계 시험과 실제 상태 전이 검증으로 판단한다.

## replay 12개와의 관계

`tools/check_contract_bindings.py`는 현재 다음을 별도로 보고한다.

```text
PASS: 48 fixtures ... 14 bound kernel responses ... 12 replay guards present
```

replay 12개는 `REPLAY_GUARD_COUNTS`에 파일·계약별로 등록되어 있다. `check_anchor_weight`는
이를 다시 타입 수에 섞지 않고 범위 밖으로 표시하며, replay의 런타임 무게는
negative-persisted-prior 시험이 담당한다. 이 분리가 맞다. replay를 fresh 서빙 타입의
rejection 결과로 간주하면, 실제로는 fresh만 시험된 경우를 숨기게 된다.

## 회귀 숫자 해석

`9f96a541` 자체에서의 기준선은 **7/7/0/1, 총 15개 in-scope 타입**이다. 이후 다른 SHA에서
7/8/0처럼 보이는 결과가 나오더라도 곧바로 회귀나 개선으로 읽으면 안 된다. 소스와 시험
집합이 달라졌을 수 있으므로 SHA, 범위, 실행 위치를 함께 비교해야 한다.

이번 수정은 다음을 명시해 숫자 변화의 의미를 보존한다.

1. 스캔한 모듈 목록
2. 타입 단위 집계임
3. fresh/replay 분기를 자동으로 분리하지 못함
4. 범위 밖 replay 앵커 목록과 권위 있는 검사기
5. 정적 proxy이며 실제 런타임 무게는 변이 시험이라는 점

따라서 독자가 `15`를 전체 앵커 위치 수로 읽을 가능성은 낮다. 다만 위치별 무게가 필요하면
별도 수동/전용 리포트가 필요하며, 이 도구가 그것을 주장하지 않는 것이 옳다.

## 이 갈래의 최종 상태

- replay 12개: `check_contract_bindings` 등록과 negative-prior 런타임 시험으로 분리 보호.
- EvidenceEnvelope 5개: 위치별 시험과 변이 대조를 Codex가 수행했으며,
  `shard_completion`은 이 Windows 호스트에서 Linux Node 전제 때문에 실행하지 않음.
- WorkloadSpec 6개: 5개 입력 경계의 거부 시험과 앵커 제거 변이를 완료. `shard_recovery`
  내부 호출은 중첩 `ShardRecoveryPrepareInput` 검증과 중복되어 별도 무게로 세지 않음.
- Claude 게이트: 범위·단위·fresh/replay 한계를 명시한 수정에 대해 독립 검토 완료.

이제 이 갈래의 남은 항목은 두 가지다. `shard_completion` Linux 실행과 WorkloadSpec의
전체 DB 통합 실행은 새 PC 또는 CI에서 수행한다.
