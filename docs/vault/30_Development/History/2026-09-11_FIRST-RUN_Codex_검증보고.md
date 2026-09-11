---
doc_id: "HIST-FIRST-RUN-REPORT-20260911"
title: "FIRST-RUN Codex 검증보고"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-11T11:00:00+09:00"
source_of_truth: "Git"
---

# FIRST-RUN 검증보고

Task FIRST-RUN, owner Codex / reviewer Claude 대기. [[2026-09-11_FIRST-RUN_Codex_착수]]와 [[Codex Workspace 첫 실행과 승인 입력 계약]]을 따른다. 구현 코드 `b6301a9613097122a7574fa647b63d791fe13d2d`, 브랜치 `agent/codex/dev-environment`에 commit/push했다. 변경 없는 확정 코드에서 실제 Linux/PostgreSQL/Go/Docker 통합 159개, Python core 260개와 Windows Go 전체 패키지 시험이 통과했다. 독립 검토·CI 실행·운영 인수는 미완료이므로 전체 개발 완료로 올리지 않는다.

실제 첫 Python/CPU 학습은 기존 실행 없이 draft에서 승인 후 attempt 1로 시작했다. 입력 준비 실패·승인 누락·등록 실패·중복 enqueue·실행 전/queue 후 취소·권한/자원/Node 변경·출력 저장 재개를 검사했다. 사용자/PKI는 독립 시험 fixture이며 현재 운영 계정 또는 다른 물리 PC로 실행한 결과가 아니다.

## 확정 코드 검증

| KST 시각 | 실제 명령·범위 | 결과 |
|---|---|---|
| 10:48:21 | 구현 중 최초 실행 25개 + 업무 연결 16개 | 41 passed, exit 0. 확정 SHA 결과는 아래 159개로 대체 |
| 10:53:06 | `python -m pytest tests/core -q`, services/node-agent에서 `go test -p 1 ./...` | 260 passed 및 Windows Go 전체 패키지 통과, 각각 exit 0 |
| 10:56:01 | `python tools/check_kernel_docker.py --go C:/Project/SaintVision-Invion/.work/node-toolchain-1.27.1/go/bin/go.exe` | dirty false, 159 passed/0 skipped, exit 0. Node·Workspace 재개·샤드·취소·containment·업무 연결·첫 실행 포함 |
| 10:57:02 | GitHub API로 위 SHA의 build 조회 | 3개 모두 job 시작 전 계정 결제/spending 제한으로 failure. 코드 실패로 해석하지 않으며 계정은 변경하지 않음 |

Python 실행 파일은 `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`다. 공개 원본 결과는 `Evidence/first-run-b6301a9.json`, 단위 검증은 `Evidence/first-run-b6301a9-local-checks.json`이다. 통합 결과 JSON은 UTF-8/LF로 저장했고 Git blob 기준 SHA-256은 `1aab2c62dbb0e85337548b5fa54e855f26786f1fb0795f66517d14a685ad7c82`다. 최초 실행 네 사례는 모두 attempt 1, activeLeases 0, containerAbsent true다. 성공 사례에는 실제 receipt·Evidence·파일별 SHA가 있고 exit 7 사례에는 성공 Evidence가 없다. CPU 선형 모델 학습은 400 epoch, evaluation MSE `1.6549685545817483e-12`로 기록됐으며 GPU 또는 대규모 학습 시험이 아니다.

새 Node 시험 이미지 digest는 `sha256:f8af70427bcc35f1bebe18f4d121a505eb1a346028596c133fe6cd481a1c6abe`다. 입력·승인·선택 Node·resource·profile/policy 버전을 고정하고 등록 실패를 원자 rollback했다. queue 이후 취소는 Node 미실행/정지 증거를 확인한 뒤 회수한다. 출력 확정 장애는 이미 실행한 attempt를 재실행하지 않고 기존 receipt로 완료했다. 시험 DB/runner는 모두 정지했으며 기존 pilot DB와 Orthanc 컨테이너를 유지했다.

CI 공개 조회 결과는 `Evidence/first-run-b6301a9-ci.json`이다. [Backend 34552381518](https://github.com/egparadise/SaintVision-Invion/actions/runs/34552381518), [Core 34552381546](https://github.com/egparadise/SaintVision-Invion/actions/runs/34552381546), [Docs 34552381544](https://github.com/egparadise/SaintVision-Invion/actions/runs/34552381544)는 실행 전 차단됐다. main 병합 및 독립 검토는 수행하지 않았다.

## 운영 상태와 다음 담당

`Evidence/first-run-operating-boundary.json`의 읽기 전용 실측에서 web 3000·로컬 Studio 18100·관측 API 18082는 HTTP 200이다. 실제 다른 PC `192.168.45.225`의 `nod_01M25VZZFBYQVFGYB11G7HC10J` 한 대가 fresh/online이며 `lan-observe-v1`이다. offered는 비어 있고 killSwitch true, userWorkloadSubmission false, webAuthenticationConfigured false, runs는 비어 있다. 이 사실을 다섯 노드 실행 완료로 바꾸지 않는다. 로컬 SQLite Studio 작업은 별도 개발 기능이며 이번 PostgreSQL kernel 경로가 이미 운영 화면에 연결됐다는 뜻이 아니다.

| 순서·owner | 다음 구현/인계 | 완료를 확인할 증거 |
|---|---|---|
| 1 Claude | FIRST-RUN 독립 검토, 실제 IdP 사용자와 프로젝트/Workspace/public-inv mapping 생성, 첫 실행 API를 업무 router에 연결. 실제 migration graph에서 0025와 기존 branch 변경 정합성 검토 | 실제 로그인 권한으로 draft→입력 고정→별도 승인→enqueue. 권한 회수/변조/오류 시 실행 차단과 실제 inv Run 조회 |
| 2 Gemini | 새 계약의 파일 bytes·명시적 Node 선택·승인·접수/실행/완료 상태를 UI에 연결. [[2026-09-11_GEMINI-STUDIO_수정본_Codex_재검토]]의 3개 P1과 배포 P2 수정 | 실제 브라우저에서 요청 실패를 성공으로 표시하지 않고 실제 산출물 bytes/hash·Evidence를 검증. 예약 가능량과 관측 여유를 구분 |
| 3 Codex | 새 initialized/startId 계약을 지원하는 원격 agent/supervisor 이미지·명시적 실행 profile 배포와 실제 PC 실행/취소/출력 복구 검증 | 동일 원격 Node identity/journal을 보존하고 실제 서명 receipt·attempt·파일 SHA·물리 정지·예약 회수를 기록 |
| 후속 Codex | 큰 저장소/장시간 작업, Workspace 편집·PTY/Git 현재 추적 코드 확인, GPU/Windows/BuildKit 격리, 다중 Node 학습·5대 부하/복구·Context/RO 평가 | 각 범위 실제 장비/데이터/버전의 재현 가능한 합격 Evidence |

기존 원격 `Enable-ExecutionTests.ps1` bundle은 이전 고정 probe 시험용이다. 이번 첫 Python 입력 계약/이미지를 포함한 배포물로 간주하지 않는다. 원격 장비 실행 권한·운영 identity를 합성 fixture로 대신 구성하지 않았다. 다른 Agent에게 메시지를 전송하거나 검토를 대신 완료하지 않았다.

오류 기록은 [[2026-09-11_FIRST-RUN_오류와해결]]이다. 외부 Obsidian 인덱스와 Gemini 정정 보고를 원문/SHA로 보존·검토한 뒤 해당 인덱스의 sync 기준만 갱신했다.

## 전달 기록

2026-09-11 10:59 KST에 `python tools/check_docs.py`는 원본 hash 24개/문서 213개/48 task/12 outcome 검사 exit 0, `python tools/check_ontology.py`는 RDF·SHACL·질의 검사 exit 0이었다. 문서 검사를 제품 build로 계산하지 않는다. `python tools/sync_obsidian.py --check --state .work/dev-sync-state.json`은 충돌 0, 같은 옵션의 `--apply`는 13개 내보내기/328개 hash 일치, 후속 `--check`는 대기 0/충돌 0으로 모두 exit 0이었다. 외부 저자의 원문 보고와 관리 대상 밖 파일은 유지했다. 이 전달 기록 추가 후 동일 check/apply/check를 다시 수행하고 문서만 commit/push한다. 문서 커밋의 실제 SHA와 최종 원격 상태는 Git/최종 사용자 응답을 따른다. 제품 코드 검증 기준은 계속 b6301a9다.
