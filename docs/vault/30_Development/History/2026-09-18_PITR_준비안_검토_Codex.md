---
doc_id: "HIST-CODEX-PITR-REVIEW-001"
title: "Claude PITR 준비안 소스 검토와 보류 조건"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T14:03:53+09:00"
source_of_truth: "Git"
---

# Claude PITR 준비안 소스 검토와 보류 조건

- task AC-12 준비안 검토, owner Codex(검토), 수정 owner Claude. base fc1959b, branch agent/codex/model-registry-binding.
- 대상 origin/agent/claude/vf-cl-cx01 8c72fbf22ac83de52b0959779f4c1a8b3c48486b, 제출 문서 PROPOSAL-CLAUDE-PITR-001 v1.1.0 및 docker-compose.pitr.yml. agent-delivery1.1.0/core-reliability1.0.0 적용.
- 판정: 아래 수정 전 착지 보류. 운영 적용 승인 요청 단계가 아니다. Docker/DB/운영 재실행 0; 소스 검토이며 실제 PITR 리허설 성공을 주장하지 않는다.

## 수정 요청

### PITR-R1-01 / P1: 논리 복원을 PITR 성공으로 판정

제안 §수용 경로 2와 인수 runbook은 recovery_drill exit0를 기능 PITR 성공으로 부른다. 현재 tools/recovery_drill.py:812는 pg_dump custom, :858은 pg_restore이고 :881은 백업 시각부터 복원 시작까지의 간격이다. --from-backup도 동일한 _restore_and_verify로 간다. 물리 base backup과 WAL replay, 목표 시점 복원 경로가 없다. 논리 복원 무결성 증거는 유효하지만 WAL PITR 검증을 대체하지 못한다.

수정 조건: 논리 복원과 PITR 리허설을 명시적으로 분리. 물리 백업 이후 기록 A, 목표 시점, 이후 기록 B를 만든 뒤 별도 격리 클러스터에서 WAL을 복원하여 A 존재/B 부재와 목표 도달을 확인하는 구체 경로·증거를 제출한다. 운영 배포 없이 준비 가능한 내부 작업이다. 현재 --require-operational-rpo가 fail-closed라는 본문 정정은 타당하며 마지막 '활성 후 해당 옵션으로 재확인' 문장도 이에 맞춰 고친다. 단일 drill 간격을 운영 보장으로 올리지 않는다.

### PITR-R1-02 / P1: 같은 호스트 MinIO를 off-host 내구성으로 간주

Tier B는 기존 minio에 전송하면 호스트 손실까지 보장한다고 서술한다. docker-compose.prod.yml의 minio는 같은 compose의 minio_data:/data이며 별도 장애 도메인·외부 복제 증거가 없다. S3 API 사용만으로 호스트 손실 내구성은 생기지 않는다.

수정 조건: 현재 same-host 구성의 한계를 표시하고 실제 별도 호스트/저장소 및 백업·WAL 동시 생존 조건을 별도로 정의한다. 격리 기능 리허설과 실제 off-host 인수를 분리하며 증거 없는 RPO 보장 표현을 제거한다.

### PITR-R1-03 / P2: archive_command 재시도와 내구성 준비 미완

Tier A의 test ! -f ... && cp ...는 동일 파일이 이미 있으면 항상 실패한다. 복사 후 성공 기록 전 장애로 재호출되면 정상 파일도 재시도 실패하며 WAL이 적체될 수 있다. 제출물이 fsync 부재를 인정한 점은 맞지만 '결정만 하면 바로 적용' 상태는 아니다.

수정 조건: 완전하게 지속 저장된 동일 파일의 재시도 성공, 다른 내용의 덮어쓰기 거부, 부분 복사/중단/재시도 검증을 갖춘 구현 또는 검증된 아카이브 도구를 준비한다. pg_wal 적체·저장소 고갈 경보/대응도 명시한다. 운영 저장소 적용은 별도 사용자 결정으로 유지한다.

### PITR-R1-04 / P2: 용량 및 timeout 설명 정정

archive_timeout=300이 완전 idle에도 전환한다는 설명은 틀리다. 지난 전환 이후 DB 활동 조건이 있다. 16MiB를 300초마다 전환하는 가정의 192MiB/시간·4.5GiB/일은 조건부 추정이며 idle 최소량이 아니다. 전송 지연/실패 때문에 timeout 설정만으로 RPO 상한도 보장되지 않는다. 미아카이브 WAL 보존을 wal_keep_size 효과로 설명하는 부분도 정정한다.

수정 조건: 세그먼트 크기·실제 WAL 발생률·압축·백업/WAL 보관 의존성을 명시하고 용량 산식의 가정을 표시한다. 정량 목표는 승인된 인수 기준을 따른다.

## 근거와 검증 범위

- git show로 위 고정 SHA의 제안/override를 검토하고 현재 recovery_drill 및 prod compose 소스와 대조했다(명령 exit0). 제출한 순수 함수 gate 결과는 Claude 보고로 수신했으며 Codex 재실행/실제 PG 리허설로 합산하지 않았다.
- [PostgreSQL 16 continuous archiving](https://www.postgresql.org/docs/16/continuous-archiving.html): pg_dump는 WAL 재생용 물리 백업이 아니다. 아카이브는 동일한 지속 저장 파일의 재호출을 처리해야 하고 실패 누적은 WAL 저장 공간을 고갈시킬 수 있다.
- [PostgreSQL 16 WAL 설정](https://www.postgresql.org/docs/16/runtime-config-wal.html): archive_timeout은 활동 조건이 있는 세그먼트 전환 설정이며 목표 복구에는 recovery.signal 및 restore_command 등 별도 구성이 필요하다.
- 다음 Claude: R1-01~04 수정 및 격리 PITR 리허설 증거 제출. 다음 Codex: 수정본 재검토. 현재 제출물 미병합, 운영 적용/AC-12 합격/운영인수 0/5 변경 없음.

## image 후속 수신 및 전달

사용자가 fc1959b 판정에 동의하고 unreadable의 이전 실패가 timeout, writable/business는 host-init이었다고 케이스별 정정했다. OneDrive 단일 원인 확정과 이번 skip만으로 R5-01 본문 실패 보존 검증을 주장한 부분도 철회했다. 기존 판정과 일치하며 새 실행 결과로 합산하지 않는다. 새로운 환경 조치나 진단 없이 동일 image lane을 반복하지 않는다.

fc1959b image 증거/정본 8파일 Obsidian scoped export 완료: 8 exported, 0 pending, 0 conflicts. CI는 결제/CLI 인증 외부 대기이며 재시도하지 않았다.

## 사용자 독립 소스 확인 수신 및 대기

확인 시각 2026-09-18T14:07:20+09:00, base f1bbf1d. 사용자가 R1-01(논리 pg_dump/pg_restore 및 백업 나이 지표), R1-02(same-host MinIO), R1-03(기존 파일 재호출 실패)를 독립 소스로 확인했다고 보고했다. 이는 사용자 소스 검토 수신이며 새 PITR 실행 성공이나 Codex 추가 재현으로 집계하지 않는다. R1-04 용량/timeout 정정도 기존 요청대로 미결이다. 사용자가 Claude에게 전달하고 수정 중이라고 보고했다.

git fetch origin 및 log/diff 확인 exit0: Claude tip 1ff43243c0475a33fab4b1f6cc981f0236c58281은 image 상태 지도 변경이며 PITR 파일은 8c72fbf 이후 수정되지 않았다. 제출 브랜치 보류 유지. f1bbf1d는 integration/all-agents-unified와 작업 branch에 반영됐고 Obsidian 5파일 hash 일치, pending0/conflicts0였다. 이전 integration 단축 ref push는 이름 충돌로 거부됐으며 정확한 integration/all-agents-unified ref로 정상 전달했다.

현재 승인 범위의 다음 Codex 행동은 Claude PITR R1-01~04 수정본·격리 리허설 증거 재검토다. 11e9f44 policy 설정 독립검토도 Claude 대기다. CI 결제/인증, 잔여 timeout 환경 진단, 원격 profile/mTLS, 실제 운영 PITR 적용은 각 담당 조건 대기다. 새 근거 없이 image lane을 반복하지 않고, Claude 구현을 중복 작성하거나 새 카드를 만들지 않는다. 이번 수신은 문서만 변경하며 Docker/DB/CI/원격 실행0, 제품 코드 변경0, 운영인수0/5 유지.
