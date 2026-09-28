---
doc_id: "HISTORY-S11-AC11-LONG-SOAK-RUNNER-20260929"
title: "S11 AC-11 composite long-soak reference-only 생산자"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T02:26:32+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_id: "S11-BE"
acceptance_id: "AC-11"
tags: ["S11", "AC-11", "long-soak", "runner", "reference-only"]
---

# S11 AC-11 composite long-soak reference-only 생산자

## 작업 범위와 결과

- Card 124를 #217 head `35c5b207682c19cdc2be3e05df22e91bd4f4475f` 위에서 시작했고 구현 commit은 `0c71f75234bb1bec648135101b90a691a8cde4b2`, hosted fixture 보정 commit은 `b2976b8adadbab2a256522fdc356ec5d3a32c8b6`이다. PR은 #236이며 branch는 `agent/codex/ac11-composite-long-soak-runner`이다.
- `tools/run_ac11_composite_long_soak.py`는 G-19 `s01-readiness-inventory:1` 입력을 strict하게 검사한다. 정확히 5개 Node, ADR-100의 CP 겸임 1개와 독립 Ubuntu worker 4개, 고유 node/hostname/DNS/IP/install/certificate identity, `lan-workspace-v1`, 자원·폴더·NTP 입력이 모두 있어야 한다.
- dry-run은 기존 LAN pilot과 five-node preflight의 검증 함수를 재사용해 14개 exact case와 닫힌 fault class 집합을 전부 순회한다. 생성·시작·fault simulation·복구 관측·정리 receipt는 합성 메모리 상태에서만 만들고 SSH, Docker, LAN pilot state, PostgreSQL은 건드리지 않는다.
- dry-run report는 `referenceOnly=true`, `acceptanceClaim=false`, `verdict=NOT_OBSERVED`, `physicalActions=false`로 고정된다. JUnit 15개 항목도 reference-only skip이며 합격 수치로 세지 않는다. importer는 exact case/fault/receipt/child hash/source clean-tree 결속을 다시 검증한다.
- 실제 모드는 inventory 누락·수량·identity 불일치를 실행 전 `BLOCKED_EXTERNAL(G-19)`로, 유효 inventory만 있고 운영자 소유 physical adapter가 없으면 `BLOCKED_EXTERNAL(G-24)`로 끝낸다. 두 경우 모두 `execution.started=false`이고 Node 중단·fault injection·복구 작업은 없다.

## 검증

- `.venv/Scripts/python -m pytest -q tests/test_run_ac11_composite_long_soak.py tests/test_import_ac11_composite_long_soak.py tests/test_placement_benchmark_five_node_adapter.py` → **59 passed**, exit 0.
- `.venv/Scripts/python -m py_compile tools/run_ac11_composite_long_soak.py tools/import_ac11_composite_long_soak.py tools/five_node_lab_preflight.py` → exit 0.
- `python tools/check_docs.py` → exit 0.
- `python tools/check_contract_bindings.py` → exit 0.
- `python tools/check_frontend_integrity.py` → exit 0.
- `python tools/check_ontology.py` → exit 0.
- `python tools/check_doc_single_source.py --ratchet` → exit 0.
- `git diff --check` → exit 0.
- Docs hosted run `36454774423`, head `0c71f75234bb1bec648135101b90a691a8cde4b2` → success.
- 첫 Backend hosted run `36454774473`, head `0c71f752…`는 Python 3.12와 3.14 모두 제품 코드가 아니라 CLI fixture 1건에서 실패했다. checkout depth 1인 CI가 target 문서의 조상 commit을 갖지 않아 실제 `RepositoryGit` 검증이 `EvidenceImportError`로 닫힌 것이 원인이다. CLI fixture가 이미 `_git_value`를 격리했던 것과 같은 경계에서 importer Git reader도 명시적 `FakeGit(source, tree)`로 격리했고, 실제 importer의 ancestry fail-closed 구현은 바꾸지 않았다.
- 보정 head `b2976b8adadbab2a256522fdc356ec5d3a32c8b6`의 Backend run `36456314532`는 success다. Python 3.12와 3.14가 각각 **3844 passed / 49 skipped / 2 deselected / 0 failed**였고 두 job 모두 exact skip distribution gate를 통과했다. Docs run `36456314587`과 desktop-browser run `36456314615`도 success다. Core와 S11 hosted storage fault lane은 opt-in label이 없어 skipped이며 실행 증거로 세지 않는다.
- 로컬 `ruff`는 현재 Python 환경에 module이 없어 실행하지 못했다. PostgreSQL, Docker, SSH, LAN pilot state, 물리 Node는 사용하지 않았다.
- `python tools/sync_obsidian.py --check`는 공유 목적지의 기존 미관리 충돌 7건(작업판 양쪽 변경 3, destination edit 1, baseline 없음 3) 때문에 exit 3이었다. 이번 카드의 source 문서는 게이트를 통과했지만 worker 권한으로 `--apply`하거나 공유 목적지를 덮지 않았고 coordinator 정본 sync에 인계한다.

## 판정과 다음 행동

- 이 카드는 물리 long-soak 합격이 아니라 재현 가능한 reference-only 생산 경로다. AC-11 physical long-soak은 계속 `BLOCKED_EXTERNAL(G-19/G-24)`이다.
- Claude가 inventory 경계, 합성 결과의 합격 승격 차단, importer exact binding, 물리 실행 전 차단을 독립 검토한다. 검토·병합은 coordinator 소유이며 self-close하지 않는다.

관련 문서: [[S11_AC11_composite_long_soak_설계]], [[2026-09-28_21-38-56_KST_S11_AC11_composite_long_soak_repin_Codex]].
