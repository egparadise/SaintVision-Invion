---
doc_id: "RES-DOC-004"
title: "RES-DOC-004 Git 공백 검사와 원문 보존 대응"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-09T15:37:31+09:00"
source_of_truth: "Git"
---

# RES-DOC-004 Git 공백 검사와 원문 보존 대응

오류: [[ERR-DOC-004 Git 공백 검사와 원문 보존]].

원문 bytes는 보존하고 gitattributes에서 archive와 Markdown 의도된 공백을 구분했다. 새 파일은 LF와 단일 끝줄로 정리, diff check exit 0, 원문 hash 검사 통과.

resolution_scope: documentation_delivery.
