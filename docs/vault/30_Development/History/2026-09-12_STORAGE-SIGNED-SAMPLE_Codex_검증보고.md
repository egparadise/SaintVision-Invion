---
doc_id: "HIST-STORAGE-SIGNED-SAMPLE-REPORT-20260912"
title: "2026-09-12 STORAGE-SIGNED-SAMPLE Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T12:19:39+09:00"
source_of_truth: "Git"
---

# 서명된 폴더 sample 수집·검증 전달

기준 2026-09-12T12:19:39+09:00 KST / 구현 `124fe97ec7d8b96dc0a7a4c73fbb5e358a392ef0` / base1947587 / agent/codex/workspace-bridge / PR19 draft. CX-02 무결성 하위 작업, owner Codex/reviewer Claude pending. S12-ST 원 owner Claude 유지. [[2026-09-12_STORAGE-SIGNED-SAMPLE_Codex_착수]], [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.1.0 / ADR-088.

## 구현한 범위

`inv/storage_sampling.py`는 내부 Python 수집/검증 모듈이다. 기존 ChannelProof의 tenant/node/epoch/version/endpoint/certificate pin과 실제 Run/project/contribution/root version, catalog 항목(ID/version/path/hash/size), catalogued 수, nonce/발급/만료를 불변 Challenge로 묶는다. 실제 Run 존재·프로젝트 권한은 이 함수의 ID 형식 검사로 입증되지 않는다. 후속 issuer가 기존 Run 인가와 일관 catalog 조회를 수행하고 발급한 challenge를 보존해야 한다.

로컬 ConfiguredSampler는 별도로 승인한 ReadRoot와 Node의 보호된 Ed25519 키/인증서를 받는다. request에서 root·key를 만들지 않는다. 기존 certificate_identity로 SAN/epoch/EKU/유효기간을 검사하고 현재 스냅샷의 지문 및 키 일치를 확인한다. CA 검증을 새로 구현한 것이 아니라 신뢰된 ChannelProof의 정확한 certificate bytes pin을 사용한다. 실제 장비 키를 Control Plane에 복사하거나 로드하지 않았으며 시험 키는 일시 생성했다.

실제 파일 검사는 CLI와 `saintvision.storage.sampling.check_sample`을 공유한다. 기존 ReadRoot/hash_file의 두 번 읽기·hash/size 검사를 사용한다. hash_file에 optional max_bytes를 추가해 열린 파일 크기가 예산을 넘으면 stream seek/read 전에 거부한다. 기본 CLI는 기존 제한/읽기 전용 출력 계약을 유지한다.

v1 범위는 sample 1~32개, 파일당1MiB, payload64KiB, challenge30초다. 최대 두 번32MiB(+변경 감지 byte) 읽기 범위이며 대형 학습 파일 점검을 지원한다고 주장하지 않는다. OS 파일 I/O 자체를 강제 취소하는 timeout은 아니다. 수집 후 만료/시계 역행/인증서 만료를 재확인해 늦은 결과에 서명하지 않는다.

JSON bytes는 정렬 키/ASCII escape/공백 없는 형태로 고정하고 domain prefix와 함께 Ed25519 서명한다. verifier는 크기/base64/서명/domain/정확한 challenge/시각/필드/개수/순서/항목 hash/size를 검사한다. Node가 보내는 healthy boolean은 받지 않고 실제 관측과 고정 catalog로 sample 판정을 계산한다. 누락 파일·기준 checksum 없음·잘못된 size·링크 탈출·과대 파일을 정상으로 판정하지 않는다. 조회하지 않은 catalog 수는 unsampled로 남긴다.

## 실제 검증

| 환경·명령 | 결과 | Evidence |
|---|---|---|
| 개발 중 pytest tests/test_node_storage_sample.py |56개→보완 후68개 통과; 실제 로컬 파일·임시 Ed25519 인증서 |최종 아래 같은68개 포함|
| Windows cx01_local.py tests/test_node_storage_sample.py tests/test_storage_check_integrity.py tests/test_verification.py tests/test_verification_readroot.py |clean124fe97, **124 passed/0 skipped/exit0**, warning1; 자체 생성 PostgreSQL 제거 완료|[Windows cases](../Evidence/storage-signed-windows-124fe97.json)|
| Linux check_kernel_docker.py --prepared ... --tests 같은4개 |clean124fe97, **129 passed/0 skipped/exit0**, owned cleanup 모두 성공|[Linux images/hashes/cases](../Evidence/storage-signed-linux-124fe97.json)|
| git push origin agent/codex/workspace-bridge |124fe97 exit0|PR19|
| 동일 SHA GitHub Actions 6개 |결제/한도 때문에 job 시작 전 실패|[CI ID와 원문 사유](../Evidence/storage-signed-124fe97-ci.json)|

Windows124=서명68+storage25+hash13+ReadRoot18; Linux는 ReadRoot Linux 전용5개 추가로129. 공통 시험 수를 합산해253개 고유 시험으로 쓰지 않는다. 위조/다른 domain·tenant/node/epoch/channel·Run/project/root/catalog/nonce 교체·만료·파일 손상·과대 입력·결과 누락·잘못된 관측 필드 등을 검증했다. 실제 네트워크 mTLS/Go 수집/물리 .225 시험은 수행하지 않았다.

## 남은 구현과 인계

이 모듈은 서명된 관측을 검증하지만 **운영 기록은0**이다. verify_sample의 같은 envelope 재검증은 허용하며 nonce 소비를 흉내 내는 메모리 cache를 만들지 않는다. VerifiedSample.recorded/operational_acceptance_assessed는 false다. 서명은 해당 키의 관측 진술이며 악성 Node의 정직한 실행·하드웨어 위치 증명은 아니다.

다음 Codex: (1) 이 내부 프로토콜을 공통 JSON Schema/Go Node의 보호 daemon에 연결하고 승인 root 설정/서명 키 사용을 검증한다. (2) 실제 Run/현재 프로젝트 권한·contribution/catalog 버전·ChannelProof/epoch를 고정하는 durable challenge 발급/소비를 구현한다. (3) 수신 증거 bytes/서명/검증에 사용한 인증서를 보존하고 동일 transaction에서 현재 권한·epoch·버전을 재검사한 뒤 기존 StorageCheck/inv.evidence를 연결한다. rollback/중복/동시 회수 시험이 필요하다. 공개 runtime에 광범위 public 테이블 쓰기 권한을 추가하거나 새 Evidence 원장·가짜 Run ID를 만들지 않는다. 기존 ResultView가 조회 정본이다.

Claude:124fe97/ADR-088 독립 검토 대기. Gemini: 아직 인증된 운영 건강/점검 완료로 표시할 입력이 생긴 것이 아니다. 실제 .225 profile/7개 시험·5대/GPU·운영 복원·CI 계정 해결은 별도 잔여다.

전체 성숙도 추정 **57.81% 완료/42.19% 잔여 유지**. S12-ST 기존50점 범위의 후속 구현이며 Go/DB/운영 인수 전에 추가 점수를 부여하지 않는다.

## 외부 제안 수신과 동기화

Obsidian 공통/Claude 작업판2개 외부 수정으로 --check exit1, 쓰기0이었다. [원문/hash](../Evidence/obsidian-proposals-20260912-storage-signed/manifest.json)를 보존하고 이번 정본에 수신 요약을 추가했다. Claude f17ad62b11f304e4991ac3c9d4324ed02ac38d44의 partition runner3파일 변경은 git show로 확인했다. 작성자7시험/27 partition/110→383일 주장은 이번 독립 실행 결과가 아니다. 운영 DB DDL/일정 배포는 수행하지 않았다. 과거 인증·저장소 보강/검토 기록은 그대로 유지한다. 최종 check/commit/push/동기화 결과는 전달 기록에 남긴다.

전달 검증: check_docs.py exit0(원문24·문서315·작업48), check_ontology.py exit0. git diff --check의 문서 끝 추가 빈 줄 경고를 정리하고 다시 검사한다. 제품 수정 없이 보고서만 추가했다.
