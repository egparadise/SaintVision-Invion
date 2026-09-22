---
doc_id: "HIST-CLAUDE-DECISION7-ALARM-LIVE-EVIDENCE-001"
title: "결정 #7 실 운영 증거 — 정본 tip 7168d573의 tools/alarm_check.py를 이 PC dev PostgreSQL에 실제 실행: P2 시각 스큐 알람 quiet (노드 0대라 quiet가 정상)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T21:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["decision-7", "clock-skew", "alarm", "live-evidence", "dev-pg", "GOV-ALERT-001"]
---

# 결정 #7 실 운영 증거 — dev PG에서 alarm_check 실제 실행

코디네이터 카드 (b). [[2026-09-22_결정7_시각스큐알람_활성화_구현_Claude]]가 병합된 **정본 tip**에서 도구를 **이 PC의 개발 PostgreSQL**에 대고 실제로 돌린 기록이다. 시험 하네스(일회용 DB·합성 노드)가 아니라 운영형 DB(dev)의 실제 상태를 읽은 것이라 "알람이 켜져서 돈다"의 첫 운영 증거다. 단, 이 DB에는 **등록된 노드가 0대**이므로 알람은 quiet이고, **quiet는 "시계가 정상"이 아니라 "볼 노드가 없다"는 뜻**이다(도구 출력 자체가 그렇게 말한다).

## 1. Provenance

| 항목 | 값 |
|---|---|
| 코드 | integration tip **`7168d573`**(= PR #41 병합 커밋), 워크트리 `.worktrees/claude-alarmev`, `git status --porcelain` 0줄 |
| 인터프리터 | `.venv/Scripts/python.exe`(py3.14.7), `PYTHONUTF8=1` |
| DB | 이 PC dev PostgreSQL 16(컨테이너 `saintvision-invion-dev-pg`, 127.0.0.1:55432, DB `invdev`), DSN = `.env` `INV_TEST_DATABASE_URL`(값 미기재), migration head **`0045_discovery_machine_credentials`** |
| DB 상태 | `inv.nodes` **0행 / online 0** (컨테이너 안 psql로 확인) |
| 실행 시각 | 2026-09-22T18:17:27+09:00 (KST) |
| 명령 | `python tools/alarm_check.py --dsn <INV_TEST_DATABASE_URL>` (텍스트) / 같은 명령 `--json` |
| exit | **0 / 0** (firing 없음) |
| 증거 파일 | `docs/vault/30_Development/Evidence/alarm-check-live-7168d573-20260922.txt`·`.json` (DSN·비밀 문자열 0건 확인 후 저장) |

## 2. 출력 (텍스트, 그대로)

```
ok  resource_snapshots partition 잔여: 100 day(s) of runway; partitions run to 2027-01-01
ok  audit_events partition 잔여: 100 day(s) of runway; partitions run to 2027-01-01
ok  evidence_envelopes partition 잔여: 100 day(s) of runway; partitions run to 2027-01-01
ok  체크섬 불일치: 0 mismatch(es) in folder checks over the last 7 days
ok  백업 실패 또는 복원 스모크 실패: 0 unverified backup(s), 0 non-passed drill(s)
ok  Node 이탈 감지 지연: 0 node(s) still marked online with no heartbeat for over 60s
ok  Node 시각 스큐 한도 초과: 0 online node(s) unmeasured or outside ±5s of 0 online; kernel already excludes them from scheduling

7 evaluated data families; 11 conditions not evaluated here; 0 governance-gated conditions.
```
이어서 not-evaluated 11건 목록과 "Nothing firing above does not mean the system is healthy…", "No channel is implemented…" 문구가 출력된다(전문은 증거 .txt).

## 3. 해석 (정직하게)

- **결정 #7 A가 정본에서 실제로 동작한다**: `Node 시각 스큐 한도 초과`가 governanceGated 버킷(0건)에서 나와 **평가 대상 7 family 중 하나**로 돌고, P2 판정 행이 출력된다. 활성화 전 tip에서는 이 행이 없고 `1 governance-gated conditions`였다(활성화 구현 문서의 CLI 실행과 대조).
- **quiet의 의미**: `of 0 online` — 이 DB에 online 노드가 없어 판정할 대상이 없다. **시계 정상의 증거가 아니다.** 물리 PC 5대가 등록되어 heartbeat로 `clock_skew_seconds`가 채워지기 전까지 이 알람의 firing 경로는 운영 DB에서 관측된 적이 없다(firing/해제 경로의 증거는 일회용 DB 7케이스 시험 [[2026-09-22_결정7_시각스큐알람_활성화_구현_Claude]] §2뿐).
- **채널 없음**: 도구는 여전히 "No channel is implemented"를 출력한다 — 통지 채널·수신자는 GOV-ALERT-001 §3 `unknown`(사용자 결정 범위 밖 그대로). 이 실행은 **판정**의 증거이지 **전달**의 증거가 아니다.
- dev DB의 다른 6 family(파티션 runway 100일·체크섬·백업/드릴·이탈)도 quiet — 역시 데이터가 거의 없는 dev DB라 "정상"이 아니라 "비어 있음"에 가깝다.

## 4. 다음

- 5대 등록 후 같은 명령을 다시 돌려 `of N online`과 실제 `clock_skew_seconds` 분포(±5초 보정 근거)를 기록 — S02-BE 인수 증거의 한 줄.
- 기록 채널이 정해지면 이 출력이 어디로 가는지(대시보드 알람 로그) Gemini 배선.

관련: [[S02_선행입력_체크리스트_2026-09-22]] §4 시각 동기화 항목 · [[알람 라우팅과 대응 주체]] · [[ERR-DESIGN-007 시각 동기화 요구 부재]]
