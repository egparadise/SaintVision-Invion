---
doc_id: "ERR-ENV-004"
title: "ERR-ENV-004 GitHub CLI 미로그인"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-09T15:37:31+09:00"
source_of_truth: "Git"
---

# ERR-ENV-004 GitHub CLI 미로그인

gh api 조회가 로그인 필요 메시지와 exit 1로 실패했다. Git push 인증과 gh 로그인은 별도다.

해결: [[RES-ENV-004 GitHub CLI 미로그인 대응]]. 제품 오류가 아닌 전달 환경/문서 검사 문제다.
