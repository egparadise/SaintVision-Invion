# 2026-09-22 Codex semantic ontology generation check

## 구현

`tools/check_ontology_generation.py`를 추가했다. 이 도구는 실제 checkout을 덮어쓰지 않고 임시 복제본에서 `generate_ontology.py`를 실행한 뒤, 다음 네 생성물을 RDF graph로 파싱해 삼중항 집합을 비교한다.

- `ontology/example.ttl`
- `ontology/example.jsonld`
- `docs/vault/50_Ontology/Release-0.2.0/example.ttl`
- `docs/vault/50_Ontology/Release-0.2.0/example.jsonld`

차이가 있으면 `missing`/`unexpected`와 함께 주어·술어·객체를 출력한다. JSON-LD 배열 순서나 Turtle 직렬화 순서는 의미 비교에 영향을 주지 않는다.

`.github/workflows/docs.yml`에도 이 검사를 추가했다. 이제 registry를 닫고 생성물을 갱신하지 않으면 CI docs lane에서 semantic diff와 구체적인 triple이 표시되며 실패한다.

## 양방향 회귀 증거

- 정상 tip: `python tools/check_ontology_generation.py` exit 0 (`4 ontology artifacts are graph-equivalent`).
- registry의 `S01-DB` 상태만 `done → review`로 바꾸고 생성물을 갱신하지 않은 임시 checkout: exit 1, `S01-DB` 관련 `missing`/`unexpected` triple 출력.
- JSON-LD `@graph` 배열만 역순으로 만든 임시 checkout: exit 0. 직렬화 순서 변경을 오탐하지 않는다.
- 회귀시험: `tests/core/test_ontology_generation_check.py` 2 passed.

## 게이트 판정

미검출 잔량은 이번 핵심 결함(상태 변경 후 ontology 미재생성)에 대해 0이다. 순서만 바꾼 JSON-LD는 통과했고, 실제 registry drift는 구체적인 차이와 함께 실패했다. 따라서 report-only가 아니라 docs CI gate로 올렸다.

현재 검사는 생성기를 임시 복제본에서 실행하므로 작업 트리의 생성물을 덮어쓰지 않는다. JSON-LD serializer의 바이트 순서가 비결정적이므로 바이트 diff는 사용하지 않는다.

## 범위

검사는 registry 정본과 생성 ontology의 의미적 일치만 보장한다. registry 상태를 바꾸는 명령 자체와 done 판정의 증거 충분성은 별도 책임이다. `check_ontology.py`의 RDF/SHACL/registry 검사는 계속 함께 실행한다.
