---
doc_id: "ERR-ENV-003"
title: "ERR-ENV-003 PowerShell Python 파이프 문자 인코딩"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-09T15:33:26+09:00"
source_of_truth: "Git"
---

# ERR-ENV-003 PowerShell Python 파이프 문자 인코딩

종류: environment. 제품 오류 아님.

PowerShell 문자열을 python stdin에 전달할 때 한국어가 물음표로 바뀌어 날짜 보고서 파일명에서 OSError 22가 발생했다. 보고서는 생성되지 않았다.

해결: [[RES-ENV-003 PowerShell Python 파이프 문자 인코딩 대응]].
