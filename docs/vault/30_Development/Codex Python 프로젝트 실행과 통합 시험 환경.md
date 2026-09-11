---
doc_id: "CONTRACT-PYTHON-KERNEL-TEST-001"
title: "Codex Python 프로젝트 실행과 통합 시험 환경"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T10:05:00+09:00"
source_of_truth: "Git"
---

# Python 프로젝트와 실행 커널 연결

owner Codex / reviewer Claude 대기. 기존 ADR-044~047/061/062의 승인·입력 고정·격리·출력 확정 계약을 Python 시작 프로젝트로 검증한다. 공개 API/DB 상태 계약을 변경하지 않는다. 운영 사용자 연결과 UI 배포는 이 시험 환경에 포함되지 않는다.

## 실제 입력과 출력

`deploy/testing/Dockerfile.python-node`는 Python 3.12, Git, 고정 Go supervisor와 합성 probe를 포함한다. 실행 시 image content ID를 고정하고 `/usr/local/bin/python3`만 해당 프로필의 실행 파일로 허용한다. Python 라이브러리는 해당 이미지 배포판에 설치하며 다른 OS의 glibc나 `/lib` 구조를 덮어쓰지 않는다. 이미지에 Docker socket·DB 비밀번호·운영 인증서를 넣지 않는다.

일반 작업은 `python3 -B src/app.py`, CPU 학습은 `python3 -B src/train.py`다. 입력은 승인 전에 고정한 Workspace snapshot이며 실행 동안 UID 65532의 private tmpfs에 배치한다. CPU 500 millicores·RAM 64 MiB·최대 10초·PID 64·network none·read-only root·capability 없음이 이번 시험 예산이다. 일반 장시간 학습 또는 GPU 한도가 아니다.

정상 종료 후 실제 stdout/stderr hash와 Workspace 파일 snapshot을 검증한다. Run/Evidence와 `outputs/model.json`, `outputs/metrics.json`, `outputs/loss.csv`가 같은 execution attempt의 결과에 연결된다. nonzero exit는 Run failed로 반영하고 자원을 반환하며 성공 Evidence를 만들지 않는다. 결과 publication 재개는 저장된 동일 receipt를 사용하고 Node를 다시 실행하지 않는다. 학습 중간 optimizer 상태를 이어 학습하는 기능과는 구별한다.

## 재현 가능한 독립 시험

Windows에서 프로젝트 Python으로 실행한다. Linux에서도 같은 도구에 해당 Go 경로를 지정할 수 있다.

```powershell
& 'C:/Project/SaintVision-Invion/.venv/Scripts/python.exe' tools/check_kernel_docker.py --go 'C:/Project/SaintVision-Invion/.work/node-toolchain-1.27.1/go/bin/go.exe'
```

준비 시 외부 패키지는 이미지 빌드에만 사용한다. 실행 환경은 별도 내부 Docker 네트워크, 새 PostgreSQL 컨테이너와 무작위 테스트 DB/role, 고정 소스 사본, 제한 test runner로 구성된다. 실제 프로젝트 파일/기존 DB/Node 개인키를 bind하지 않는다. 테스트 runner만 Node 제어를 위해 로컬 Docker socket을 사용한다. 실제 workload 컨테이너에는 socket/host bind가 없다. DB 256 MiB, runner 512 MiB, workload 한도는 위와 같다. 동시에 사용자 대형 작업과 실행하지 않는 것이 현재 서버 자원에 적합하다.

`--prepare-only`로 빌드까지 수행하고 출력된 `prepared.json`을 `--prepared`로 재사용할 수 있다. 소스 hash가 달라지면 재빌드해야 한다. `--tests tests/integration/test_developer_workloads.py`로 Python 전용 시험을 선택할 수 있다. 테스트 runner/DB는 해당 호출의 고유 label을 확인한 뒤 종료한다. 로그는 ACL로 제한된 `.work/sv-kernel-...`에 보존하며 공개 결과에는 비밀번호·JWT·개인키 대신 사례 상태/이미지 SHA/소스 SHA만 쓴다. 실패와 skip이 있으면 합격으로 처리하지 않는다.

테스트 계정·2인 승인·CA는 fixture이며 운영 사용자로 등록되지 않는다. 단일 서버의 실제 여러 Node 프로세스 시험을 물리 PC 여러 대의 시험으로 보고하지 않는다. 결과와 남은 작업은 [[2026-09-11_KERNEL-LIVE_Codex_검증보고]]에 기록한다.

## 제품 연결 인계

- Codex: 이 이미지/입력/결과 경계를 실제 Node 프로필과 kernel에 연결하고 사전 예약·취소·복구 검증을 유지한다. 원격 PC 설치와 실제 운영 권한 조건을 확인한다.
- Claude: 실제 사용자·프로젝트·Workspace를 kernel identity/grant와 연결하고 업무 API/도구 Adapter를 구성한다. 개발 Studio의 SQLite `dev_` 기록을 제품 PostgreSQL Run으로 가장하지 않는다.
- Gemini: 서버가 반환한 실제 Run 상태·Node·예약 가능량·Evidence를 표시한다. API 실패 시 가짜 Run 생성, 관측 여유량을 예약 가능량으로 사용, 생성 응답을 실행 성공으로 해석하는 동작은 금지한다.
