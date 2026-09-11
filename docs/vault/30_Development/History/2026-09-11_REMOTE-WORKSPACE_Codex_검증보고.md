---
doc_id: "HIST-REMOTE-WORKSPACE-REPORT-20260911"
title: "REMOTE-WORKSPACE Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T11:35:00+09:00"
source_of_truth: "Git"
---

# 원격 Workspace 실행 프로필 배포와 검증 준비

owner Codex / reviewer Claude 대기, task REMOTE-WORKSPACE(S03-BE/S06-BE/S07-BE/S12-BE). [[2026-09-11_REMOTE-WORKSPACE_Codex_착수]]의 base `9c3a376`에서 작업했고 설치본 코드 `01236401367c4a430cf73da2b68984ca411e4883`, 서버 시험 도구/전송 개선 코드 `650ca0bde40043a3f32099f2a55971de88f5cb45`를 `agent/codex/dev-environment`에 commit/push했다.

**서버의 설치본 게시와 검증 도구 준비는 완료했고, 실제 원격 PC 설치·작업 실행은 아직 대기 중이다.** 192.168.45.225는 fresh mTLS 연결·lan-observe-v1 상태다. SSH/WinRM 22/5985/5986 접속 경로가 없어 해당 PC에서 [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]]를 한 번 실행해야 한다. 설치 명령과 마지막 JSON 요청을 사용자에게 전달했으며 개인키는 요청하지 않았다.

## 설치본과 보존 경계

서버 게시 URL은 `http://192.168.45.99:18081/workspace-worker.zip`, 크기 111,708,260 byte, SHA-256은 `b651729eec874c947c42ab4a24be493bbe2543bd271bc80f6a20d6fd62a4cbfe`다. 기존 worker.zip과 별개이며 개인키/DB credential/사용자 파일을 포함하지 않는다. 공개 manifest·두 이미지·공개 신뢰 자료·설치 코드만 허용 목록으로 검사하고, 실제 HTTP 다운로드 bytes의 해시가 일치함을 확인했다.

실행 이미지 코드는 이전 FIRST-RUN 통합 159개를 통과한 `b6301a9613097122a7574fa647b63d791fe13d2d`다. 검증된 inv-node 바이너리 및 Node/Go 계약 source hash를 대조한 뒤 agent 이미지를 만들었다. 서버에서의 agent ID는 `sha256:153bcae19a2aab26dbaab638ddaa3aa6622a628f99d32c76b3ee711f63473753`, Python/supervisor ID는 `sha256:f8af70427bcc35f1bebe18f4d121a505eb1a346028596c133fe6cd481a1c6abe`다. 원격 Docker image store가 ID를 바꾸더라도 layer/config를 모두 검증하고, 서버 시험에는 원격 설치 JSON의 실제 executionImage를 사용한다.

설치기는 기존 Node/tenant/epoch/주소/인증서·공개키·peer policy 및 owned volume을 확인한다. 미정리 workload가 있으면 중단한다. 기존 Node를 정지·백업하고 같은 volume/journal을 연결하며 credential은 기존 바이트와 root 0600 권한으로 검증한다. 새 컨테이너 시작 실패는 기록된 이전 ID로 복구하고, 설치 중단은 phase 기록과 명시적 rollback 경로로 처리한다. 성공 후 새 실행이 있을 수 있는 자동 downgrade는 거부한다.

새 profile은 `lan-workspace-v1`; Node hard limit CPU 1 core/RAM 512 MiB/30초, 시험 workload는 CPU 0.5 core/RAM 64 MiB/최대 20초다. 작업은 Python 고정 이미지, non-root, read-only root, no-new-privileges, cap-drop-all, PID 제한, network none, host bind/Docker socket 없음이다. 신뢰된 Node 관리 프로세스만 Docker socket에 접근한다. GPU/장시간·대규모 학습 인수가 아니다.

## 실제 검증 범위

| KST·코드 | 수행 | 결과 |
|---|---|---|
| 11:16경 구현 중 | `python -m pytest tests/core -q` | 270 passed, exit 0. 설치 보호 경계 포함 |
| 11:18:27 / clean 0123640 | `python tools/check_workspace_upgrade.py --prepared .work/sv-kernel-c652c90eaccf/prepared.json --agent-image saintvision-workspace-agent:b6301a961309` | 실제 로컬 Docker에서 upgrade/replay, 실패 후 이전 컨테이너·journal 복원, trust 불일치 무변경 3개 passed, exit 0 |
| 11:20경 | 실제 HTTP ZIP 다운로드, SHA/byte count 비교 | 일치, exit 0. bootstrap은 256 KiB 전송으로 전체 파일 메모리 적재 제거 |
| 11:27:11 / 작업 중 | 원격 시험 도구의 local self-test | 7개 통과. 아래 clean 코드 결과로 확정 |
| 11:30경 / clean 650ca0b | `python tools/check_remote_workspace.py --self-test --prepared .work/sv-kernel-c652c90eaccf/prepared.json --image sha256:f8af70427bcc35f1bebe18f4d121a505eb1a346028596c133fe6cd481a1c6abe --agent-image sha256:153bcae19a2aab26dbaab638ddaa3aa6622a628f99d32c76b3ee711f63473753` | 실제 Go/mTLS/Docker/PostgreSQL을 사용한 로컬 7개 통과, exit 0. 두 물리 PC 결과 아님 |
| 11:29경 | 신규 core/integration 동시 collect, core 설치·console·PKI 시험 | 13개 정상 수집/25개 passed, 각각 exit 0. 파일명 중복을 피하도록 core 모듈 이름 구분 |
| 11:31~11:33 | 원격 읽기 전용 preflight와 실제 관측 API | profile lan-observe-v1, 실행 미수행. 프로필 미설치 시 시험 DB 생성/서명 permit 발급 이전에 차단 |

모든 Python 명령은 `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`를 사용했다. 핵심 Go/Control Plane 실행 코드는 b6301a9와 hash 일치한 기존 검증 이미지다. 신규 설치/시험 도구는 위 코드 SHA와 구분해서 기록했다.

| 로컬 self-test 사례 | 실제 결과 |
|---|---|
| 최초 Python 실행 | draft→승인→attempt 1→succeeded, 실제 파일 checkpoint/Evidence |
| 최초 CPU 선형 모델 학습 | attempt 1 succeeded, outputs/model.json·metrics.json 및 SHA 검증 |
| 실행 전 취소 | attempt 0, Node의 미실행 tombstone 후 Lease 2개 반환 |
| 실행 중 취소 | attempt 1, cancelled/exit 143, mTLS receipt의 processStarted/stopped 및 Lease 반환 확인 |
| 작업 실패 | attempt 1, failed/exit 7, 성공 Evidence 없음 |
| 시간 초과 | attempt 1, failed/reason timeout, 물리 정지 후 반환 |
| 출력 복구 | 첫 서버 worker 프로세스가 실제 exit 17. 다른 프로세스가 같은 receipt로 출력/Evidence를 확정, attempt 1 유지 |

7개 모두 active Lease 0, 동일 command의 receipt를 관측 전용 endpoint에서 다시 대조했다. 물리 정지의 원격 확인 수단은 검증된 Node 코드가 생성하고 mTLS로 인증한 receipt이며 원격 Docker 관리 셸을 직접 조회했다고 주장하지 않는다. 자체 시험 Node·DB·runner는 정지했고 pilot DB와 기존 Orthanc만 계속 실행 중이다.

공개 Evidence는 `Evidence/remote-workspace-upgrade-0123640.json`, `Evidence/remote-workspace-self-test-650ca0b.json`, `Evidence/remote-workspace-package-0123640.json`, `Evidence/remote-workspace-readiness.json`이다. clean self-test JSON의 UTF-8/LF SHA-256은 `bd0b360cffebdf16364a942c2449e3462c934c21672e332ae0c980794516e6de`다. 개인키·DB connection 설정과 원문 진단 로그는 접근 제한된 .work에 보존하며 공개 Evidence에 넣지 않았다.

## 실제 원격 시험 재개

설치 결과의 `profile`, `nodeId`, 실제 `executionImage`를 확인한 후 Codex가 아래 명령을 실행한다. 마지막 이미지 값은 설치 JSON에서 확인한 값을 사용한다.

```powershell
& 'C:/Project/SaintVision-Invion/.venv/Scripts/python.exe' tools/check_remote_workspace.py --state 'C:/Project/SaintVision-Invion/.work/lan-pilot' --prepared .work/sv-kernel-c652c90eaccf/prepared.json --image '<worker executionImage>'
```

도구는 기존 pilot DB의 gate/claims/grants/활성 Lease를 읽어 현재 관측 전용 경계를 확인하며 수정하지 않는다. 원격 실행 profile을 fresh mTLS로 확인한 뒤 새로운 Docker DB/제한 runtime role와 합성 JWT 승인자를 만들고, 실제 kernel API와 signed permit으로 같은 7개 시험을 수행한다. 운영 DB·로그인·프로젝트 사용자 권한을 시험용 데이터로 대체하지 않는다. 실패/불확실 완료는 시험 DB와 출력·저널을 보존하고 자동 재실행하지 않는다. 다른 PC의 Node private key는 서버로 가져오지 않는다.

운영 사용자로 하는 일반 프로젝트 제출·화면 연결·독립 코드 검토는 Claude/Gemini의 별도 인계이며 이번 장비 시험과 구분한다. 새 main 병합 또는 독립 reviewer 승인을 수행했다고 기록하지 않는다.

## 전달·CI·동기화

650ca0b의 [Core 34554867615](https://github.com/egparadise/SaintVision-Invion/actions/runs/34554867615), [Backend 34554867585](https://github.com/egparadise/SaintVision-Invion/actions/runs/34554867585), [Docs 34554867634](https://github.com/egparadise/SaintVision-Invion/actions/runs/34554867634)는 모두 계정 결제/spending 제한으로 job 시작 전 차단됐다. 계정 변경·반복 재시도를 하지 않았다. 원문 조회는 `Evidence/remote-workspace-ci-650ca0b.json`이다.

외부 Obsidian 인덱스에서 기존 개발/검토 기록 다수의 삭제 및 Gemini 11:30 보고 추가를 발견했다. 전체 diff를 읽고 원문 인덱스/신규 보고를 `Evidence/remote-workspace-sync-proposals.json`에 보존했다. 기존 Git History는 유지하며 신규 보고는 수신·검토 대기로 기록한다. 통합 checkout 2e049ee의 새 UI 코드는 이번 원격 Node 작업에서 검토/배포하지 않았다. 보존 SHA가 같은 해당 인덱스의 sync 기준만 갱신했고 외부 저자 보고 본문은 유지한다. 오류와 해결은 [[2026-09-11_REMOTE-WORKSPACE_오류와해결]]이다.

2026-09-11 11:35 KST `python tools/check_docs.py`는 원본 hash 24개/문서 217개/48 task/12 outcome exit 0, `python tools/check_ontology.py`는 RDF/SHACL/질의 exit 0이었다. `python tools/sync_obsidian.py --check --state .work/dev-sync-state.json`은 338개 관리 파일/충돌 0, 같은 옵션의 `--apply`는 12개 내보내기/전체 hash 일치, 후속 `--check`는 대기 0/충돌 0으로 모두 exit 0이었다. 이 전달 기록 추가 후 문서 check와 sync check/apply/check를 다시 수행하고 문서만 commit/push한다. 마지막 문서 SHA·CI 상태는 Git/최종 사용자 응답을 따른다. 본문에 자기 SHA를 추가하는 재귀 커밋은 만들지 않는다. 원격 설치 확인·실제 두 PC 결과·독립 reviewer 및 CI 실행 전까지 전체 task는 done이 아니다.
