---
doc_id: "ERR-WORKSPACE-BRIDGE-001"
title: "2026-09-10_WORKSPACE-BRIDGE_정적검사_오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T17:07:26+09:00"
source_of_truth: "Git"
---

# 정적 확인에서 수정한 사항

WORKSPACE-BRIDGE / base `dac25591adfb61a4a81382f737c4d1eed34c07d5`, owner Codex, reviewer Claude pending. [[2026-09-10_16-32-13_KST_WORKSPACE-BRIDGE_Codex_개발과정]]과 [[Codex Workspace 편집과 PTY 및 원격 Git 계약]]을 따른다. 이 문서는 실제 테스트 실패 보고가 아니다. 사용자 지시대로 pytest/Go test/DB 적용/Node 실행/브라우저 시험은 수행하지 않았다.

- 2026-09-10 KST 계약 생성 중 enum의 type 누락과 nullable type 배열을 현재 generator가 처리하지 못하여 `python tools/generate_contracts.py` exit 1. schema 정본에 string type과 anyOf(null)을 명시하고 다시 생성하여 exit 0. 생성 결과를 수작업 수정하지 않았다.
- 2026-09-10 KST 소스 정적 분석 `python -m pyflakes` exit 1: remote_git의 http.client, business_handoff/workspace_resume의 PrivateTree import가 남아 있었다. OneConnection/checkout_snapshot 통합 후 미사용 import 3개를 제거했다. 후속 결과는 build-only 인계 보고서에 기록한다.
- 코드 검토에서 원격 Git mutation의 응답 유실을 자동 retry하면 안 되는 점, 같은 원격 branch의 다른 작업이 미확정 dispatch를 우회하면 안 되는 점을 확인했다. durable dispatch와 remote_scope partial unique index, read-only reconcile로 반영했다. 실제 crash/동시성 검증은 아직 없다.
- WebSocket production dependency와 frame/queue/압축 설정 누락 가능성을 소스 검토에서 찾아 websockets 17.1과 명시적 uvicorn websocket 설정을 추가했다. 실제 handshake/PTY/브라우저 동작 성공을 주장하지 않는다.

초기 문서/파일 검색의 잘못된 경로와 Windows rg glob 조회 실패는 소스 변경 실패가 아니며, 실제 경로를 조회해 후속 읽기를 완료했다. 원본 docs/sources와 기존 worktree는 변경하지 않았다.
