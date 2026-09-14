---
doc_id: "HIST-ROUTE-SURFACE-START-20260914"
title: "2026-09-14 ROUTE-SURFACE Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:39:43+09:00"
source_of_truth: "Git"
---

# 실제 구성된 서버의 경로 측정

CX-01 owner Codex/reviewer Claude pending. base3dc96f0c5c2a70d61db13366f0ee4db9d397ef5a, branch agent/codex/workspace-bridge, agent-delivery1.1.0/core-reliability1.0.0. Claude fef3292의 route_coverage.py와 원저자시험을 가져와 기존정본을 확장한다(별도중복구현을 만들지 않음).

소스전체스캔이 demo/fixture까지더해 실제제공으로 보이는 위험을 줄이기 위해 --configured-surface 모드를 추가한다. 실제kernel factory와 선택된BusinessDispatch의 route만 읽는다. 환경검증 실패시 소스스캔으로 fallback하지 않는다. 합격: unmounted/demo route 미포함,실제선택한업무경로만포함,라우터prefix/WebSocket처리,잘못된경로입력 거부. 정적경로일치가 method/payload/권한/실장비인수는 아님을 출력에 항상명시한다.
