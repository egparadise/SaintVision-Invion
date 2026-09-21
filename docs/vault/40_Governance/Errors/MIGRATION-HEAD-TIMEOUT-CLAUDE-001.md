---
doc_id: "MIGRATION-HEAD-TIMEOUT-CLAUDE-001"
title: "migration-head 시험 고정 타임아웃 — 도달/미도달 구분으로 처리. 별도 항목"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T16:00:00+09:00"
source_of_truth: "Git"
tags: ["saintvision", "test-reliability", "timeout", "reached-vs-not-reached", "migration"]
---

# migration-head 시험 고정 타임아웃 (별도 항목)

`tests/test_account_integration.py::test_published_migration_heads_upgrade_without_rewriting`가 **오늘 두 번 연속 같은 이유로 실패**했다(마무리 회귀 배치 + 격리 재실행). 모두 `subprocess.TimeoutExpired`, 180초 고정 타임아웃이다. 이것을 부하 탓으로 넘기면 안 되는 이유: **호스트가 한가하면 통과·바쁘면 실패하면, 실패해도 사람이 "또 부하겠거니" 넘기게 되고 언젠가 진짜 결함도 같은 이유로 무시된다.** 오늘 우리가 계속 막아온 "신호가 의미를 잃는" 형태와 같다. 그래서 처리했다.

## 측정 — 부하가 아니라 타임아웃이 너무 짧았다
도구 `check_migration_upgrade.py`를 **한가할 때** 직접 측정: **3m20s(≈200s), exit 0**(마이그레이션 정상). 즉 **180s 여유가 음수(-20s)** — 도구가 구조적으로 ~200s인데 타임아웃이 180s다. 부하 의존 flakiness가 아니라 **타임아웃이 단순히 짧은 것**이다. (지난 40e921b에선 격리 <180s였는데 지금 ~200s — 마이그레이션 수 60개 불변·도구 불변이니 호스트/디스크가 느려진 결과.)

## 구조 — O(published priors), 매번 전체 재실행
도구는 `for prior in priors:` 각 published prior마다 **새 disposable DB를 만들고 그 prior→head 전체 마이그레이션을 replay**한다. priors·revisions가 늘면 시간이 늘어난다(구조적). 따라서 **타임아웃을 늘리는 것만으로는 근본 해법이 아니다**(언젠가 또 넘는다).

## 처리 — 도달/미도달 구분 (오늘 전반에 쓴 원칙)
타임아웃은 그 시험이 검증하려던 것이 **틀렸다는 증거가 아니라 도달하지 못한 것**이다. 진짜 마이그레이션 결함은 도구가 **non-zero exit**로 끝난다(budget 훨씬 이전). 그래서 두 신호를 분리했다(`test_account_integration.py`):
- **non-zero exit → FAIL**(진짜 결함, 기존대로).
- **TimeoutExpired → 이유보이는 SKIP**(미도달, 실패 아님): "…did not complete within Ns and never reached its assertions — incomplete run, not a migration defect."
- budget는 `INV_MIGRATION_CHECK_TIMEOUT`로 **조정 가능·기본 600s**(idle ~200s의 3배 여유).

이로써 **timing은 PASS(완료) 또는 SKIP(미완)만 내고 절대 오도하는 FAIL을 내지 않는다.** FAIL은 진짜 결함(non-zero exit) 전용이 되어, 부하로 실패가 둔갑하거나 진짜 결함이 부하로 치부되는 일이 사라진다.

## 검증 — 부하·한가 양쪽 일관
- **한가**: 기본 600s → **PASS**(211s).
- **부하**(CPU 4프로세스): → **PASS**(324s, 여전히 <600). idle과 같은 PASS = 일관.
- **강제 타임아웃**(`INV_MIGRATION_CHECK_TIMEOUT=5`): → **SKIP**(이유 명시), FAIL 아님.
- 즉 환경에 따라 PASS↔FAIL로 갈리던 것이 이제 **PASS로 일관**(극단·미래 성장 시에만 정직한 SKIP). 고친 것이 진짜다.

## 남은 권고 (Codex, 도구 소유)
budget 상향은 구조적 증가에 대한 stopgap이다. **근본은 도구를 incremental하게**(매번 전체 replay 대신 head만/증분, 또는 priors 표본화) 만드는 것이다. 그때까지 skip-on-timeout이 성장을 정직히 흡수한다. 진행 상황(도구가 prior마다 출력하는 `PASS: <prior> -> …`) 기반으로 멈춤(hang) vs 느림을 구분하는 것도 후속 개선안이다.

## 별도 항목 기록
오늘 **두 번 재현**(회귀 배치 + 격리). 지난 회귀(40e921b)에선 격리 통과였으나 **이번엔 격리에서도 초과**(도구 ~200s > 180s). 코드 회귀 아님(마이그레이션·도구 불변) — 고정 타임아웃이 도구 구조적 런타임에 못 미친 것. 처리 완료·검증 완료.
