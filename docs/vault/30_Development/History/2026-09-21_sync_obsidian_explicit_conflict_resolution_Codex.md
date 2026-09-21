---
doc_id: "SYNC-OBSIDIAN-EXPLICIT-CONFLICT-RESOLUTION-20260921-CODEX"
title: "Obsidian 동기화 명시 경로 충돌 해소"
version: "1.2.0"
status: "review"
author: "Codex"
reviewer: "Pending"
base_commit: "84f26ca"
updated: "2026-09-21T12:03:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["sync-obsidian", "conflict-resolution", "file-safety"]
---

# Obsidian 동기화 명시 경로 충돌 해소

## 목적과 안전 계약

14개의 현재 충돌 중 사용자가 명시한 파일만 저장소 사본으로 해소할 수 있도록 `tools/sync_obsidian.py`에 제한된 경로 목록 옵션을 추가했다. 일괄 덮어쓰기 옵션은 없다. 실제 공유 vault에는 적용하지 않았다.

경로 목록은 UTF-8 텍스트 파일이며 한 줄에 `docs/vault` 기준 상대 POSIX 경로 하나를 적는다. 빈 줄은 무시한다. 절대 경로, 드라이브 경로, 역슬래시, `.`/`..`, `.obsidian`, 중복 및 빈 목록은 거부한다. 각 경로는 실행 시점의 현재 충돌이어야 하며, stale/non-conflict 경로가 하나라도 있으면 어떤 파일이나 state도 쓰기 전에 exit 1로 거부한다.

```powershell
.venv\Scripts\python.exe tools/sync_obsidian.py --apply --resolve-conflicts-from .work\approved-sync-paths.txt
```

일부 충돌만 목록에 있으면 목록 파일만 저장소 바이트로 원자 교체하고 각 경로의 정규화 해시를 state에 기록한다. 그 실행에서는 일반 pending export를 건너뛰고 미목록 충돌 및 사유를 계속 보고하므로 exit 3이다. 처리한 경로는 각각 출력 및 JSON `resolvedFromRepository`에 기록된다. 현재 충돌 전체가 목록에 있으면 일반 pending export까지 정상 수행하고 전체 해시를 확인한 뒤 exit 0이다. 사용자는 실제 14경로 목록을 별도로 제공할 예정이므로, 그 전에는 위 명령을 실제 vault 대상으로 실행하지 않는다.

각 대상은 스캔 당시 source/destination 원본 바이트 SHA-256을 재검사한 후 같은 디렉터리의 임시 파일에서 `os.replace`로 교체한다. 목록이 오래됐거나 검사 뒤 어느 쪽이 바뀌었으면 거부한다. 정상 EOL 비교 정책은 유지한다: 비교와 state는 CRLF→LF 정규화 해시를 사용하고, 덮어쓰기할 때는 저장소 원본 바이트를 쓴다.

## 확인 결과

- 실행 시험: `.venv\Scripts\python.exe -m pytest -q tools/test_sync.py` — **13 passed**, exit 0. 모든 경로는 temporary repository/vault를 사용했다.
- 경로 제한: 승인 목록의 충돌만 쓰고, 미목록 충돌을 남기며, 일반 pending export를 보류하고 exit 3을 반환하는 시험이 있다.
- 오래된 목록: 현재 충돌이 아닌 경로를 넣으면 exit 1이며 해당 대상·다른 충돌·state가 모두 변경되지 않는다.
- 완전 해소: 모든 현재 충돌을 목록에 넣으면 경로별 출력, state 갱신, 이후 `--check` exit 0을 확인한다. 같은 목록을 다시 쓰면 더 이상 충돌이 아니므로 exit 1로 거부된다.
- 유효성: 중복/절대/드라이브/역슬래시/상위 경로를 거부하고 `--check`에서 옵션 사용을 argparse exit 2로 차단한다.
- 되돌림 대조: 현재 충돌 여부 검사를 제거한 변형에서 `test_resolution_list_rejects_a_path_that_is_not_a_current_conflict`가 실패했다. `stale.md`가 실제로 덮어써지고 3으로 귀결되는 변형을 해당 시험이 탐지했다. 변형을 원복하고 전체 13시험을 다시 통과시켰다.
- 실제 사용자 vault 적용, 실제 14경로 목록 처리, GitHub Actions 및 Obsidian 열기는 실행하지 않았다.

## 사용자 실행 완료 수신 — 공유 vault 안정 상태

사용자가 vault 전체 백업 후 승인한 현재 충돌 14경로를 목록으로 전달해 실행했다고 보고했다. 실행 명령은 `.venv\\Scripts\\python.exe tools/sync_obsidian.py --apply --adopt-identical --resolve-conflicts-from <14-path-list>`이며 exit 0이다. Codex는 이 명령을 재실행하지 않았다.

- 사용자 보고: 88개 파일 기록, vault 총 파일 수 1307→1381. 이 두 카운터의 관계와 최종 managed 개수 차이는 제공된 보고만으로 재구성하지 않는다.
- 실제 내용 도달 예: `SYNC-OBSIDIAN-BLOCKED-CLAUDE-001.md`, `2026-09-19_감사에대한감사_Codex.md`가 vault에서 확인됐다.
- 사용자의 `Overview.md` 안 `2026-09-15` 설계 보강 문단이 그대로 보존됐다. 이는 사용자가 백업과 대상 목록을 준비한 뒤 실행한 보존 확인이다.
- 후속 `--check`: exit 0, **1370 managed files / 0 pending / 0 conflicts**. Obsidian 동기화는 현재 안정 상태다.
- 다음 문서는 현재 clean check 이후 별도 동기화 주기를 따른다. Codex의 resolver 변경 및 시험은 `549e697`에 있고, 공유 vault를 이 작업에서 별도로 다시 쓰지 않았다.

### 이번 정본 문서화 뒤 Codex read-only 재확인

Codex는 이어서 새 기록·진행판 변경 후 `.venv\\Scripts\\python.exe tools/sync_obsidian.py --check`를 실행했다. 이 checkout의 Git metadata state 기준으로 **7 no-baseline 충돌, exit 1**이 나왔고 파일은 쓰지 않았다. 목록은 전체 진행 현황, Codex 작업 현황, 검증 상태 지도, 이 sync 기록, 이전 sync/SSR 감사 기록, UI-FB 검토 기록, 검증 경계 종합이다. 사용자 이전의 1370/0/0 결과는 그 실행 시점에 대한 유효한 사용자 보고지만, 이후 이 문서 변경까지 반영된 최신 clean 상태라고 확대하지 않는다. 이 7건은 현재 충돌 여부와 사용자 vault의 최신 편집을 확인하기 전에는 새로 덮어쓰지 않는다. 새 check 결과 보고서만 `.work/obsidian-sync-conflicts.json`에 생성됐다.
