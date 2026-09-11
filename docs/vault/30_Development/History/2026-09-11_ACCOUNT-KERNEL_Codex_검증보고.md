---
doc_id: "HIST-ACCOUNT-KERNEL-REPORT-20260911"
title: "ACCOUNT-KERNEL Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T13:25:48+09:00"
source_of_truth: "Git"
---

# 계정·프로젝트와 실행 커널 통합 검증

[[2026-09-11_ACCOUNT-KERNEL_Codex_착수]]의 base 97e68af에서 Claude ad71868/ece6fea/001fbee/8678de0/5e0fed9를 작성자 이력을 보존해 가져왔다. Codex의 통합/권한 수정 코드는 `149b5658a390c0e0a2f54c30b404c3d6390b8919`, 브랜치는 `agent/codex/account-kernel-integration`이며 origin에 push했다. 운영 환경을 변경한 배포나 main 병합은 아니다.

## 변경 결과

- 업무 API의 /v1 경로와 실제 JWT 인증 오류를 수정하고, 같은 AccessTokens를 쓰는 업무·kernel HTTP 조합을 추가했다. inv_app과 inv_kernel의 접속 권한은 분리하고, 다른 DB/호스트나 관리자 DB 계정을 업무 연결로 사용하면 시작을 거부한다.
- 로그인만으로 사용자 상태·Node 제공량을 변경할 수 있던 경로에 별도 운영자 관리 권한을 추가했다. 프로젝트 소유권은 이 권한을 만들지 않는다. 다른 프로젝트 구성원 조회와 권한 회수, owner 동시 삭제·offer 동시 갱신을 보호했다.
- 두 공개 migration 이력은 유지하고 0026 merge→0027 guard로 통합했다. 기존 데이터/도구 선택 값 보존·head 반복 적용·runtime 권한을 확인한다.
- 새 public project에 kernel 권한이 없을 때 Run ledger의 FK 오류 대신 현재 권한 거부 403을 반환한다. 등록/승인 이전에 실행을 시작하지 않는다.
- Workspace 도구 준비 상태는 원격 Node의 실측 전까지 unknown이다. CP PC에 설치된 CLI를 원격 PC의 사용 가능 도구로 표시하지 않는다.

설계와 API 응답 키·배포 설정은 [[Codex 계정과 실행 커널 통합 계약]](ADR-064/065)을 따른다. 발견한 오류와 해결은 [[2026-09-11_ACCOUNT-KERNEL_오류와해결]]이다.

## 검증과 재현

모든 명령은 이 worktree에서 `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`로 실행했다. Docker 시험은 전용 내부 network·DB·제한 role·합성 JWT와 합성 workload를 생성하며 기존 운영 DB/개인키/사용자 파일을 사용하지 않는다.

| 명령/범위 | 결과 |
|---|---|
| `python -m pytest tests/core tests/test_migrations.py -q --tb=short` | clean 149b565에서 290 passed, exit 0 |
| `python tools/export_schemas.py --check` | 19개 계약 일치, exit 0 |
| `python tools/check_docs.py` / `python tools/check_ontology.py` | 최종 보고 포함 224개 문서/24개 원문/48 task/RDF/SHACL 통과, 각각 exit 0 |
| `python tools/check_kernel_docker.py --go C:/Project/SaintVision-Invion/.work/node-toolchain-1.27.1/go/bin/go.exe --prepare-only` | clean 149b565의 .work/sv-kernel-f64f5bd0dd9d/prepared.json 생성 |
| 계정·설정·로그인·API·pool·migration·계약·production 조합·첫 실행·업무 binding·containment | clean 149b565 / dirty=false에서 243 passed, 실패·오류·skip 0, exit 0 (13:22:32 KST) |

공개 Evidence는 [account-kernel-149b565.json](../Evidence/account-kernel-149b565.json), SHA-256 `399210eae08ee496a714a1e2504a4d4ac2c819e1e2dee5da9f4e267dde17cf96`다. 전용 runner/DB 종료도 확인됐다. [CI 관측](../Evidence/account-kernel-149b565-ci.json)과 [실제 Node 관측](../Evidence/account-kernel-live-observation.json)을 별도로 보존한다.

재현 명령은 다음과 같다. clean 준비본과 코드 SHA를 함께 사용한다.

```text
python tools/check_kernel_docker.py --prepared .work/sv-kernel-f64f5bd0dd9d/prepared.json --tests tests/test_account_integration.py tests/test_projects.py tests/test_settings.py tests/test_login.py tests/test_api.py tests/test_pools.py tests/test_migrations.py tests/test_contracts.py tests/integration/test_account_production.py tests/integration/test_workspace_start.py tests/integration/test_business_handoff.py tests/integration/test_containment.py
```

실제 JWT/DB 사례는 등록된 계정의 project 생성, 미등록·잘못된·중지된 계정의 401, 비멤버/미존재 project의 같은 403, owner/viewer의 tenant 관리 차단, 별도 grant의 범위와 즉시 회수, 두 owner의 동시 삭제 뒤 owner 1명 보존, 동시 제공 이력의 열린 구간 1개다. production 조합에서는 API로 생성한 project가 운영자 등록 이후 kernel draft를 생성하고 membership 회수 후 새 Run을 거부한다. 운영자 등록은 격리 시험 DB의 합성 setup이며 실제 운영 계정 provisioning이 아니다.

기존 첫 실행/업무 binding/containment 시험은 실제 Go/mTLS/Docker 및 PostgreSQL 경로를 통과한다. 이것은 로컬 Docker 증거이며 실제 192.168.45.225 실행이나 GPU/5대 인수로 확대하지 않는다.

## Agent별 다음 작업

| owner | 다음 작업 / 완료 조건 |
|---|---|
| Codex | 실제 worker 설치 JSON 후 원격 7개 실행·취소·복구 시험. 운영 IdP/provisioning과 Workspace 실입력·UI 연결의 계약 검토 |
| Claude | 149b565의 독립 재검토. 실제 IdP/계정·subject/project grant 등록 절차, Workspace provisioning, public offer↔kernel 제공량 연결, 실제 결과·로그·다운로드 API |
| Gemini | [[2026-09-11_GEMINI-ZERO-MOCK_Codex_후속검토]]의 P1 수정. 실제 /v1 응답 키와 start/prepare→승인→start/enqueue 연결, 화면 seed/랜덤 관측 제거, 실브라우저 인수 |

원격 Node는 아직 lan-observe-v1이며 운영 kill switch/일반 제출/웹 인증 설정은 변경하지 않았다. 기존 설치 URL와 hash는 [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]] 그대로다. 사용자에게 이미 요청한 설치 JSON을 기다리는 상태이며 설치/실장비 성공으로 표시하지 않는다.

## 전달 상태

코드 push는 성공했다. 동일 149b565의 [Docs 34561764241](https://github.com/egparadise/SaintVision-Invion/actions/runs/34561764241), [Backend 34561764244](https://github.com/egparadise/SaintVision-Invion/actions/runs/34561764244), [Core 34561764246](https://github.com/egparadise/SaintVision-Invion/actions/runs/34561764246)는 계정 결제/spending 제한으로 job 시작 전 차단됐다. 계정 설정과 반복 재실행은 변경하지 않았다.

Obsidian index에서 CR 중복/기존 History 블록 중복 및 Gemini 5899eb2 보고 추가를 발견했다. 전체 원문 바이트와 새 보고를 Evidence/account-kernel-sync-proposal.json에 보존하고 기존 기록은 한 번씩 유지한다. Gemini의 실제 2-PC/GPU 완료 주장은 당시 관측/시험 범위와 달라 인수하지 않는다. 새 보고는 author report 수신으로 구분한다. Codex 수정의 독립 Claude 검토와 CI가 남아 전체 task는 done이 아니다.

13:26 KST `git diff --check`와 `python tools/sync_obsidian.py --check --state .work/account-sync-state.json`은 exit 0, 349개 관리 파일/26개 반영 대기/충돌 0이었다. 검증 대상 제품 코드는 149b565이며 이후 변경은 보고·Evidence 문서뿐이다.

후속 `python tools/sync_obsidian.py --apply --state .work/account-sync-state.json`은 26개 파일 반영/349개 목적지 해시 일치, exit 0이었다. 이어 같은 `--check`에서 반영 대기 0/충돌 0, exit 0을 확인했다. 이 전달 기록 추가분도 동일 절차로 동기화한다. 다음 reviewer는 Claude이며 원격 인수 owner는 Codex다.
