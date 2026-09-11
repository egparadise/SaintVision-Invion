---
doc_id: "HIST-WORKSPACE-INTEGRATION-VERIFY-20260911"
title: "Workspace 최신 커널 통합 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T16:58:55+09:00"
source_of_truth: "Git"
---

# Workspace 최신 커널 통합 검증

WORKSPACE-INTEGRATION / S06-BE·DB·ST 부분. owner Codex, 독립 reviewer Claude pending. [[2026-09-11_WORKSPACE-INTEGRATION_Codex_착수]]와 [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.1.0 / ADR-071에 따른다.

## 전달 코드와 결과

코드 `c5f215475b203b1e6731927117093921cda9c183`는 PR19 base `33e6510d4410639ac7bf1252f1a0c232b1659cbe`와 최신 resource-offer/tenant kernel `609c807d8cd61cbfab2f9a705baf9660459c3744`를 이력 보존 merge했다. branch는 `agent/codex/workspace-bridge`, 기존 [PR #19](https://github.com/egparadise/SaintVision-Invion/pull/19)에 push했다. 새 draft는 만들지 않았다. 검토 base를 resource-offer-integrity로 정리하여 #21 → #22 → #19 의존 순서로 검토한다. main 병합은 이 작업의 완료 사실이 아니다.

- 0033은 공개 0024_workspace_bridge와 0032를 합친다. 기존 parent/함수 이력을 다시 쓰지 않았으며 tenant 경계 보강과 kernel ResultView를 유지했다.
- 편집 revision과 freeze 입력이 일치하는지 확인한 실제 Node 실행이 성공하고 수정 결과·Git commit·출력 checkpoint·Evidence·자원 반환을 검증했다.
- PTY의 누락된 Node 검증기 5개를 등록하고 Docker exec/start API 버전 협상을 적용했다. frozen first-start/resume + 명시적 profile만 허용한다. 첫 실행에서 상충하는 targetNodeId를 거부한다.
- 실제 Python PTY 입력·동일 요청 재전송 1회 처리·재접속 시 실행 횟수 보존·old disconnect CAS·ticket 재사용/Origin/요청자/Workspace/만료/중복 연결 거부·현재 grant 회수·취소 후 차단·실제 WebSocket 연결을 시험했다.
- Git proposal replay는 현재 public membership을 다시 검사한다. public membership만 삭제하고 kernel grant가 남은 상태에서도 403이다. Git 원격 provider는 이 시험에서 메모리 대역이며 실제 GitHub publication 성공을 뜻하지 않는다.
- Core/Backend/Frontend/Documentation의 이 branch 시험 생략 조건을 모두 제거했다.

## 고정 SHA 검증

| 명령/범위 | 결과와 증거 |
|---|---|
| `python -m pytest tests/core tests/test_migrations.py -q` | 301 passed, exit 0; JUnit 확인 |
| `python tools/check_kernel_docker.py --prepared … --tests …` (계정·tenant·자원·readiness·첫 실행·containment) | 307 passed, 0 skipped, exit 0 |
| 같은 도구 (실제 Node·전송·출력 복구·Workspace·샤드·PTY) | 95 passed, 0 skipped, exit 0 |
| `tools/check_migration_upgrade.py` (위 계정 시험에서 실제 PostgreSQL 실행) | 공개 prior 20개 → 0033, 재적용·제한 runtime grant 검증, exit 0 |
| Linux Go unit binary 및 `tools/check_node_docker_compat.py` | 고유 최상위 시험 43개 통과. 실제 Docker API 1.41의 isolation/output/fail/sleep 하위 시나리오 4개와 durable replay/물리 정리 확인. race detector는 로컬 미실행 |
| `python -m build services/control-plane` | sdist/wheel 성공, exit 0 |
| `npx --package typescript@5.9.3 tsc --noEmit --strict packages/contracts-ts/src/index.ts` / Go 계약 compile | exit 0; Go 계약 package에는 자체 시험 없음 |
| 계약 재생성 / `git diff --exit-code` | drift 없음, exit 0 |
| `python tools/check_docs.py` / `python tools/check_ontology.py` | exit 0; 보고서 추가 후 재검사 |

최종 격리 통합 합계 **402개**, 별도 기본 검사 301개다. 중간 dirty 46/3/57개는 디버깅 증거이며 합산하지 않는다. Go는 중복 실행한 runtime 27개를 다시 세지 않는다. 소스별 SHA-256·바이너리·이미지 ID·case별 상태·시험 컨테이너 정리 결과는 `Evidence/workspace-integration-c5f2154-business.json`, `-runtime.json`, `-checks.json`에 있다. 임시 DB credentials/pytest 원문은 공개 보고에 넣지 않았다.

CI push/PR 8개 workflow는 job 시작 전 결제/사용 한도 제한으로 failure였다. Core IDs 34576495336, 34576489061. `Evidence/workspace-integration-c5f2154-ci.json`에 annotation을 보존했다. 로컬 통과를 CI 완료·독립 승인으로 인정하지 않는다.

## 운영 관측과 실제 남은 일

2026-09-11 16:55 KST 실제 mTLS 관측: remote `192.168.45.225` online/fresh, profile `lan-observe-v1`, agent 0.1.0. 운영 killSwitch=true, userWorkloadSubmission=false, webAuthenticationConfigured=false. 관측 1대이며 실제 원격 업무 또는 5대가 연결된 것으로 표시하지 않는다. `Evidence/workspace-integration-live.json` 참고.

| 담당 | 이어서 할 일 / 완료 조건 |
|---|---|
| Codex | 원격 PC에 기존 [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]] 설치 결과 수신 → identity/journal 보존 확인 → 실제 원격 7개 실행·취소·실패·timeout·출력 복구. 이후 대체 Node·장비 PTY/Workspace 이동·GPU/Windows/BuildKit·5대 부하/장애/복구 및 Context/RO 안전성 인수 |
| Claude | 이 merge/0033/RLS·Terminal ticket/frame·Git 현재 grant·실패 복구의 독립 검토. 실제 IdP/verified person·project/Workspace/Node provisioning와 설정. 백업 복원 보고의 fencing/RPO/내용 대조 지적 수정 |
| Gemini | editor CAS/동결·현재 Node 선택·ticket 만료/complete-line PTY·Git diff/전체 pull 교체/2인승인/dispatched 화면을 실제 API와 연결. ResultView 실제 bytes 다운로드, readiness 7항목/권한 상태, 관측 unknown 처리 후 브라우저 인수 |
| Orca | #21 → #22 → #19 의존/owner/reviewer/CI 상태 추적. 앞선 독립 검토·CI 제한을 해소한 후 main 통합 증거 기록 |

실제 GitHub 대상 repository/branch/operator credential과 독립 2인 승인 후 CAS·응답 유실·reconcile을 검증해야 한다. 운영 키/DB/gate는 변경하지 않았다. Workspace 내용 32 KiB/manifest 64 KiB, 최대 30초 Linux PTY, 줄바꿈 없는 prompt 비표시 제한은 남는다. 전체 최초 설계나 AC-06을 done으로 표시하지 않는다.

## Obsidian 전달

2026-09-11 17:00 KST report SHA `8283cfddf55fae051d37e905251a0921e1663814`에서 `python tools/sync_obsidian.py --check → --apply → --check`를 실행했다. exit 0, 13개 export, 관리 파일 396개 전체 SHA-256 일치, pending 0/conflict 0을 확인했다. 이 후속 전달 기록도 commit/push 후 다시 동기화한다. OneDrive 클라우드 업로드 완료는 검증하지 않았다.

같은 report SHA의 CI도 Core 34577022052/34577016166 등에서 job 시작 전 결제/한도 제한을 확인했다. 코드 SHA와 report SHA의 제품 소스 차이는 없다. PR19는 resource-offer-integrity를 base로 하는 draft이며 독립 승인·main 병합은 남는다.

