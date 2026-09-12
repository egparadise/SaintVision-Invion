---
doc_id: "CONTRACT-STORAGE-SAMPLE-001"
title: "Codex 로컬 폴더 점검과 Node 증명 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T11:11:46+09:00"
source_of_truth: "Git"
---

# Codex 로컬 폴더 점검과 Node 증명 계약

ADR-086 / owner Codex / reviewer Claude pending. 구현8c6805f, Linux harness a7d0f5e. [[2026-09-12_STORAGE-CHECK_Codex_검증보고]]. Claude71cf2c0 collector를 검토해 같은 tools/storage_check.py 경로에서 보완했다. 별도 collector/hash 정본을 만들지 않았다.

## 가능한 동작

운영자가 별도로 지정한 --root와 tenant/contribution/declared node가 모두 일치할 때 해당 로컬 폴더의 catalogued file을 점검한다. --root를 DB path나 request parent에서 추론하지 않는다. ReadRoot(ADR-085)로 실제 bytes를 두 번 읽고 catalog checksum과 byte_size를 비교한다. sample은 정수1~1000, 쿼리도 LIMIT을 사용하며 total/검사한 수/검사하지 않은 수를 구분한다.

```text
python tools/storage_check.py --dsn-env INV_STORAGE_CHECK_DSN --tenant <tenant UUID> --node <선언 Node ID> --contribution <기여 ID> --root <운영자가 허용한 로컬 절대경로> --sample 32 --json
```

DSN은 보호된 실행 환경 변수로 공급하며 argv에 넣지 않는다. CLI는 잘못된 인수·접속 오류에 원본 DSN/예외를 출력하지 않는다. PostgreSQL READ ONLY + REPEATABLE READ 트랜잭션으로 catalog를 읽는다. --apply/--record는 제공하지 않는다. 명령행 옵션 문자열만으로 실제 node 소유권을 입증하지 않는다.

응답 scope는 local-storage-sample-v1, nodeBindingVerified=false, recorded=false, operationalAcceptanceAssessed=false다. sampleHealthy는 검사 대상으로 선택된 sample의 결과이며 전체 폴더/원격 Node/운영 인수 정상이라는 뜻이 아니다. sampled는 hash 기준이 있는 파일의 검증 시도 수(읽기 실패 포함), mismatches는 실패 수다. unverifiable은 기준 hash가 없는 파일이다. unsampled는 선택하지 않은 catalog 항목 수다. 빈 sample/기준 없는 항목/파일 오류/hash 또는 size 불일치는 sampleHealthy=false다. freeBytes를 경로 기반 disk_usage로 추정해 운영 건강 판정에 쓰지 않는다.

exit0은 선택 sample 일치, exit1은 sample 불일치·검증 불가, exit2는 잘못된 scope/설정·접속/루트 오류다. exit0도 Node 신원 확인·DB 운영 기록·인수 완료가 아니다. text와 JSON은 같은 판정식을 쓴다.

## 기존 StorageCheck

record_storage_check의 healthy는 reachable AND sampled_count>0 AND mismatch_count=0 AND unverifiable 없음으로 제한한다. counts는 실제 nonnegative int만 허용한다. 주의 대상 집계는 과거 healthy boolean을 그대로 신뢰하지 않고 zero sample/검증 불가 detail/미래 시각/같은 최신 시각의 실패를 재평가한다. raw DB 제약·과거 row를 이번에 변경하지 않는다. 직접 SQL로 과거와 같은 boolean을 만들 수 있으므로 raw healthy만 소비하면 안 된다. 서비스와 집계의 제한은 Node attestation의 대체물이 아니다.

## 다음 쓰기 경계

다음 Codex 구현은 기존 Node mTLS/identity/epoch 체계에 collection challenge와 서명된 결과를 연결하는 것이다. tenant·node·contribution·승인 root 설정 버전·대상 catalog digest·challenge/만료·epoch·실제 결과 hash를 함께 묶고, 서비스가 현재 권한/최신 epoch/중복 결과를 확인한 뒤 기존 StorageCheck/Evidence에 원자적으로 기록해야 한다. root 승인·node 인증·관측의 freshness가 없으면 기록하지 않는다. 새 DB 원장을 별도로 복제하기 전에 기존 kernel Evidence와 idempotency 계약을 확인한다.

Claude는 이 보완본을 독립 검토하고 운영 절차를 조율한다. Gemini는 sample 일치와 Node 증명/운영 상태 unknown을 구분해야 한다. 실제 .225 설치/7개 시험과5대 인수는 이 로컬 점검으로 충족되지 않는다.

