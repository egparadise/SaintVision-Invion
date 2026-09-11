---
doc_id: "HIST-KERNEL-LIVE-REPORT-20260911"
title: "KERNEL-LIVE Codex 검증보고"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-11T10:13:52+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["development", "kernel", "evidence"]
---

# KERNEL-LIVE 검증보고

Task KERNEL-LIVE / S03·S06·S12 후속 / owner Codex / reviewer Claude 대기. [[2026-09-11_KERNEL-LIVE_Codex_착수]]의 base `32367cd7fe7847c654a2bec0513cfdc58cb72b6f`에서 Python/CPU 학습 프로젝트를 실제 제품 커널로 검증하는 독립 환경을 구현했다. 코드 `e5d9b0ba6c8b15d17dbcf686aaded978f5bec2b9`, 브랜치 `agent/codex/dev-environment`, commit/push exit 0.

## 확정 코드의 실제 실행 증거

2026-09-11 **10:12:29 KST**, clean SHA(`dirty: false`)의 통합 **118개 passed / 0 failed / 0 errors / 0 skipped**, 명령 exit 0. 별도 Linux 컨테이너의 PostgreSQL·Python 커널·Go mTLS Node·Docker workload를 사용했다. 사용자 pilot DB/PKI/Workspace와 분리했으며 시험 identity/승인자/CA는 fixture다. 물리 두 PC 또는 운영 사용자 인수 시험이 아니다.

```powershell
& 'C:/Project/SaintVision-Invion/.venv/Scripts/python.exe' tools/check_kernel_docker.py --go 'C:/Project/SaintVision-Invion/.work/node-toolchain-1.27.1/go/bin/go.exe'
```

공개 증거 `Evidence/kernel-live-e5d9b0b.json`에 사례별 결과·소스/바이너리/이미지 SHA·Run/command/receipt/Evidence ID·모델 파일 SHA·raw log SHA 및 시험 컨테이너 종료 확인을 저장했다. 수집 원본(CRLF) SHA-256 `c28e6688fea8063d91bb46f3762e454d35a3bde0e0bf62b1894517b1a4232705`, Git 정본(LF) SHA-256 `f23890fe5a51951b3b6619d581e8cb4659ecb906025c5a6cf34444853b056125`. Git의 줄바꿈 정규화에 따른 파일 바이트 차이이며 내부 실제 출력/모델 digest는 동일하다. Node image `sha256:cb79b7baa273afe70cbcf10ea8c5e33f6bfa3ba7ca5dcb39c976ac3f77052ad2`.

| 통합 영역 | 통과 사례 |
|---|---:|
| `test_containment` | 28 |
| `test_developer_workloads` | 4 |
| `test_node_delivery` | 18 |
| `test_node_runtime` | 22 |
| `test_output_ingestion` | 5 |
| `test_shard_recovery` | 21 |
| `test_workspace_api` | 9 |
| `test_workspace_resume` | 11 |

## 일반 개발·AI 실행과 복구

- JWT HTTP 준비 → 서로 다른 두 시험 승인자 → 원자 예약/queue → Go Node mTLS 전달 → 실제 Python 실행 → hash/파일 snapshot → PostgreSQL Run/Evidence 확정을 검증했다.
- 승인 뒤 Workspace 원본을 실패 코드로 바꿔도 고정한 승인 입력으로 정상 실행됐다. 같은 enqueue 재전달은 추가 attempt/컨테이너를 만들지 않았다.
- CPU 학습은 합성 데이터 51개로 400 epoch, 별도 평가 50개로 MSE `1.6549685545817483e-12`를 얻었다. 모델 weight `2.999997771347398`, bias `1.9999999999999991`, `model.json`·`metrics.json`·401행 `loss.csv`를 실제 checkpoint에서 복원했다. GPU/일반 AI 성능 지표가 아니다.
- 실행을 끝낸 Node를 정지한 뒤 새 출력 저장 worker 3개가 같은 receipt를 동시에 처리해도 완료 기록은 1개였다. 재학습 없이 결과를 복원했다. optimizer 중간 상태에서 학습을 이어가는 시험은 아니다.
- Python exit 7은 Run failed, 성공 Evidence 없음, 활성 Lease 0, 실행 컨테이너 제거로 끝났다. 정상 두 업무와 복구 업무도 활성 Lease 0·실행 컨테이너 없음이다.

| 전용 시험 | 실제 Run ID | 결과 |
|---|---|---|
| python | `run_01M2709FMXVXGH8Q8TCTN3WV7N` | succeeded, exit 0 |
| ai | `run_01M2709JNZ0MM4W8J93KNN5MD5` | succeeded, exit 0 |
| ai-output-recovery | `run_01M2709NF495WMJV8NMA42XKJD` | succeeded, exit 0 |
| python-failure | `run_01M2709RG3MB8DM1RY7CPNFH4K` | failed, exit 7 |

시험 runner와 별도 DB는 호출 소유 label을 확인해 종료했으며 `Running: false`, PID 0을 확인한 뒤 합격으로 기록했다. 원문 pytest/JUnit은 접근 제한된 `.work/sv-kernel-d72b453f0954/runs/aefeed119ae8`에 남겼다. 실제 사용자 DB와 Orthanc 컨테이너는 유지했다.

## 전달·동기화·검토

같은 코드 SHA의 [Core 34549360136](https://github.com/egparadise/SaintVision-Invion/actions/runs/34549360136), [Backend 34549360161](https://github.com/egparadise/SaintVision-Invion/actions/runs/34549360161), [Documentation 34549360169](https://github.com/egparadise/SaintVision-Invion/actions/runs/34549360169)는 기존 계정 결제/한도로 job 시작 전 차단됐다. 서버 실행 통과와 GitHub CI 미실행을 구분한다. 계정 설정은 변경하지 않았다.

Obsidian check는 외부 History 인덱스 편집 1건을 감지해 exit 1, 파일 쓰기 없이 중단했다. 새 Gemini 2-PC/GPU 보고와 인덱스 원문을 `Evidence/kernel-live-sync-proposals.json`에 보존했다. [[2026-09-11_GEMINI-TWO-PC_Codex_검토]]에 fixture 응답·digest 존재만 검사·CPU/RAM을 GPU 값으로 해석한 문제를 기록했다. 검토한 인덱스 SHA가 보존본과 같을 때만 해당 sync 기준을 갱신했다. 외부 보고의 실제 장비 완료 주장은 인수하지 않았다. 최종 문서/ontology/sync 결과는 아래 실행 기록을 따른다.

## 다음 담당과 완료 조건

| 담당 | 이어 할 작업 | 합격 증거 |
|---|---|---|
| Codex | 실제 운영 identity·프로젝트·Node profile 연결 시 승인/입력 고정/예약/결과 경계를 검토하고 원격 PC 설치 뒤 실행·중단·회수 시험 | 운영 계정 기반 실제 Run/Evidence, 원격 Node receipt·해시·물리 종료. GPU 및 분산 학습은 별도 장치 확인 후 검증 |
| Claude | 실제 사용자·프로젝트·Workspace·grant/IdP provisioning과 업무 API/Orca·Claude·Codex·Gemini 도구 Adapter 연결, 이번 코드 독립 검토 | 운영 인증/권한 매핑·서비스 시험·검토 결과. 임의 synthetic 운영 승인자로 우회하지 않음 |
| Gemini | 기존 Studio 4개 P1 및 이번 보고의 3개 P1/1개 P2 수정, 실제 API·Run/로그/출력/복구 화면 연결 | 오류 시 가짜 Run 없음, 서버 예약 가능량 사용, 실제 브라우저·운영 Evidence |

현재 로컬 Studio는 기존 SQLite 개발 실행이며 이번 시험은 PostgreSQL kernel Run이다. 두 경로의 운영 제출 연결은 미완료다. 10:11 KST 실제 원격 PC는 `lan-observe-v1`, offered 없음, kill switch 유지 상태다. [[2026-09-11_NODE-COMPAT_다른PC실행안내]] 설치 결과가 있어야 원격 시험을 진행할 수 있다. GPU·장시간 학습·중간 checkpoint 재학습·물리 2대/5대 시험, Claude 독립 검토, main 병합은 완료하지 않았다. baseline 48 task를 done으로 변경하지 않았다.

## 문서 전달 실행 기록

2026-09-11 10:14:50 KST: python tools/check_docs.py exit 0 (208 versioned documents, 원본 24개 hash, 48 tasks/12 outcomes 유지), python tools/check_ontology.py exit 0, git diff --check exit 0. sync_obsidian.py --check → --apply → --check 각각 exit 0: 318 managed files, 9개 출력 후 pending 0/conflicts 0. Obsidian 로컬 파일 hash 일치이며 OneDrive 클라우드 동기화 완료를 뜻하지 않는다. 이 결과 기록을 포함한 문서는 docs-only 후속 commit/push로 전달하고 실제 제품 시험을 다시 실행한 것으로 세지 않는다.

보고 commit `e9ad6da199605e1868c696104a3a74adae42fc21` push exit 0. 10:15 KST CI Core 34549930599 / Backend 34549930535 / Documentation 34549930539 모두 같은 계정 사유로 시작 전 차단. 웹 3000·Studio 18100·관측 API 18082 HTTP 200, 원격 Node fresh observe-only 유지, 실행 중 테스트 컨테이너 0을 확인했다. 이 파일의 원본/Git SHA 표기 정정은 시험 결과를 변경하지 않는다.
