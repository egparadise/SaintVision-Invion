---
doc_id: "HIST-VF-DESKTOP-LAYOUT-001"
title: "잔여 진척 확인과 Desktop 배치 복원 보강"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-18T09:55:16+09:00"
source_of_truth: "Git"
---

# 잔여 진척 확인과 Desktop 배치 복원 보강

- owner Codex/reviewer Gemini·Claude 미수신, task VF-CX-01 통합후속, branch agent/codex/vf-desktop-layout, base b947b1c. 공통판1.0.87/Codex1.0.55, agent-delivery1.1.0/core-reliability1.0.0 적용.
- Git fetch exit0: Claude b30a723/Gemini5ef0f1a 이후 새 commit 없음. 공유 Obsidian 공통판1.0.87과 Git 일치.
- 승인된 기존 산식2775/4800=57.8125%, 잔여2025/4800=42.1875%(표시42.19%). 전체 신규 점수 재승인 없음. VF 운영0/5와 별도. 공식48카드 done 여부는 registry에서 재집계한다.
- 이번 작업: 저장된 Desktop 창 배열을 검증 없이 복원하는 경계의 crash 재현, 정본 앱 allowlist·유한 위치/크기·누락창 복구, 로컬 시험/CI/범위제한 sync.

## 결과와 범위

- 2026-09-12 점수 정본 development-progress-storage-check-20260912.json의48개 row를 재합산:2775/4800, 잔여2025/4800=42.1875%. 9월18일 새 평가 점수가 아니라 최신 채택 기준의 재확인이다. registry planned33/review12/in_progress3/done0. VF Codex 운영 인수0/5. 시간·비용 잔여율로 해석하지 않는다.
- DesktopShell이 [null] 또는 위치·크기 없는 창을 복원할 때 SSR crash2건 재현(exit1). restoreDesktopLayout은 크기 제한JSON, 정본ID/app일치, boolean/유한좌표·양수크기, 중복거부를 검사한다. 정본title/icon/params를 유지하고 뷰포트 밖 좌표·크기를 제한한다. 저장소 접근 실패는 기존fallback 유지.
- Windows `npm test` 최종256pass(신규14)/0skip, exit0. `npm run build` exit0. 실제 browser/HTTP 회귀는 기반7c55fea의2여정이며 이번 변경의 독립 browser 인수로 확대하지 않는다.
- 다음 첫 행동: Gemini는 손상된 localStorage 후 실제 Desktop 진입/작은화면 접근성 독립검토, Claude는 복원 계약 검토. Codex는 finding을 받아 수정. CI·운영 SSO/PITR·5대 인수는 별도이며 진행률 승격 없음.

## 전달과 현재 차단

- code546ec50e0c1a3d2e378f5d4e8f5b0f5e0c08c0b7 push exit0, [Draft PR31](https://github.com/egparadise/SaintVision-Invion/pull/31), basePR30. docs482/ontology검사 exit0.
- 9월18일 동일SHA CI 재확인: core35293302188/Desktop35293302174/docs35293302129/backend35293302076/frontend35293302089의6check 모두 billing/spending limit로 실행 전 차단. 기존 차단을 날짜만 갱신한 추정이 아니라 새 receipt를 저장했다.
- 구현·로컬시험 완료, CI/독립 browser 검토/운영 인수 미완료. 다음 Gemini 복원/접근성 검토, Claude 계약검토, 운영owner billing·SSO/PITR·5대. 진행률 새 승격 없음.

- 전체sync check는 외부편집 충돌 exit1/쓰기없음. baseb947b1c 확인 후 scoped6파일 hash일치/pending0/conflict0, 일반Codex공유본 보존. receipt·최종보고를 동일state로 재동기화한다.
