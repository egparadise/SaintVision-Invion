---
doc_id: "ERR-ROUTE-SURFACE-20260914"
title: "2026-09-14 ROUTE-SURFACE Codex 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:44:22+09:00"
source_of_truth: "Git"
---

# 측정조건 정정

최초 시험이 /v1/settings를 BusinessDispatch의 선택 경로로 잘못 가정해 1개 실패했다. 실제 선택 경로 /v1/projects/{project}/members를 사용해 shadowing을 검증하도록 수정했다. 이후24개 통과, lazy WebSocket 보강 후unit23개 통과. [[2026-09-14_ROUTE-SURFACE_Codex_검증보고]]. 설정실패 출력은 credential을 노출하지 않고exit2를 반환하며 소스스캔으로 fallback하지 않는다.
