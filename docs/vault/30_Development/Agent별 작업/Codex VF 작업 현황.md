---
doc_id: "WORKBOARD-VF-CODEX-001"
title: "Codex VF 작업 현황"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-15T11:47:29+09:00"
source_of_truth: "Git"
---

# Codex VF 작업 현황

기준: ROADMAP-VIRTUAL-COMPUTER-001 1.0.0, ARCH-WEB-FABRIC-001 1.0.0, GOV-CONTINUOUS-001 1.0.0. 원격 기준 b9752a8e31573ee92b5bbb89724224923459f295. 작업 branch agent/codex/vf-cx-01, worktree codex-vf-cx. owner Codex, reviewer Claude (수신/착수/승인 미확인).

기존 진척 2775/4800 = 57.81%는 유지한다. 새 Codex VF의 운영 인수 분모는 5카드이며 현재 0/5 = 0%다. 구현·로컬 시험을 운영 인수로 계산하지 않는다. 다른 Agent 카드와 전체 VF의 가중 진행률은 미산정.

| 카드 | 현재 상태 | 다음 행동 |
|---|---|---|
| VF-CX-01 | canonical factory·fixture 격리 구현, 통합 검증 진행 | Linux 복원/definer 검증 → Evidence 고정/독립 검토 인계 |
| VF-CX-02 | ready (01 일부 보안 경계 로컬 검증) | 기존 DataLocation/Lease 위 manifest 계약과 검증 commit 구현 |
| VF-CX-03 | 02 의존 | 검증된 replica locality와 scheduler 연결 |
| VF-CX-04 | 03 의존 | 기존 dispatch/permit/recovery 경계 연결 |
| VF-CX-05 | W2~W4·실장비 의존 | 실제 5대 및 운영 자격증명 확보 후 signed Evidence 인수 |

## 작업한 것

- 이전 Codex 커널 89a405a 계보를 b9752a8에 통합 중. 0038까지 migration history와 Lease/epoch 경계를 보존.
- 배포 정본은 `saintvision.server:create_app --factory`. 두 역사적 mock 서버는 `tests/fixtures`로 이동. 원문 bytes 보존, 배포 image/package에서 제거.
- apps/web 및 frontend workflow는 원격 b9752a8 그대로 유지. 기존 mock의 임의 Bearer는 401이지만 자가 생성 code/PKCE는 관리자 토큰 발급 200, 인증 없는 프로젝트 조회 200을 재현.
- 구성된 정본은 이 발급 경로 404, 임의 bearer 401, 설정 없으면 기동 거부. Compose 내부 서비스는 localhost publish, 암호 필수.
- 감사 정책 revision을 실제 0038에 맞춤 (함수 hash/허용 grant 완화 없음), DB target 비교에서 connect_timeout의 오탐을 수정.

## 확인한 것

- Windows Python 3.14, Docker Linux Python 3.12/PG16. 운영 DB/Node를 사용하지 않은 임시 자원.
- 전체 최초 회귀: 1583 passed, 26 failed, 18 errors, 139 skipped (exit 1); 실패 원인을 보존하고 수정 후 선택 재검증 중. 통합 완료 주장이 아니다.
- 관리자 발급 우회/실제 factory 경로 추가 시험 2 passed; Compose 경계 2 passed; package+fixture 보존 13 passed (fixture 시험은 제품 인증 증거가 아님).
- Windows launcher/마이그레이션 경계 13 passed. 이후 실제 PG definer/account/upgrade 검증은 통과했고, 복원 시험의 Linux 전용/내부 network 요건은 별도 Linux runner에서 확인 중.
- 문서 검사·ontology·19 schema export·생성 계약 drift 검사 통과. 제품 인수와 별도.
- CI 같은 SHA: push 전 미실행. 독립 검토 미실행. 운영 자격증명/기존 DB 역할/운영 PITR/실장비는 미확인.

## 이어서

Codex: VF-CX-01의 Linux 복원 결과를 확인하고 commit/push/같은 SHA CI/Evidence/Obsidian 인계 기록 후 VF-CX-02로 진행한다. Claude: 실제 요청 인계본의 definer·migration·canonical 경계를 독립 검토한다. Gemini: fixture auth 및 실제 route gap을 정본 계약에 맞추고 실제 API E2E를 수행한다. 어느 Agent도 상대방의 검토를 완료 처리하지 않는다.
