---
doc_id: "HIST-VF-BROWSER-AUTH-001"
title: "승인 범위 정리와 실제 로그인 브라우저 통합"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-18T10:02:07+09:00"
source_of_truth: "Git"
---

# 승인 범위 정리와 실제 로그인 브라우저 통합

- 사용자: “니 영역에서 승인을 모두 OK 정리하고 멈추지 말고 이어서 진행해”. Codex 담당 구현·검증·통합·commit/push/인계 및 필요한 후속 작업 승인으로 기록한다. 반복 승인 질문 없이 진행한다. 실제 CI/타 Agent 독립검토/운영 인수는 수행 증거별 상태를 유지한다.
- owner Codex, reviewer Claude·Gemini 미수신. task VF-CX-01 통합후속, base54f3206, branch agent/codex/vf-browser-auth-integration, 시작2026-09-18T10:02:07+09:00. 공통판1.0.89/Codex1.0.57, agent-delivery1.1.0/core-reliability1.0.0/연속정책 적용.
- 발견: 기존 approval-browser branch의 Login/session 구현과 시험 진입파일이 후속 frontend 병합에 빠졌다. 현재App은 비로그인 dashboard, Login은 합성code와 클라이언트JWT판독을 사용하며 이전 실제PKCE시험은 실행경로에서 제외돼 있었다.
- 목표: 실제승인·로그인 여정 재현→서버검증session 복구→Desktop 유지→전용browser CI에 전체 해당시험 연결. 승인·실장비 등 확인되지 않은 결과를 완료로 대신 표시하지 않는다.

## 구현·검증

- 기준 실제로그인2시험 모두 로그인 화면 미표시로 실패. 89a405a의 검증된 Login/session/PKCE 보강 및 approval harness를 통합했다. App의 비로그인 진입을 Login으로 고정하되 Desktop/프로젝트 scope 유지.
- 첫통합6중4pass/2fail: kernel projects envelope 미처리와 완료된승인 반려버튼활성이 드러났다. 같은고정소스의 projectObservation/ApprovalDetail 보강도 통합했다. 알 수 없는 변경내역을 “파일 변경 없음”으로 표시하던 문구를 미포함으로 되돌렸다.
- 최종 actual Edge Chromium→Vite→configured Uvicorn→비소유자 PostgreSQL6/6 pass/0skip/exit0. IdP는 로컬synthetic PKCE 서버이고 응답 interception 없음. 잘못된audience거부/서버검증identity/2인정족수·중복거부/stale run/project grant/로그아웃/손상layout Desktop진입 확인. 독립review나 운영SSO가 아니다.
- `npm test`:273pass/0skip/exit0, `npm run build`:exit0. 이전271은 프로젝트조회추가2시험 전 수치다. 제거2시험은 신뢰하지 않는JWT로사용자판독하던구현 삭제에 따른것이며 auth-session17개로 대체했다.
- CI 전용browser lane에 Desktop2+Approval2+fullApp로그인2=6개를 명시하고6pass/0skip을 강제한다. backend/core에서는 동일3파일을 이 job으로 위임한다. CI 결과는 push 후 receipt로 남긴다.
- 다음ready VF-CX-05: 사용자승인에 따라 운영스냅샷 임시복원·0043업그레이드 리허설까지 이어서 실행했고 통과했다. 보관백업·독립클러스터복원은 별도후속Evidence로 남긴다. source DB변경 없음.

## 전달

- 코드325554cb2b7878bfa6eefd39621e41eaa34cde69 commit/push exit0, [Draft PR32](https://github.com/egparadise/SaintVision-Invion/pull/32). CI6check는billing/spending limit로시작전차단, ci.json에ID/원문보존.
- 연속수행: [[2026-09-18_VF-RECOVERY-REHEARSAL_Codex]]. 승인확인→실제로그인6여정→보관backup/독립restore까지수행. 독립review·운영SSO·실장비·CI는미완료. 사용자승인을다시요구하지않는다.

- 문서484/ontology/YAML/diff 검사통과. 전체sync check는외부편집충돌로미적용. base54f3206 확인 scoped17파일 hash일치/pending0/conflict0; 일반Codex공유본보존. 최종receipt와보고를같은state로재동기화한다.
