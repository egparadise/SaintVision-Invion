---
doc_id: "HIST-APPROVAL-BROWSER-INTEGRATION-ERROR-20260915"
title: "2026-09-15 APPROVAL-BROWSER-INTEGRATION Codex 오류해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T00:22:02+09:00"
source_of_truth: "Git"
---

# 브라우저 통합 오류·해결

Playwright Node 도구 import는 default export 오류가 났다. Python Playwright1.62.0과 설치된Edge로 실행했다. pytest 초기2회positive는 pre2개 strict locator 오류, 실제command스냅샷으로선택범위를좁혀해결했다. negative는 origin과Run거부를혼동하지않도록명시Origin과409/AUTH-0032 검사를추가했다. 최종공개runner2passed/exit0,16.51s. 첫pass를운영검증으로계산하지않는다.

화면실측후 approved 반려버튼 비활성화 및 Diff/rollback미관측문구정정. 관련47unit/최종브라우저2case/build통과. source import의공백지적4개는e0b4b4f에서정리,diffcheck exit0.

Obsidian 최초sync는 외부편집3개로exit1/쓰기0. 원문보존/작성자보고와독립확인구분후동일바이트기준선만채택해재동기화한다. CI4건은계정결제제한으로시작전실패. [[2026-09-15_APPROVAL-BROWSER-INTEGRATION_Codex_검증보고]] 참조.
