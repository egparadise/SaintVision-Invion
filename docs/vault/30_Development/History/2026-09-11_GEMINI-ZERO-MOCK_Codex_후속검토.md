---
doc_id: "REVIEW-GEMINI-ZERO-MOCK-20260911"
title: "Gemini Zero Mock 수정본 Codex 후속 검토"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T13:21:00+09:00"
source_of_truth: "Git"
---

# Gemini 5899eb2 후속 검토: request_changes

Codex가 root integration checkout 5899eb2의 변경·관련 소스를 읽은 정적 교차 검토다. Gemini의 [[2026-09-11_STUDIO-ZERO-MOCK_Gemini_검증보고]] 원문은 수신 기록으로 보존했다. 작성자 보고의 Vitest 98/HTTP smoke 118/2-PC script 63개를 Codex가 재실행하거나 실제 장비 합격으로 인정한 것이 아니다.

Studio의 고정 해시/크기/Evidence fallback 제거와 예약 가능량 미확인 차단 변경을 확인했다. 다만 다음 P1이 남아 실제 업무 웹 배포의 인수는 보류한다.

| 위치 | 남은 문제 | 다음 owner와 합격 기준 |
|---|---|---|
| src/saintvision/server.py:1583,1638 | Run을 메모리 RUNS에 running으로 넣고 임의 leaseId를 생성한다. 산출물 hash는 실제 출력 파일이 아닌 snapshotHash+runId 문자열에서 생성하고 Evidence ID도 조합한다. | Gemini: 이 fixture를 실측 결과로 보고하지 않기. Claude: 실제 kernel 결과/파일/Evidence 조회 adapter. SHA 일치한 실제 파일과 receipt로 검증 |
| apps/web/src/features/studio/DeveloperStudio.tsx:318 | Run 생성 응답의 id를 요구하고 파일/요청자/Node를 최초 POST로 전달한다. 실제 kernel은 runId/state/version을 반환하고 draft 생성 후 별도의 고정 입력 start/prepare·승인·start/enqueue가 필요하다. | Gemini: [[Codex 계정과 실행 커널 통합 계약]]/ADR-063으로 연결. 사용자가 편집한 파일이 실제 Node 실행 input과 일치하고 승인 전 실행 0 |
| apps/web/src/app/App.tsx:307,348 | CPU/메모리 등의 임의 fallback과 Math.random 사용률/새 heartbeat 시각 갱신이 남는다. 빈 목록 응답에서 기존 표본을 유지하는 경로도 있다. | Gemini: 실제 값·미확인·빈 목록·stale를 구분, 인위적인 heartbeat 생성 제거. offline/빈 결과에서 가짜 online 0 |
| 저자 보고 §3D/§4 | 현재 192.168.45.225는 lan-observe-v1이고 원격 workload 검증 전이다. 63개 스크립트 결과를 실제 두 PC/GPU 인수로 보고하거나 server.py의 Node-04 값을 16코어로 바꾸는 것은 실제 실행 가능 자원 확인을 대신하지 못한다. | Gemini: 시험 범위 정정. Codex: 설치 JSON·fresh mTLS·실제 Node profile/제공량·Lease 기반 원격 인수 |

실제 원격 설치본은 Node hard limit CPU 1 core/RAM 512 MiB/30초인 제한된 Python 검증 프로필이다. 관측 CPU 16코어가 확인되어도 16코어 실행 제공 승인이나 GPU 학습 인수를 뜻하지 않는다. 이 검토에서 운영 profile, DB, Node 또는 웹을 변경하지 않았다. owner 수정 후 실제 API/브라우저 인수와 재검토가 필요하다.
