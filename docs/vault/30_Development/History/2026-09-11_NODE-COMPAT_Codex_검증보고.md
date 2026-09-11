---
doc_id: "HIST-NODE-COMPAT-REPORT-20260911"
title: "NODE-COMPAT Codex 검증보고"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-11T09:32:53+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["development", "node", "evidence"]
---

# NODE-COMPAT 검증보고

Task NODE-COMPAT / owner Codex / reviewer Claude 대기. [[2026-09-11_NODE-COMPAT_Codex_착수]]의 base SHA에서 `agent/codex/dev-environment` 작업을 이어 진행했다. 원격 작업 연결의 선행 조건인 서버 서비스 복구와 Go Node의 실제 Docker 호환성을 보완했다. 전체 프로젝트 및 두 PC 업무 실행 완료 보고가 아니다.

## 구현과 실측

- Go Node: Linux Docker API 최소/최대 범위를 확인하고 1.41~1.45를 협상. 성공만 캐시하며 mutation 재전송은 하지 않는다. 기존 CPU/RAM/PID/UID/네트워크/파일 격리 readback 유지. bounded json-file 로그 적용. ADR-062 및 두 실행 계약 v1.1.0에 반영했다.
- 서버: 웹 `http://localhost:3000`, Studio `http://127.0.0.1:18100`, 관측 API 18082 복구. 현재 사용자 Startup의 `SaintVision Environment.lnk`가 `deploy/studio/Start-Environment.ps1`을 숨김 실행한다. Docker 시작과 겹치면 제한 횟수 재시도하며 새 업무를 제출하지 않는다. 실제 다음 로그인/재부팅 자체는 시험하지 않았다.
- 반복 시작: 09:25 KST 3개 listener PID 유지, 관측 Python launcher/child PID 두 개 유지. 추가 관측 프로세스가 생성되지 않았다. 기록 `.work/startup-proof.json`.
- 다른 PC `192.168.45.225`: 09:25 KST fresh mTLS online, Linux Node-visible CPU 16·RAM 8,247,738,368 bytes, 프로필 `lan-observe-v1`. 실제 Windows 전체 자원이나 GPU 제공량으로 해석하지 않는다. kill switch는 유지됐다.

## 로컬 검증

Windows `go test -p 1 ./...` exit 0. Linux runtime 전체 27개 상위 시험이 실제 Docker 시험을 포함하여 exit 0으로 통과했다. 실제 Docker 서버 20.10.22/API 1.41/cgroup v2, 고정 probe 이미지 `sha256:701236e95cff59aa352e75c60366dbe6056584e1faca9ad1dbb27fb2d91f3996` 사용.

| 실제 Node 시험 | 확인 결과 |
|---|---|
| isolation | exit 0, UID 65532/capability 없음/no-new-privileges/네트워크 없음/host socket 없음/read-only root/tmpfs/cgroup 한도 |
| output | stdout·stderr 실제 문자열, artifact 바이트 크기 및 SHA-256 일치 |
| fail | exit 7, 성공 output 없음, 물리 종료/삭제 확인 |
| sleep | timeout 후 nonzero exit, 성공 output 없음, 물리 종료/삭제 확인 |
| 위 4개 재전달 | durable duplicate, 동일 영수증, 추가 실행 없음 |

재현 명령: 프로젝트 Python으로 `tools/check_node_docker_compat.py --go <Go 실행 파일> --image <위 고정 이미지 ID>`. 테스트 runner에만 Docker socket을 연결하며 synthetic workload는 기존 격리를 적용한다. DB/제품 승인/Evidence는 이 시험에 사용하지 않는다. 보고용 Evidence의 코드 SHA와 dirty 여부로 작업 중 시험과 확정 SHA 시험을 구분한다.

## 이어 받을 작업

| owner | 다음 구현/검증 | 완료 증거 |
|---|---|---|
| Codex | 다른 PC 설치 완료 후 고정 probe permit 전달·실제 출력·전송 중단/복구 확인 | `lan-test-v1` 실제 관측, mTLS 영수증·SHA·중복 방지·물리 종료 |
| Codex | Studio 업무를 제품 kernel의 실제 사용자/프로젝트·승인·lease·queue·결과에 연결 | 실제 Run/Evidence 완료, 예약 회수·재시작 복구. 현 L2 2인 계약을 가상 사용자로 우회하지 않음 |
| Claude | 프로젝트/Workspace/사용자 서비스와 실제 kernel API·도구 Adapter 연결, Codex 독립 검토 | 실제 identity/project grant 매핑, 계약 검토 및 서비스/API 시험 |
| Gemini | 관측 온라인/시험 가능/업무 실행 가능을 분리 표시, 실제 프로젝트·Run·출력·복구 화면 연결 | 인증된 API와 실제 브라우저 여정 |

Orca는 worktree·개발 도구 조정 환경이며 별도 실행 권한자가 아니다. 원격 GPU·분산 학습·전체 샤드 업무는 아직 미완료다. 다른 PC에는 기존 공개 설치본 SHA `f9167bb15402dffc3ba00dc08e8effca7bf0cf4124229ba39f0931240cc3cdd1`의 `Enable-ExecutionTests.ps1` 실행을 요청했다. 이번 서버 호환성 코드가 그 기존 원격 설치본에 반영됐다고 주장하지 않는다.

## 전달 상태

코드 `08d8dde280afe014bfda732d174951468e375283` commit/push exit 0. 09:29 KST clean SHA의 실제 Linux runtime 27개/실제 Docker 4종 시험 exit 0, runner 종료 확인. 결과는 `Evidence/node-compat-08d8dde.json`에 원본 로그 SHA·binary SHA·컨테이너/이미지 ID와 함께 저장했다. 문서 201개/ontology/PowerShell 3개 구문 검사 exit 0 이후 인계 기록을 추가했다.

동일 SHA CI [Core 34546665501](https://github.com/egparadise/SaintVision-Invion/actions/runs/34546665501), [Backend 34546665413](https://github.com/egparadise/SaintVision-Invion/actions/runs/34546665413), [Docs 34546665643](https://github.com/egparadise/SaintVision-Invion/actions/runs/34546665643)는 모두 계정 결제/사용 한도 때문에 job 시작 전 차단됐다. 코드 시험 실패로 해석하지 않으며 CI 통과로 표시하지 않는다. 사용자 지시대로 계정 설정은 변경하지 않았다.

Obsidian check에서 기존 최신 계약/History가 과거 버전으로 바뀐 3문서와 추가 Gemini 보고를 발견했다. diff 검토 후 4개 원문 바이트·SHA를 `Evidence/node-compat-sync-proposals.json`에 보존했다. 최신 Git 정본을 유지하고 추가 주장에 대해서는 [[2026-09-11_GEMINI-STUDIO_Codex_통합검토]]에 4개 P1을 기록했다. 검토한 원문의 SHA가 변하지 않았을 때만 동기화 기준을 갱신해 재출력한다. 이후 동기화 명령/결과를 아래에 기록한다.

문서 확인 exit 0 (202개 versioned documents), sync `--check` → `--apply` → `--check` exit 0: 310 managed files, 11개 출력 후 pending 0/conflicts 0. 로컬 Obsidian 파일 hash 일치이며 OneDrive 원격 클라우드 동기화 완료 증거는 아니다. 다른 PC의 실행 명령은 [[2026-09-11_NODE-COMPAT_다른PC실행안내]]에 정리했다.

09:32:53 KST 안내문 추가 후 최종 문서 203개/ontology 검사와 sync check/apply/check가 각각 exit 0. 311 managed files, 추가 6개 출력 후 pending 0/conflicts 0. 본 결과 기록을 포함한 최종 보고 문서는 별도 docs commit으로 전달한다.

Codex 코드의 Claude 독립 검토·main 병합은 수행되지 않았다. 오류는 [[2026-09-11_NODE-COMPAT_오류와해결]]에 별도 보존한다.
