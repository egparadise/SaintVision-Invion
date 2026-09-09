---
doc_id: "PLAN-STORAGE-001"
title: "Storage 최종 개발 계획"
version: "1.0.0"
status: "baseline"
author: "Codex"
updated: "2026-09-09T15:10:54+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# Storage 최종 개발 계획

책임: **Claude; 무결성·경로·복구 Codex**. 공통 기준은 [[최종 개발 계획 - 모든 개발의 지침]], 주차별 작업은 [[24주 통합 실행 계획]]을 따른다.


## 저장 책임

S3 호환 object store에 binary, PostgreSQL에 metadata, Node 파일시스템+SQLite에 캐시 인덱스를 둔다. 사용자가 제공한 폴더만 StorageContribution으로 등록한다. Dataset read-only mount, Workspace persistent/ephemeral volume, Dataset/Model/Artifact/로그/암호화 원문/백업을 분리한다.

Claude 원문은 MinIO를 선정했다. **2026-09-09 공식 저장소에서 archive/source-only를 확인했으므로 신규 파일럿의 무조건 확정 제품으로 취급하지 않는다.** S01-ST에서 유지보수되는 S3 제품의 presign·multipart·checksum·보존·복원 검증과 license/배포 책임을 ADR로 확정한다. 후보 MinIO는 출처로 보존한다. 제품 미결이 URI·무결성·보존 계약 작성을 막지는 않지만 제품 배포의 ready 조건은 충족하지 못한다.

## URI·전송 계약

- Dataset/Model: `inv://datasets/<name>@<version>/<relative-path>`, `inv://models/<name>@<version>/<relative-path>`.
- Artifact: `inv://artifacts/<runId>/<artifactId>`; 실행 도중 해석된 실제 object version/digest를 RunRecord에 고정한다.
- Workspace: `inv://workspaces/<workspaceId>/<relative-path>`; policy scope 내 파일만 접근한다.
- 이름 최신 버전 허용은 조회·계획 입력에서만 사용하고 실제 실행에서는 불변 버전으로 고정한다.
- decode·절대경로·UNC/drive·`..`·정션/심볼릭 링크를 OS별로 확인하고 실제 open 시점도 경계를 검사한다.

업로드 init → presigned multipart → complete 요청 → 신뢰 worker의 실제 byte hash 검증 → active metadata 등록이다. 기본 part 16MiB, 최대 Artifact 50GiB, 4개 part 동시 전송, 업로드 URL 1시간/다운로드 15분이다. URL은 로그에 남기지 않는다. API는 대형 binary를 메모리 중계하지 않는다.

ETag나 사용자 metadata를 SHA-256 검증으로 대체하지 않는다. 미완료/검증 실패는 격리 staging에 유지하고 정해진 GC가 정리한다. 요청한 size를 quota에서 원자 예약하고 완료/취소 때 정산한다. URL 갱신에도 upload ID와 part evidence를 재사용한다.

## 지역성·캐시·볼륨

ready는 checksum·접근 정책·완전한 파일이 확인된 상태다. 전송 시간은 `(requiredBytes-localBytes)*8/effectiveBitsPerSecond`, 빈 데이터 locality는 0, link 미측정은 낙관적으로 0초라 하지 않는다. cache checksum은 사용 전 기록 대조·주기 재해시, LRU는 제공 공간 60% 한도, Node 동시 전송은 2개다. 활성 Lease가 pin한 cache는 축출하지 않는다.

Workspace의 미커밋 코드·파일은 단순 node 재배치로 살아난다고 보장하지 않는다. suspend/migrate 전 snapshot flush·hash·restore를 검증하고 장애 시 마지막 체크포인트 이후 손실 범위를 명시한다. 포맷·전체 디스크 편입·사용자 원본 GC는 하지 않는다.

## 보존·보안

일반 Artifact/로그 90일, Evidence 필수 참조 1년 이상 pin, Dataset·Model 수동 보존, DB backup 35일. app GC와 object lifecycle 모두 pin/hold/MLflow 접두사/진행 upload/활성 Run을 존중하도록 bucket/prefix 정책을 분리한다. DB에 없다는 이유만으로 즉시 object를 삭제하지 않고 upload ledger·유예 기간·reconciliation을 확인한다.

비밀은 credential provider 참조를 통해 주입한다. 필요한 민감 원문은 객체별 AES-GCM envelope encryption, KEK는 object와 다른 secret provider에 보관한다. 실제 비밀·환자 데이터는 Git·Obsidian·외부 AI context에 넣지 않는다. 초기 파일럿은 합성 Dataset이다.

## 검증

part 중단/재개, 내용 위조, complete 재호출, quota 동시 요청, cache 손상, 링크 탈출, GC와 upload 경합, backup 대상 장애, Workspace 복원, MLflow artifact 보존을 시험한다. 체크섬 불일치는 즉시 탐지하고 사용을 중지한다.
