---
doc_id: "ADR-S01-ST-STORAGE-ROUNDTRIP-001"
title: "S01-ST Storage SHA-256 왕복 검증기 설계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T10:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S01-ST"]
tags: ["S01-ST", "storage", "sha256", "artifact", "minio", "hosted-ci"]
---

# S01-ST Storage SHA-256 왕복 검증기 설계

## 1. 목적과 정직한 경계

`tools/verify_storage_roundtrip.py`는 합성 byte를 S3 호환 후보에 업로드하고 같은 object를 다시 내려받아 실제 SHA-256을 계산한다. 내려받은 byte와 digest는 제품의 `artifact_content_response()` 경계를 통과시켜 `X-Content-SHA256`, `Content-Length`, opaque body가 동일한 byte에 결속되는지도 확인한다. 마지막에는 자신이 만든 object만 삭제하고 재조회가 404인지 확인한다.

현재 제품의 운영 byte provider 정본은 `inv.object_store.LocalObjects`이고, S3 adapter와 공개 Artifact upload API는 아직 없다. 따라서 이 도구는 **S3 후보 byte 왕복과 제품 Artifact 응답 경계의 결합 preflight**이며, 실제 Run `OutputIngestion`→S3 adapter→DB commitment 전체 여정이나 Storage 제품 선정 완료를 주장하지 않는다. 일반 Artifact 90일/Evidence 1년/DB backup 35일 lifecycle 자동 GC도 이 카드에서 활성화하지 않는다. 직접 만든 합성 object의 삭제·부재만 GC 준비 증거로 남긴다.

## 2. 입력과 자격 경계

- 필수: `INV_OBJECT_STORE_ENDPOINT`, `INV_OBJECT_STORE_BUCKET`.
- 자격은 둘 중 정확히 하나다.
  - 환경: `INV_OBJECT_STORE_ACCESS_KEY_ID` + `INV_OBJECT_STORE_SECRET_ACCESS_KEY`.
  - 보호 volume 참조: `INV_OBJECT_STORE_CREDENTIAL_FILE=/run/saintvision/<flat-file>`; JSON에는 `accessKeyId`, `secretAccessKey`, 선택 `region`만 허용한다.
- endpoint/버킷/완전한 자격이 없으면 외부 호출 없이 `BLOCKED`, exit 3이다. 자격 두 경로가 동시에 있거나 파일 경로·mode·shape가 잘못되면 fail-closed `BLOCKED`다.
- endpoint는 자격증명·query·fragment 없는 HTTP(S), bucket은 S3 DNS 이름 규칙, region은 제한된 ASCII만 허용한다. 실제 endpoint, bucket, access key, secret, object key, provider 오류 원문은 stdout/JUnit/문서에 쓰지 않는다.

## 3. 실행 순서와 불변식

1. 32-byte 합성 payload와 임의 prefix의 단일 object key를 메모리에서 만든다.
2. AWS Signature V4로 path-style `PUT`을 보내고 payload SHA-256을 `x-amz-content-sha256`과 `x-amz-meta-content-sha256`에 결속한다.
3. 같은 key를 `GET`하여 status 200, byte length, metadata digest, 실제 다운로드 byte digest를 모두 비교한다.
4. 다운로드 byte와 artifact metadata를 `artifact_content_response()`에 넣고 `X-Content-SHA256 == sha256(body)`를 확인한다.
5. `DELETE` 후 `GET` 404를 확인한다. 어느 단계가 실패해도 `finally`에서 같은 key 삭제를 한 번 더 시도한다.

도구는 bucket 생성·삭제, lifecycle 변경, prefix 밖 목록/삭제, 운영 객체 overwrite를 하지 않는다. hosted lane은 별도 초기화 단계가 test bucket을 만들고, 도구는 실행마다 난수 key만 사용한다.

## 4. 결과와 판정

stdout은 redacted JSON 한 건만 낸다.

| status | exit | 의미 |
|---|---:|---|
| `PASS` | 0 | PUT/GET 실제 byte hash, 제품 `X-Content-SHA256`, DELETE/404 cleanup 전부 확인 |
| `FAIL` | 1 | 설정은 완전했으나 왕복·hash·제품 header·cleanup 중 하나가 실패 |
| `BLOCKED` | 3 | endpoint/bucket/자격이 없거나 신뢰 가능한 형태가 아님; 외부 호출 0회 |

결과는 `schemaVersion`, `status`, `checks` boolean, `payloadBytes`, `cleanupVerified`, `codeSha`, `observedAt`만 허용한다. endpoint·bucket·key·credential·예외 문자열은 금지한다. evidence JSON은 hosted artifact에 보존하며 Git에는 실제 자격이나 provider locator를 넣지 않는다.

## 5. 시험과 hosted lane

- PG-free 단위 시험은 가짜 transport로 SigV4 필수 header, PUT→GET→DELETE 순서, digest/header 불일치 FAIL, 입력 부재 BLOCKED/외부 호출 0, 예외 redaction, cleanup finalizer를 고정한다.
- hosted Core의 기존 `run-core` opt-in job에서 `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`를 명시적으로 기동하고 test bucket을 만든 뒤 verifier를 한 번 실행한다. GitHub Actions `services`에는 MinIO의 필수 `server /data` command를 지정할 수 없으므로, 동일한 disposable runner 안의 Docker service로 실행하고 `always()` cleanup으로 제거한다. Docker Hub 배포 중단 이후의 이 고정 upstream release는 오직 S3 호환 후보 실측용이며 운영 이미지 선정이 아니다. 실행 때 해석된 image digest, JUnit, redacted JSON을 `saintvision-core-evidence`에 포함한다. 로컬 Docker/실 PG는 실행하지 않는다.
- hosted PASS는 MinIO 후보 lane의 증거일 뿐 운영 제품 선정·TLS·전용 service credential·복원·lifecycle 인수는 아니다.

## 6. S01 preflight 및 설정 route 연결

- PR #129의 `/v1/operations/configuration-readiness`는 endpoint URL과 CA 구조가 준비됐는지만 이름으로 관측한다. 그 route의 `ready`는 왕복 PASS가 아니며 verifier 결과를 저장하거나 합성하지 않는다.
- PR #122 `s01_readiness_preflight`의 U6 후속은 `--storage-evidence <redacted-json>`을 받아 `status=PASS`, 현재 도달 가능한 `codeSha`, UTC `observedAt`, 모든 필수 check true일 때만 U6의 **Storage 왕복 증거**를 PASS로 볼 수 있다. 파일 부재·BLOCKED/FAIL·오래되거나 다른 SHA의 evidence는 U6 BLOCKED다.
- U6가 PASS여도 S01-ST `done`은 아니다. 실제 제품 선택, 운영 TLS/전용 자격, Run 전체 경로, lifecycle/복원 인수가 별도다.

## 7. 롤백

workflow step과 도구 파일을 제거하면 제품 runtime·공개 계약·migration에는 영향이 없다. 검증 중 생성한 object는 `finally` 삭제 및 404 부재 확인 대상으로 제한한다. cleanup이 확인되지 않은 FAIL evidence는 버리지 않고 hosted artifact로 남겨 운영자가 해당 test bucket/prefix만 조사한다.
