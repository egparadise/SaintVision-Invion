---
doc_id: "ERR-DOC-004"
title: "ERR-DOC-004 Git 공백 검사와 원문 보존"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-09T15:37:31+09:00"
source_of_truth: "Git"
---

# ERR-DOC-004 Git 공백 검사와 원문 보존

git diff --cached --check가 원문의 Markdown hard-break 공백과 생성 파일 EOF 빈 줄을 보고했다.

해결: [[RES-DOC-004 Git 공백 검사와 원문 보존 대응]]. 제품 오류가 아닌 전달 환경/문서 검사 문제다.
