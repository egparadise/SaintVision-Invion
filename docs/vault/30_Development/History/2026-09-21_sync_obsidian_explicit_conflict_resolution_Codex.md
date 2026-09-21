---
doc_id: "SYNC-OBSIDIAN-EXPLICIT-CONFLICT-RESOLUTION-20260921-CODEX"
title: "Obsidian 동기화 명시 경로 충돌 해소"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Pending"
base_commit: "84f26ca"
updated: "2026-09-21T12:08:00+09:00"
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

## 다음 행동

Codex가 사용자로부터 정확한 승인 경로 목록을 받은 뒤 목록 파일을 확인한다. 공유 vault 전체 백업과 실행 전 `--check` 결과를 보존하고, 목록 대상만 처리한다. 잔여 충돌이 있으면 exit 3을 그대로 보고하며 임의로 목록을 확대하지 않는다. 사용자는 목록을 제공하기 전까지 본 기능을 실제 vault에 적용하지 않는다.
