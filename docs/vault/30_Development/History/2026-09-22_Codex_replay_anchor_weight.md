# Replay 앵커 무게 검증 — Codex

- 문서 ID: `HIST-20260922-CODEX-REPLAY-WEIGHT`
- owner: Codex / reviewer: Claude (독립 검토 대기)
- base SHA: `b0313282963294fa7e69d4d9a36f0983365ab120`
- branch: `codex/integration-merge`
- worktree: `C:\Project\SaintVision-Invion\.worktrees\codex-integration-merge`
- 실행 시각: 2026-09-22 09:46 KST

## 발견과 조치

Claude의 독립 변이에서 `prior is not None` 뒤의 12개 `validate_contract(..., prior)`가 모두 제거되어도 기존 44개 시험이 통과했다. 저장된 무효 prior를 replay에 주입하는 시험이 없었기 때문이다. 기존 앵커의 존재만으로 replay 경로가 보호된다고 볼 수 없었다.

이번 변경은 두 층으로 고정한다.

1. `tools/check_contract_bindings.py`에 감사 대상 12개 replay guard의 파일별 계약명·개수를 등록했다. 소스에서 `prior` 직후 검사가 빠지거나 개수가 바뀌면 게이트가 실패한다.
2. `test_run_creation_replay_anchor_rejects_an_invalid_persisted_prior`를 추가했다. 유효하지 않은 저장 prior를 create replay에 주입하면 `DomainError`가 나야 한다. 이는 대표 런타임 경로의 무게를 증명하며, 나머지 11개는 정적 inventory로 누락을 방지한다.

## 확인

명령은 모두 파이프 없이 실행했다.

```text
C:\Project\SaintVision-Invion\.venv\Scripts\python.exe tools/check_contract_bindings.py
exit 0 — 48 fixtures, 14 serving-anchor contracts, 12 replay guards present

$env:PYTHONPATH='services/control-plane/src'; C:\Project\SaintVision-Invion\.venv\Scripts\python.exe -m pytest tests/core/test_run_approval_observation_contract.py -q
exit 0 — 18 passed, 0 failed, 0 skipped
```

되돌림 대조로 `control.py`의 create replay 검사 한 줄을 제거했다.

```text
check_contract_bindings exit 1 — control.py:ControlRunView expected 1, found 0
replay negative test exit 1 — DID NOT RAISE DomainError
```

원복 후 위 두 검사가 다시 exit 0이 됐다. 따라서 게이트가 단순히 시험 파일의 존재를 세는 데 그치지 않고, 앵커 제거와 무효 prior 통과를 각각 잡는다.

## 경계

이번 런타임 무게 시험은 create replay 대표 1개다. 12개 모든 replay 분기를 실제 DB에서 무효 prior로 재현했다고 주장하지 않는다. inventory는 전수 누락 방지이고, 전체 DB replay 증거는 별도 검증이 필요하다.

