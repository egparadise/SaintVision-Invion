---
doc_id: "ERR-BACKUP-ROOT-20260912"
title: "2026-09-12 BACKUP-ROOT 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T02:53:19+09:00"
source_of_truth: "Git"
---

# 2026-09-12 BACKUP-ROOT 오류와해결

- 원본 e46d30d의 hash_file은 임의 외부 파일·junction·hardlink를 따라 실제 외부 bytes를 읽었다. 합성 파일 3개를 Windows에서 재현했고 8994eca root 경계에서 모두 거부했다. [원본 대조](../Evidence/backup-root-reproduction.json).
- 8994eca Linux 실제102개 중101통과/1실패(exit1): 같은 크기의 빠른 덮어쓰기에서 mtime_ns/ctime_ns도 같아 metadata 검사만으로 변경을 놓쳤다. 별도 Docker Python 실험에서도 before/after 크기15·두 시각 동일을 관측했다. [실패 evidence](../Evidence/backup-root-8994eca-failure.json).
- 6a72b9d에서 FileIO unbuffered 두 차례 bounded reread와 digest 일치를 추가했다. 같은 stat version 모사 + 실제 파일 덮어쓰기 시험을 추가했고 Linux103/Windows80 통과. sleep을 넣어 시험을 우회하지 않았다.
- Actions는 8994eca/6a72b9d 모두 결제/한도 문제로 job 시작 전 차단. 로컬 통과를 CI 통과로 대체하지 않는다.
- Obsidian check가 공통 진행판/Gemini 작업판 외부 편집을 발견하여 exit1·쓰기0. [원문/hash 보존](../Evidence/obsidian-proposals-20260912-root/manifest.json) 후 제안 수신 요약만 최신 정본에 병합하고 동일 bytes adoption 절차로 동기화한다. Gemini65.63%, Claude57.81%는 작성자 제안이며 이번 전체 검증 수치로 채택하지 않는다.

