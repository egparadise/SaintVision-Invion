---
doc_id: "HIST-CODEX-S01-ST-STORAGE-ROUNDTRIP-001"
title: "S01-ST S3 호환 후보 저장소 SHA-256 왕복 preflight"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T07:35:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S01-ST"]
tags: ["history", "s01", "storage", "sha256", "artifact", "minio", "hosted-ci"]
---

# S01-ST S3 호환 후보 저장소 SHA-256 왕복 preflight

## 범위와 결정

- branch `agent/codex/s01-storage-roundtrip`, base `1e8baf04`, owner Codex, reviewer Claude다.
- 현재 제품 byte provider는 `LocalObjects`이고 S3 adapter·공개 Artifact upload API는 없다. Claude 검토와 코디네이터 결정에 따라 이 카드는 S3 호환 후보의 실제 byte PUT/GET/DELETE preflight와 U6 evidence 입력 구조 확인으로 한정했다. 제품 Artifact 경로, Run 전체 저장 경로나 운영 object store 선정 완료를 주장하지 않는다.
- endpoint·bucket·완전한 자격이 없거나 env와 보호 volume 자격이 모순되면 외부 호출 없이 `BLOCKED`/exit 3이다. 결과 JSON/JUnit에는 endpoint·bucket·object key·access key·secret·provider 오류 원문을 넣지 않는다.
- hosted Core `run-core` 레인만 고정 MinIO 후보를 기동한다. 로컬 Docker와 PostgreSQL은 실행하지 않았다.

## 설계 → 시험 → 구현

1. 설계 commit `5d3ed7ff`에서 입력·redaction·삭제/404 증명·#122 U6·#129 설정 route 경계를 먼저 고정했다.
2. 시험 commit `d8588b4c`에서 구현 파일 부재로 예상된 `FileNotFoundError`, pytest exit 2를 확인했다.
3. 구현 commit `1d24f690`은 AWS SigV4 path-style PUT/GET/DELETE, body/metadata digest, `finally` 삭제와 GET 404를 검증한다. 초기의 `artifact_content_response()`/`X-Content-SHA256` check는 제품 S3 경로를 거치지 않는 동어반복이므로 v1.1에서 제거했다. hosted workflow는 test bucket 생성과 verifier 실행 뒤 container를 `always()`로 제거하고 redacted JSON/JUnit 및 해석된 image digest를 artifact로 보존한다.

## 로컬 검증

실행 환경은 Windows, Python `D:\Project\SaintVisionI-Invion\.venv\Scripts\python.exe`이며 object-store 자격과 외부 endpoint는 주입하지 않았다.

| 검증 | 결과 |
|---|---|
| `python -m pytest tests/core/test_storage_roundtrip_verifier.py -q` | v1.1 20 passed, exit 0; M2 잔존 object 부정 대조 포함 |
| targetKind만 지정하고 저장소 입력 없는 CLI 실행 | `BLOCKED`, exit 3, network call 0 |
| `yaml.safe_load(.github/workflows/core.yml)` | parse 성공, exit 0 |
| `actionlint` | 실행 파일 부재로 NOT_RUN; hosted GitHub parser로 후속 확인 |
| `python tools/check_docs.py` | 894 versioned documents, exit 0 |
| `python tools/check_contract_bindings.py` | 54 fixtures/19 response types/14 replay guards, exit 0 |
| `python tools/check_ontology.py` | 48 task mappings/invalid fixture 4건 거부, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | baseline 18 pairs, 신규 중복 0, exit 0 |
| `git diff --check` | exit 0 |

## hosted 증거와 남은 경계

- 첫 hosted Core run `36355731393`은 archived upstream image의 Quay pull이 401을 반환해 verifier 전에 exit 1이었다. 두 번째 run `36355914520`은 digest 고정 image pull·bucket 생성과 후보 PUT/GET/body hash/metadata hash/DELETE/404는 모두 성공했지만, 당시 남아 있던 제품 응답 동어반복 check가 false라 schema 1.0 결과는 FAIL/exit 1이었다. 둘 다 최종 PASS 증거로 세지 않는다.
- registry/candidate 실패가 정상 Core 전체를 지운 결함을 해소하기 위해 같은 `run-core` gate의 별도 job으로 분리하고 publish를 loopback으로 좁혔다. evidence schema 1.1은 `targetKind`를 필수 enum으로 두고 PR head SHA를 기록한다. #122 U6은 `operational`만 받을 수 있으며 hosted `ci-candidate`는 U6 PASS가 아니다. M2 생존변이인 “DELETE 204지만 object 잔존”은 재조회 200을 주입해 FAIL하도록 시험을 추가했다. 최종 hosted 재실행은 PENDING이다.
- #129 route는 endpoint·CA의 구조적 readiness만 반환하며 이 왕복 결과를 저장하거나 합성하지 않는다.
- #122의 후속 `--storage-evidence`는 `targetKind=operational`, reachable PR head `codeSha`, UTC `observedAt`, PASS, 모든 필수 check true일 때만 U6 Storage 왕복을 PASS로 볼 수 있다. 이 카드에서 #122 branch는 수정하지 않는다.
- 운영 TLS·전용 service credential·Run `OutputIngestion`→S3 adapter→DB commitment·90일/1년/35일 retention/GC·복원 실측은 여전히 UNMEASURED/BLOCKED다.

다음 담당은 Claude 독립 검토다. 병합은 사용자/코디네이터 결정이며 Codex는 병합하지 않는다.
