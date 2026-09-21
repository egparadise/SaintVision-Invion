---
doc_id: "HIST-2026-09-22-ALARM-COVERAGE-CODEX"
title: "GOV-ALERT-001 평가 범위 표기 정정"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-22T08:01:48+09:00"
source_of_truth: "Git"
---

# GOV-ALERT-001 평가 범위 표기 정정

## 발견

`GOV-ALERT-001` 규격은 20개 조건 행을 정의하지만, `alarm_check.py`는 여러 규격 행을 같은 런타임 데이터 가족으로 접는다. 예를 들어 partition runway의 P1/P2 경계와 중복 severity 행은 실행 시 하나의 관측 결과로 표현된다. 기존 `coverage` 문자열은 이 축약 항목을 규격 행의 분모처럼 표시해 `4 of 16 alarm conditions`라고 보고했다. 이는 규격의 20개 행과도, 실제 평가 단위와도 일치하지 않는다.

## 수정

커버리지를 허위 분모로 환산하지 않고 다음 세 버킷으로 표시한다.

- 평가한 런타임 데이터 가족
- 여기서 평가하지 않은 조건
- governance-gated 조건

알람 조건 자체나 라우팅 정책은 변경하지 않았다. 평가 불가 조건을 조용히 건강 상태로 취급하지 않는 기존 동작도 유지했다.

## 확인

- `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe -m pytest -q tests/test_alarm_check.py` → 수정 후 **12 passed**, exit 0
- 기존 분모 문자열을 되살리는 변형 → **1 failed, 11 passed**, exit 1
- 변형 원복 후 동일 시험 → **12 passed**, exit 0
- `git diff --check` → exit 0

이번 확인은 순수 판정 함수와 보고 문자열 범위이며 PostgreSQL 실행·CI·알람 전달 채널은 포함하지 않는다. Claude 독립 검토와 hosted CI는 별도 대기다.

