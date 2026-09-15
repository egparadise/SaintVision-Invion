---
doc_id: "WORKBOARD-VF-CODEX-001"
title: "Codex VF 작업 현황"
version: "1.0.7"
status: "in_progress"
author: "Codex"
updated: "2026-09-15T13:10:39+09:00"
source_of_truth: "Git"
---

# Codex VF 작업 현황

기준 ROADMAP-VIRTUAL-COMPUTER-001/ARCH-WEB-FABRIC-001/GOV-CONTINUOUS-001 1.0.0, integration 원격b9752a8. owner Codex, reviewer Claude(실제 수신·검토 미확인). 현재 branch agent/codex/vf-cx-05, base42b804e. 개별 source SHA/명령/exit code는 연결된 History/Evidence가 정본이다.

| 카드 | 구현·로컬 검증 | CI/검토/운영 | 다음 행동 |
|---|---|---|---|
| VF-CX-01 | canonical factory·fixture 격리·인증 경계, code290aba5, Windows1613/139 skipped·Linux41 | CI billing, 독립 검토/운영 미완 | 실제 route/UI 정합, 운영 SSO/PITR |
| VF-CX-02 | ModelManifest·bytes hash·기존 Lease/FK commit, coded6d9d87, Windows66/Linux49 | CI billing, 독립 검토/운영 미완 | Claude Catalog/API 연결·독립 검토 |
| VF-CX-03 | 측정 locality·원자 예약·model input, codebc8797c, 상세 회귀 증거 인계 | CI billing, 독립 검토/운영 미완 | 04 입력 freeze/실행과 연결됨 |
| VF-CX-04 | CPU 모델 입력 freeze·기존 permit·최대3세대 대체 실행, Windows1716/139 skipped·Linux140/140 | CI billing/독립 검토/운영 미완 | Claude 독립 검토·runtime 서비스 연결 |
| VF-CX-05 | read-only preflight15/15, TCP3회 실패, DB0023→0042 미적용25개 | blocked: 실제5대/W2~W4/backup·운영 변경 | 운영 owner 연결 복구/백업, Claude 검토 후 재점검 |

## 작업한 것

[[2026-09-15_VF-CX-01_Codex_인계]], [[2026-09-15_VF-CX-02_Codex_인계]], [[2026-09-15_VF-CX-03_Codex_검증보고]], [[2026-09-15_VF-CX-04_Codex_검증보고]]. 정본 API/실행 권한을 복제하지 않고 기존 Catalog/Lease/승인/Node/Result를 연결했다. apps/web와 다른 Agent 작업판을 수정하지 않았다.

## 확인한 것

140개 최종 Linux 시험에서 모델 입력 실행·출력 복구·취소·실제 만료·Node 이탈 거부·두 Go Node 대체 실행을 확인했다. Evidence는 한 Docker host의 격리 시험이며 실제 두 PC/5대 인수가 아니다. [[모델 실행 입력과 대체 Node 복구 계약]]의32KiB CPU 범위를 넘어선 GPU/collective/대용량 provider는 미지원으로 표시한다. 실패와 수정은 [[2026-09-15_VF_오류와_해결]].

## 이어서

Codex: [[2026-09-15_VF-CX-05_Codex_선행조건_점검]]에 실제 선행조건·변경 계획·재개 순서를 인계했다. 후속 운영 변경 승인이 확인되면 preflight부터 재검증한다. Claude: kernel migration/동시성/보안 독립 검토와 서비스 API. Gemini: canonical route/모델 상태/UI 연결 및 browser 검증. 운영 owner: CI billing, SSO/credential/PITR,5대 장비 및 검증된 runtime profile.

기존2775/4800=57.81% 유지. 새 VF 운영 인수0/5(0%). 구현/로컬/CI/독립 검토/운영 인수를 별도로 관리한다. 다른 Agent의 수신·착수·승인을 대신 기록하지 않는다.

최종 로컬 회귀1716 passed/139 skipped/0 failed; Linux140/140은 한 Docker host이다. GPU/대용량/routing/data/tensor-pipeline 및 W2~W4 전체 인수는 여전히 별도 미완 범위다. 05 준비 점검을 제품 인수 성공으로 바꾸지 않았다.
