---
doc_id: "REVIEW-RECOVERY-PREREQ-LABELS-ARCHIVER-CLAUDE-001"
title: "Codex 3건 독립 검토 — recovery 전제 헬퍼·cleanup 라벨 확장·archiver 분류기. 소스+주입"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-20T15:00:00+09:00"
head_commit: "8c15e1a"
source_of_truth: "Git"
tags: ["saintvision", "independent-review", "docker", "delete-safety", "archiver", "no-values"]
---

# Codex 3건 독립 검토 (삭제 경로 포함)

HEAD `8c15e1a`(통합 tip) 기준. 삭제 기능이 있어 두 번째 눈이 필요한 3건을 검토했다. **기준 유지: 소스만 읽고 판단한 것(`[소스]`)과 실제로 주입해 확인한 것(`[주입]`)을 구분**한다. 이번 검토는 mocked `run` 주입만 썼고 실제 docker 자원은 만들지 않았다(정리할 것 없음). 값 미기록.

## ① `tests/recovery_drill_prerequisites.py::resolve_owned_postgres_container` — sound
전제 불충족(skip)과 안전 실패(fail)를 나누는 헬퍼. **`run`/`which` 주입으로 17경로 검증 `[주입]`**:
- **skip**: CX01_CONTAINER 미설정 · docker CLI 부재 · FileNotFound · TimeoutExpired · PermissionError · inspect `no such object`(컨테이너 부재) · inspect `daemon unavailable`.
- **fail(안전)**: 기타 OSError · 기타 inspect 오류(알 수 없음) · invalid JSON · 컨테이너≠1개 · malformed labels · **인정 라벨 없음** · cx01/kernel-test 빈 값 · codex-db `created-by` 부재/불일치 · created-by=codex인데 codex-db 라벨 없음.
- 전부 **fail-closed**(불확실하면 fail, 미충족이면 이유보이는 skip). 사용자 6경로 외 **놓친 경로 없음**.

**비대칭 판정(핵심): 의도적·타당 `[소스 추적]`.** `cx01`·`kernel-test`는 값만 truthy면 인정, `codex-db-test`는 `created-by==codex` 추가 게이트. 라벨 부착처를 추적하니:
- `ai.saintvision.cx01` → `tools/run_vf_security_tests.py`(일회용 보안테스트 컨테이너) + 내 실행.
- `ai.saintvision.kernel-test` → `tests/test_check_kernel_docker_hygiene.py`(일회용).
- `ai.saintvision.codex-db-test` → **repo 코드에 부착 없음**(Codex가 외부에서 부착).
즉 **repo 하네스가 통제하는 라벨은 존재 신뢰, 외부 부착 라벨은 provenance 게이트** — 합리적 신뢰 경계. 주입으로 `codex-db + created-by=claude → FAIL`, `created-by=codex 단독(라벨 없음) → FAIL` 확인. (관찰: cx01/kernel-test는 provenance 게이트가 없어 그 라벨이 오직 일회용에만 붙는다는 전제에 의존 — 추적상 참이나 codex-db보다 defense-in-depth는 한 겹 얕다. 결함 아님.)

## ② `tools/cleanup_owned_docker.py` 라벨 7→17 확장 — safe
10개 신규 라벨(codex-db-test/configured/cx01/guard/pitr-rehearsal.run/restore/rpo-network/rpo-test/storage-test/web-test)이 삭제 대상에 편입됐다(= 더 많이 지워지는 방향). **각 라벨 부착처를 소스로 추적 `[소스]`, 전부 일회용 test 자원**:
- `configured` → `run_approval_browser_test.py`·`run_vf_security_tests.py`의 **일회용 PG**(`--tmpfs /var/lib/postgresql/data`)·hygiene 테스트. (이름/값 "keep"이 의심됐으나 hygiene 테스트의 값일 뿐, 부착처는 전부 tmpfs 일회용.)
- `rpo-test`/`rpo-network` → `test_recovery_drill.py`(recovery drill), `web-test` → `test_web_container.py`, `restore` → `rehearse_independent_restore.py`, `guard` → `test_migration_role_guard.py`, `storage-test` → `check_storage_bundle.py`, `pitr-rehearsal.run` → pitr rehearsal, `cx01` → 위, `codex-db-test` → 외부+게이트.
- **오래 사는 자원에 붙는 라벨 없음.** 장수 workspace 라벨 `ai.saintvision.pilot`(`tools/lan_pilot.py`)은 **OWNERSHIP에 없어 미대상**.
- `test_cleanup_owned_docker_label_inventory.py`가 **모든 소스 라벨이 OWNERSHIP 또는 NON_CLEANUP으로 명시 분류됐는지 강제**(통과 `[주입: pytest]`) — 좋은 완결성 backstop. 단 **분류가 올바른지는 검증 안 함**(라벨이 어느 버킷이든 통과) → 나는 각 라벨의 disposable 성격을 소스 추적으로 별도 확인.
- 보호: `PROTECTED_PREFIXES`(saintvision-lan-db/saintview-orthanc)가 `_eligible` **첫 검사**(앞선 검토에서 인정 라벨 있어도 보호 우선 주입 확인). rpo-test/rpo-network가 이제 OWNERSHIP — 내가 앞서 지적한 backstop 갭이 닫혔다.
- **정정(사용자 언급 `NON_CLEANUP_LABELS`)**: 그 상수는 **도구가 아니라 위 테스트**에만 있다. 도구의 pilot 보호는 "OWNERSHIP에 없음 → ownership label absent로 제외"이지, 도구에 NON_CLEANUP 목록이 있는 것이 아니다. 결과는 동일(pilot 미삭제)하나 위치를 명확히 한다.

## ③ `_classify_archiver_connection_failure` (test_recovery_drill.py:105) — sound
host가 내부 네트워크 archiver에 못 닿을 때 skip/fail 분류. **9경로 주입 검증 `[주입]`**:
- running+ready+**무게시포트** → **skip**(네트워크 격리) · exited/startup fail → fail · running+FATAL로그 → fail · running+ready+**게시포트** → fail(게시포트면 닿아야 함) · running+ready없음+error없음 → fail(판별 불가) · **restart loop(running=True여도 restartCount>0)** → fail · ownership mismatch → fail · inspect 실패 → fail.
- 마스킹 `[주입]`: `password=<redacted>` · `postgresql://<redacted>@` · `<redacted-key>` — password·DSN·PEM 전부 가려짐(노출 0). 사용자 5케이스와 일치.

**사용자 질문(running+ready+무게시포트 세 조건이 동시에 참인데 실제로는 기동 문제일 수 있는가): 아니오 `[소스+주입]`.** skip은 `status==running AND running AND not restarting AND restart_count==0 AND ready 마커 AND FATAL/PANIC/ERROR 로그 없음 AND 무게시포트`일 때만 발동한다. **모든 기동 문제는 not-running·restarting·restartCount>0·error-마커 중 하나로 나타나 전부 skip 이전에 fail로 라우팅된다**(케이스 6이 증명: running=True+ready여도 restartCount>0이면 fail). 게다가 host↔내부네트워크+무게시포트 연결은 archiver 건강과 무관하게 **항상** 격리로 실패하므로, 그 상태에서의 연결 실패는 격리가 원인임이 확정적이다. **유일한 이론적 잔여**는 ready 로그 후 런타임 hang(기동 문제 아님, 어떤 inspect 기반 분류기로도 판별 불가) — 실질 위험 아님.

## 종합
세 건 모두 **sound, 결함 0**. 삭제/실행 경계가 fail-closed이고 라벨 확장이 일회용 자원에 한정됨을 소스 추적과 주입으로 확인했다. 소규모 관찰 2건(cx01/kernel-test의 얕은 provenance, `NON_CLEANUP_LABELS` 위치 정정)만 기록 — 결함 아님. 도구 소유는 Codex.
