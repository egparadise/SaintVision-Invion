---
doc_id: "HISTORY-2026-09-22-ARTIFACT-CONTENT-CODEX"
title: "Artifact content 응답 계약 결속 및 브랜치 정리"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T01:53:00+09:00"
source_of_truth: "Git"
---

# Artifact content 응답 계약 결속 및 브랜치 정리

## 범위와 출처

- 작업 카드: `THREAD-2026-09-22-ARTIFACT-CONTENT-CONTRACT`; owner Codex, 독립 reviewer pending.
- 구현 branch: `agent/codex/artifact-content-contract`; 기준 integration SHA `8cb1251572de743ef14c6c8ec85dde3d7de65676`; 구현 SHA `65aec0ccbd276e35bd4707b93965b0b1b786debe`.
- 실행 worktree: `C:/Project/SaintVision-Invion/.worktrees/codex-artifact-content`. 코드 검증은 구현 commit의 clean tree에서 수행했다. 각 명령은 `tools/provenance.py`로 감쌌으며 Python은 `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` (Python 3.14.6), Node는 v24.17.0, 실행자는 Codex였다. 시각은 2026-09-22 KST 01:51경이다. PostgreSQL DSN과 Go toolchain은 이 실행 환경에 없었다.
- 직전 `agent/codex/response-freshness` 로컬 커밋 `33188d9f`는 integration 이력에 이미 포함됐음을 확인했다. 원격 ref `aca7378e`의 별도 후속 내용도 integration에 같은 결정이 반영된 것을 확인했다. 이력 불일치 브랜치 ref는 force-push하지 않고 원격 삭제를 요청해 성공을 확인했고, 기존 로컬 브랜치와 clean worktree를 제거한 다음 integration에서 이 작업 branch를 새로 만들었다. 증거 내용은 integration에 보존되어 있다.

## 구현

- `ArtifactContentResponse` JSON Schema를 canonical `contracts/v1alpha1/core.schema.json`에 추가하고 공유 fixture를 만들었다. 계약은 raw body가 `application/octet-stream`이며, 응답의 `Content-Length` 및 SHA-256이 nested `RunArtifactFile.byteSize`와 `checksumSha256`에 정확히 맞아야 함을 정의한다. 고정 disposition과 `nosniff`도 계약에 포함했다.
- `ResultView.download`가 bytes와 함께 manifest 메타데이터를 반환하도록 연결했다. HTTP 응답 생성 지점은 body 길이/hash를 검증하고 계약 validator를 호출한 다음 raw response headers를 만든다. 불일치나 계약 위반은 성공 응답으로 내보내지 않는다.
- Python 생성 모델/schema와 TypeScript 및 Go 타입을 생성했고, backend route와 frontend fixture 검사 및 PostgreSQL integration assertion을 추가했다. 화면 코드는 수정하지 않았다.

## 실행 증거

| 검사 | 결과 | 범위와 한계 |
|---|---:|---|
| `.venv/Scripts/python.exe -m pytest tests/core/test_artifact_content_contract.py tests/core/test_run_result_contract.py -q` | exit 0; 13 passed | 로컬 core 계약·route 경계. 2 deprecation warnings. |
| `tools/check_contract_bindings.py` | exit 0; 36 fixtures, 12 anchored kernel responses | 정적 contract binding/serving-anchor 검사. |
| `tests/integration/test_result_observation.py::test_result_and_download_match_actual_node_output_and_current_grant` | 1 skipped, 0 failure/error | 명시 사유: `INV_TEST_ADMIN_DSN`이 disposable PostgreSQL 16+를 가리키지 않음. 실 PostgreSQL 경로는 미검증이다. |
| `npm exec -- vitest run tests/run-result-contract.test.ts` | exit 0; 6 passed | frontend shared fixture/Ajv contract 검사. |
| `npm run contracts:check` | exit 0; 16 API response TS types 일치 | 생성 타입과 JSON Schema 간 검사. |
| `npm run build` | exit 0 | TypeScript 및 Vite build, 97 modules transformed. 브라우저 인수는 아님. |
| `tools/generate_contracts.py` | exit 0 | 생성물 갱신. formatter/newline 관련 FutureWarning은 있었고 생성 검사는 통과했다. |
| `git diff --check` | exit 0 | whitespace 검사. |

해당 테스트는 provenance wrapper로도 재실행했다. 실행 당시 환경은 Windows 11, Docker 이용 가능, PostgreSQL DSN 없음, Go 없음이었다. JUnit 파일은 만들지 않았으며 pytest/vitest console 출력이 결과 원본이다. 모든 결과는 작성자 실행이며 독립 검토 및 live PostgreSQL 인수는 미완료다.

## 되돌림 대조와 제한

1. 응답 helper의 `validate_contract("ArtifactContentResponse", response)` 호출을 제거했다. `test_artifact_content_route_refuses_contract_invalid_response_metadata`가 route의 200 응답을 관측하고 기대한 422 거부가 없어 실패했다. 호출을 복구했다.
2. canonical schema의 `contentType` 상수를 `application/json`으로 변형했다. frontend Ajv 검사는 즉시 실패했다. Backend 검사는 생성된 schema 사본을 읽으므로, canonical schema를 변형한 뒤 생성기를 실행하자 backend fixture 검사도 실패했다. canonical 값을 복구하고 생성기를 다시 실행했다. 즉 schema 변형은 생성 단계와 양 소비자 검사 모두를 통해 드러난다.
3. body/hash 길이 불일치, 필수 checksum 누락, 잘못된 media type, 음수 byte size 및 추가 필드의 거부 경로를 시험했다.
4. live PostgreSQL, 실제 브라우저, 배포 HTTP 경로는 실행하지 않았다. integration 시험의 skip은 제품 통과가 아니라 선행 DSN 부재다.

## 다음 행동

1. Claude가 `65aec0ccbd276e35bd4707b93965b0b1b786debe`를 고정 SHA로 독립 검토한다.
2. `INV_TEST_ADMIN_DSN`을 가진 disposable PostgreSQL 16+에서 integration test를 실행한다.
3. 통합 SHA에서 docs, ontology, 계약 검사 및 동기화 체크를 다시 기록한다.
4. 이후 계약 우선순위 지도에서 node usage contract는 사용자 모델 결정 대기, Go T1-3는 CI/toolchain 선행 조건 대기로 유지한다.
