# R2-b push 게이트 exit hard-stop 적용

- 작성자: Codex
- 대상: `docs/vault/40_Governance/개발환경_이전_절차서.md`
- 기준 브랜치: `codex/ontology-regeneration`
- 목적: 검사 출력만 보고 commit/push하지 않도록 exit code를 행동 조건으로 강제

## 변경

PowerShell 절차의 문서·계약·프런트 게이트마다 다음 순서를 사용하도록 바꿨다.

1. 게이트를 별도 명령으로 실행한다.
2. 즉시 `$LASTEXITCODE`를 변수에 저장한다.
3. 0이 아니면 `throw`로 중단한다.
4. 모든 게이트가 0일 때만 개인 index의 commit/push 절차로 진행한다.

`;`로 검사와 행동을 이어 쓰는 예시는 제거했다. PowerShell 세미콜론은 앞 명령이
실패해도 다음 명령을 실행하므로 검사 결과가 장식이 될 수 있다.

## 변형 검증

임시 PowerShell 시험에서 게이트를 의도적으로 `exit 1`로 만들었다.

```text
BLOCKED as expected: gate exit 1
PASS: push action did not run
```

push 동작을 나타내는 임시 marker는 생성되지 않았고 시험 exit는 0이었다. 이 변형은
게이트 실패 시 다음 행동이 실제로 차단되는지만 검증하며 원격 push를 수행하지 않는다.

## 경계

- R2-b 규칙 자체의 공유 정본은 `7a65cc16`에 있다. 이 브랜치에서는 충돌하는 공유
  진행판 파일을 cherry-pick하지 않고, Codex가 사용하는 이전 절차서의 실행 예시만
  exit 조건형으로 고쳤다.
- 실제 commit/push는 모든 게이트가 0인 경우에만 수행한다. push 후 rev-range 파일
  검증은 별도로 유지한다.
