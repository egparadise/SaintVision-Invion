---
doc_id: "CODEX-REGISTRY-CLOSURE-CANDIDATES-20260922"
title: "Registry closure candidate audit — S01-DB pattern"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T08:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# Registry closure candidate audit

## 범위와 판정 기준

2026-09-22 integration 기준으로 `planned` 33건과 `in_progress` 2건, 총 35건을 훑었다. S01-DB가 닫힌 방식인 **새 코드 없이 기존 계약 검증·설계 검토·인벤토리 증거를 모으고, 부족한 실제 DB 실행 증거를 채우는 경로**가 다른 과제에도 열려 있는지 확인했다.

후보에서 제외하는 조건은 다음과 같다.

1. 실장비, 실 IdP/CA/DNS, Storage 제품 또는 운영 인수가 필요하다.
2. 새 기능 구현이나 제품 연결이 필요하다.
3. 실제 API·브라우저 여정, 경합·부하, 복구·분할, GPU, 보안, E2E 또는 운영 인수 증거가 요구된다.

## 전체 모양

| 요구 증거 유형 | planned/in_progress 수 | S01-DB 방식 후보 여부 | 이유 |
|---|---:|---|---|
| 계약 검증·설계 검토·인벤토리 보고 | 2 | 후보 | S01-BE, S01-ST. 단, 각각 외부 블로커가 남아 실제 닫힘은 아님 |
| 실제 API·브라우저 여정·인증 실패 기록 | 3 | 아니오 | 실제 실행·인증 환경 필요 |
| 허용·거부 로그·exit code·증거 ID | 3 | 아니오 | 제품 실행 경로 증거 필요 |
| 만료 승인·취소·중복·재전송 통합 결과 | 3 | 아니오 | 통합 여정 필요 |
| 경합·snapshot/weight/policy·Explain | 3 | 아니오 | 경합·설명 결과 필요 |
| 소스 commit·WS/PTY·restart·restore | 3 | 아니오 | 재시작·복원 실행 필요 |
| Node 중단·분할·late result·cache 경합 | 3 | 아니오 | 장애·경합 실행 필요 |
| 보안·GPU·복원 | 3 | 아니오 | GPU/보안/복원 실행 필요 |
| golden eval·금지 행동 시험 | 3 | 아니오 | 평가 실행 필요 |
| Adapter·lineage·배포 digest | 3 | 아니오 | 외부 adapter/배포 증거 필요 |
| E2E·부하·복원·보안·접근성 | 3 | 아니오 | 다중 실행 환경 필요 |
| Release manifest·사용자 인수·web smoke·복구 | 3 | 아니오 | 사용자/운영 인수 필요 |

## 후보별 실제 판정

### 1. S01-BE — 현재 닫히지 않음

- 계약 검증, 설계 검토, 개발환경 및 소프트웨어 권한 경계 증거는 이미 있다.
- 그러나 실제 IdP/CA 연결은 확인되지 않았고, 관련 운영 값은 사용자 입력 대기다.
- 따라서 기록만 갱신하면 되는 순수 후보가 아니다. 사용자 입력과 그 범위의 증거가 먼저다.

### 2. S01-ST — 현재 닫히지 않음

- Storage 계약·URI·보존 코드와 일부 검증 증거는 있다.
- Storage 제품 선택, 실장비 5대, 허용 폴더·자원 인벤토리가 없다.
- 따라서 사용자 결정·장비 인수 전에는 닫을 수 없다.

## 결론

- **지금 추가로 닫을 수 있는 과제: 0건.** S01-DB가 현재 유일한 증거 정리형 닫힘이다.
- **사용자 입력이 오면 후보가 되는 과제: 2건(S01-BE, S01-ST).** 입력만으로 자동 done 처리하지 않고, 입력 후 해당 범위의 증거를 다시 대조해야 한다.
- **나머지 33건:** 실제 API/브라우저, 통합·경합·복구·보안·CI·운영 인수 중 하나 이상이 필요하다. 증거 문서만 정리해 닫을 수 있는 상태로 추정하지 않는다.
- S01-FE 등 `review` 상태 12건은 이번 planned/in_progress 선별 범위 밖이며 별도 reviewer 판정이 필요하다.

## 근거와 한계

- 명령: `Get-Content docs/task-registry.json -Raw | ConvertFrom-Json` 및 task별 `status`, `scope`, `evidence_required` 전수 그룹화.
- 기준 SHA: 현재 작업 트리 integration merge 기준(실제 반영 SHA는 커밋 시 기록).
- 이는 registry와 기존 History 문서를 읽은 분류다. 각 후보의 새 독립 실행을 수행한 것은 아니며, 후보를 done으로 변경하지 않았다.
