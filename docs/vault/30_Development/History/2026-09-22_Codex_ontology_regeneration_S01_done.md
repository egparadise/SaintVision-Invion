# 2026-09-22 Codex ontology regeneration and stale-output guard finding

## 착지

`docs/task-registry.json`에서 `S01-DB`와 `S01-FE`가 `done`으로 닫혔지만 Reverse-Ontology ABox가 이전 상태를 가리켜 `check_ontology.py`가 RED였다. 현재 통합 tip에서 ontology 생성물을 동기화했다.

- base / integration: `5c8db9f3ee3ad56c11948455a479ff9363d64cf4`
- 작업 브랜치: `codex/ontology-regeneration`
- 작업 워크트리: `C:\Project\SaintVision-Invion\.worktrees\codex-ontology-regeneration`
- 실행 시각: 2026-09-22 KST
- 실행 interpreter: `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe` (rdflib 7.1.4)

변경한 네 생성물은 다음과 같다.

- `ontology/example.ttl`
- `ontology/example.jsonld`
- `docs/vault/50_Ontology/Release-0.2.0/example.ttl`
- `docs/vault/50_Ontology/Release-0.2.0/example.jsonld`

각 파일에서 바뀐 의미는 두 상태뿐이다.

- `S01-DB`: `in_progress` → `done`
- `S01-FE`: `review` → `done`

## 확인

1. 변경 전 `python tools/check_ontology.py`: `ModuleNotFoundError`는 시스템 Python에 rdflib가 없어서 발생했다. 프로젝트 문서 환경의 절대 경로 interpreter로 다시 실행하면 stale 상태에서 `AssertionError`가 났다.
2. `python tools/generate_ontology.py` 실행 후 검증: RDF 405 schema triples / 916 data triples 생성, `check_ontology.py` exit 0.
3. 두 상태 중 하나를 되돌린 변형: `check_ontology.py` exit 1 (`Turtle and JSON-LD differ`), 원복 후 exit 0.
4. 최종 `check_ontology.py`: `PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors.`

생성기의 JSON-LD 직렬화는 RDF graph iteration 순서 때문에 반복 실행 때 바이트 순서가 크게 달라질 수 있다. 따라서 의미상 두 상태만 바뀐 이번 착지에서는 전체 JSON-LD 재직렬화 노이즈를 커밋하지 않고, 생성 결과와 의미가 같은 두 상태를 네 미러에 동기화했다. TTL은 반복 실행에서도 안정적이었다.

## 왜 생겼는가

registry 상태 변경과 ontology 생성이 하나의 명령으로 묶여 있지 않다. 사람이 registry를 `done`으로 바꾼 뒤 `generate_ontology.py`를 잊으면, 로컬 코드와 문서 검사는 일부 통과해도 registry↔ontology 대조 게이트에서 뒤늦게 RED가 된다. 이번에는 S01-DB와 S01-FE를 연속으로 닫았는데 두 번 모두 같은 누락이 발생했다.

현재 `check_ontology.py`는 stale output을 **발견**하는 게이트이지, 상태 변경 시 생성을 자동으로 수행하는 장치는 아니다. 그래서 다음 구조 개선은 별도 과제로 남긴다.

- `generate_ontology.py --check`처럼 임시 출력 graph와 추적 생성물을 의미적으로 비교하는 모드
- 또는 registry 상태 변경을 착지하는 workflow에서 생성과 stale 검사를 함께 실행하는 CI 단계
- JSON-LD는 바이트 diff가 아니라 RDF graph 동등성으로 비교해야 한다. 현재 serializer의 순서가 안정적이지 않기 때문이다.

이번 작업에서는 CI workflow나 registry 편집 도구를 넓히지 않았다. 우선 첫 CI와 새 PC 이전을 막는 RED를 제거했다.
