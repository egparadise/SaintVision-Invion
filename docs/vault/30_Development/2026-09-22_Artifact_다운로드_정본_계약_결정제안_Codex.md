---
doc_id: "CODEX-ARTIFACT-DOWNLOAD-CANON-PROPOSAL-001"
title: "Artifact 다운로드 정본 계약 결정 제안"
version: "1.1.0"
status: "accepted"
author: "Codex"
updated: "2026-09-22T16:05:00+09:00"
source_of_truth: "Git"
---

# Artifact 다운로드 정본 계약 결정 제안

> 결정: 2026-09-22 코디네이터가 사용자 위임으로 **A `X-Content-SHA256` + storage object bytes**를 승인했다. 저장소 밖 `X-Checksum-SHA256` 운영 배포는 확인되지 않았다. 근거 출처는 코디네이터의 2026-09-22 답변이며, 옛 PC의 인트라넷 파일럿 컨테이너는 운영 배포가 아니었다. 따라서 레거시 호환은 계약에 넣지 않는다.

## 결정할 것

다운로드 응답의 무결성 정본을 현행 `X-Content-SHA256: <64 lowercase hex>`로 고정하고, 레거시 `X-Checksum-SHA256: sha256:<hex>`를 폐기할지 결정한다. 동시에 S03-ST가 읽을 실제 bytes의 정본을 DB 영수증이 아니라 검증된 storage volume object로 고정할지를 정한다.

## 비교

| 안 | 결과 | 위험 |
|---|---|---|
| A. 현행 정본 고정(권고) | `X-Content-SHA256` 하나, body bytes의 SHA-256과 exact match, volume object에서 읽기. 레거시 경로는 410/명시 오류 후 제거. | 저장소 밖 레거시 배포가 있다면 선행 업그레이드가 필요하다. |
| B. 전환기 이중 지원 | 두 헤더/형식을 일정 기간 수용하고 레거시 배포를 올린 뒤 제거. | 두 정본처럼 보일 수 있어 precedence·종료일·불일치 거부 규칙이 추가된다. |
| C. 미결 유지 | 코드 변경 없음. | 엄격 클라이언트의 레거시 다운로드 거부와 S03-ST 전송 공백이 유지된다. |

## 권고: A, 단 레거시 실배포가 확인되면 B로 한정 전환

정본 규칙은 다음과 같다.

1. 응답 body는 DB receipt JSON이 아니라 `result_commitment.object_id`가 가리키는 ready storage object의 bytes다.
2. `X-Content-SHA256`은 lowercase 64 hex이며 body digest와 다르면 서빙을 거부한다.
3. `Content-Length`, `Content-Type: application/octet-stream`, `Cache-Control: no-store`를 고정한다.
4. `X-Checksum-SHA256` 또는 `sha256:` 접두사는 정본 계약에 넣지 않는다.
5. 레거시 배포가 실제 존재하면 migration 기간과 종료 SHA를 기록하고, 두 헤더가 불일치하면 무조건 실패한다.

## 승인 후 착지 범위

우선 JSON Schema/생성 타입으로 `ArtifactDownloadMetadata`와 fixture를 고정한다. HTTP binary body 자체는 JSON Schema 대상이 아니므로 헤더·digest invariant 시험을 별도로 둔다. volume read route 구현은 S03-ST 카드로 이어가며 계약 착지와 운영 배포 완료를 구분한다.

결정 요청: **A 현행 정본+volume bytes(권고)** / **B 한정 이중지원(레거시 실배포 있음)** / **C 미결 유지**. 레거시 실배포 존재 여부도 함께 답한다.
