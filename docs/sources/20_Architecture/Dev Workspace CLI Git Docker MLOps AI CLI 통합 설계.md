---
title: Dev Workspace CLI Git Docker MLOps AI CLI 통합 설계
aliases:
  - Dev Workspace 통합 설계
  - INV Dev Workspace
tags:
  - saintvision
  - inv
  - workspace
  - cli
  - git
  - docker
  - mlops
status: baseline
updated: 2026-09-09
---

# Dev Workspace CLI Git Docker MLOps AI CLI 통합 설계

## 1. 목표

INV Dev Workspace는 사용자가 Saint Vision 안에서 요구사항 정리, 코드 작성, AI 코딩 도구 사용, Build, Test, Container 실행, GPU 학습과 평가, Model 등록과 배포까지 수행하게 하는 개발 환경이다.

Workspace는 특정 물리 PC의 원격 Desktop이 아니다. Project의 지속적인 파일과 Toolchain을 제공하는 논리 환경이며, 무거운 실행은 INV Scheduler가 적합한 Node로 보낸다.

## 2. Workspace와 Node

~~~mermaid
flowchart LR
    USER[Browser User] --> WS[Logical Workspace]
    WS --> EDIT[Edit on Workspace Service]
    WS --> TERM[Terminal Session]
    WS --> JOB[Workload API]
    JOB --> SCHED[INV Scheduler]
    SCHED --> N2[Node 2 Build]
    SCHED --> N3[Node 3 GPU Test]
    SCHED --> N4[Node 4 Training]
    SCHED --> N5[Node 5 Dataset]
~~~

사용자가 Terminal에서 python train.py를 실행해도 Command Classifier가 이를 GPU Workload로 변환할 수 있다. 사용자가 명시적으로 local 실행을 요청한 경우에만 Workspace Runtime에서 실행한다.

## 3. Workspace 구성요소

| 구성요소 | 기능 |
|---|---|
| Web IDE | 파일 탐색, 편집, Search, Diff와 Extension |
| Terminal Gateway | PTY Session, WebSocket, 입력과 출력 Audit |
| Shell Profiles | Bash, Zsh, PowerShell 7, Windows PowerShell과 제한된 CMD |
| File Service | Workspace Volume, inv URI Mount와 Artifact |
| Git Service | Credential, Clone, Branch, Commit, Pull, Push와 Review |
| Runtime Client | Docker, BuildKit, Ray, PyTorch와 INV Workload 제출 |
| AI CLI Hub | Claude Code, Codex, Orca, Antigravity와 기타 Adapter |
| Notebook | Jupyter와 GPU Kernel 연결 |
| MLOps Client | Experiment, Dataset, Model, Registry와 Deployment |
| Policy Client | 명령 위험 분류, 승인, Budget와 Secret 요청 |

## 4. Workspace 유형

### Container Workspace

Linux 기반 일반 개발의 기본값이다. 빠르게 생성하고 Image로 재현할 수 있으며 Project마다 Dependency를 격리한다.

### Windows Workspace

PowerShell, Windows SDK, .NET Framework 또는 Windows 전용 Tool이 필요한 Project에 사용한다. 별도 Windows Node Pool과 강화된 Policy가 필요하다.

### Ephemeral Job Workspace

CI, Build, Test와 Batch 작업에 사용한다. Run 종료 후 변경 가능한 Layer를 폐기하고 Artifact만 보존한다.

### Persistent Research Workspace

Notebook와 장기 실험에 사용한다. 자동 Suspend, Storage Quota와 Checkpoint가 필요하다.

## 5. Template

| Template | 기본 Tool |
|---|---|
| General Development | Git, Bash, PowerShell, Python, Node.js |
| Python AI | Python, uv 또는 pip, Jupyter, NumPy, MLflow Client |
| PyTorch GPU | Python, PyTorch, CUDA Runtime, nvidia tools |
| Medical Vision AI | PyTorch, MONAI, OpenCV, pydicom, SimpleITK, DCMTK |
| LLM Development | Transformers, vLLM Client, Tokenizer, Evaluation Tool |
| Full Stack | Node.js, Python, Database Client, Docker CLI |
| Go | Go Toolchain, Linter, Debugger |
| Rust | Rust Toolchain, Cargo, Clippy |
| Custom | 사용자가 관리하는 Dockerfile과 Lockfile |

Template는 Base Image Tag가 아니라 Digest, Tool Version, Policy Profile과 SBOM을 가진 Versioned Resource다.

## 6. Terminal 설계

### Workspace Terminal

- 일반 사용자의 기본 Terminal
- Workspace Root와 허용된 inv Mount만 접근
- Shell마다 Resource Limit, Timeout과 Network Policy 적용
- Session Resume는 승인된 수명 안에서만 허용
- Shell 입력 전체를 비밀 원문으로 보관하지 않도록 Redaction 적용

### Node Terminal

- 운영 관리자 전용
- 특정 Node의 진단과 복구 목적
- 명시적 사유, 짧은 TTL, 승인이 있는 Session
- Command, 출력, 파일 전송과 권한 상승을 감사
- 기본 Read-only Profile, 변경 명령은 별도 승인

### Terminal 생성 흐름

1. 사용자와 Project 권한 확인
2. Workspace 상태와 Shell Profile 검증
3. Session Token과 PTY 생성
4. Vault에서 필요한 단기 Credential만 주입
5. WebSocket 연결과 Audit 시작
6. Idle Timeout 또는 사용자 종료 시 Process 정리

## 7. INV CLI

기본 명령은 inv다.

| 명령 | 목적 |
|---|---|
| inv status | Cluster와 Resource Offer 확인 |
| inv nodes | Node Capability와 상태 확인 |
| inv project open NAME | Project Workspace 열기 |
| inv workspace create TEMPLATE | Workspace 생성 |
| inv run TARGET | Workload 제출 |
| inv up | inv.yaml에 따라 Build와 실행 |
| inv explain RUN | Placement와 Policy 이유 |
| inv logs RUN | Run Log Stream |
| inv artifacts RUN | Run Artifact 조회 |
| inv cancel RUN | Run 취소 |
| inv shell NODE | 승인된 Node Terminal |
| inv powershell NODE | 승인된 Node PowerShell |
| inv mlflow RUN | 연결된 Experiment 열기 |

### 예제

~~~powershell
inv status
inv run .\train.py --gpu 2 --mode distributed
inv explain run_01JXYZ
inv artifacts run_01JXYZ
~~~

CLI는 Portal과 같은 API, Identity, Policy와 Audit를 사용한다. 로컬 관리자 권한을 우회 경로로 사용하지 않는다.

## 8. AI CLI Hub

### Adapter 구조

~~~mermaid
flowchart TB
    WS[Workspace] --> HUB[AI CLI Hub]
    HUB --> CONTRACT[Provider Adapter Contract]
    CONTRACT --> C1[Claude Code Adapter]
    CONTRACT --> C2[Codex Adapter]
    CONTRACT --> C3[Orca Adapter]
    CONTRACT --> C4[Antigravity Adapter]
    CONTRACT --> C5[Open Source Adapter]
    CONTRACT --> C6[Custom Agent Adapter]
    HUB --> VAULT[Secret Vault]
    HUB --> POLICY[Tool and Network Policy]
    HUB --> TRACE[Run and Evidence]
~~~

### 공통 Adapter 계약

- probe: 설치 여부, Version과 Capability 확인
- install: 승인된 Version을 Workspace에 설치
- authenticate: 사용자별 CredentialRef 연결
- run: Working Directory, 입력, Model Profile과 Budget으로 실행
- cancel: Process와 Provider 요청 취소
- collect: 출력, 변경 파일, Usage, 비용과 오류 Metadata 수집
- redact: Secret과 민감 데이터 제거
- attest: CLI Version, Config와 실행 Image Digest 기록

### 사용 원칙

- 사용자는 각 Provider 계정과 License를 소유한다.
- Provider Credential은 Workspace Image나 Repository에 넣지 않는다.
- CLI가 생성한 Shell 명령은 동일한 L0-L3 Policy를 통과한다.
- Provider 장애 시 다른 CLI로 자동 전환하려면 사용자의 사전 정책이 있어야 한다.
- Prompt, Source와 Dataset의 외부 전송 허용 범위를 Project별로 설정한다.

## 9. Git 통합

### 기능

- GitHub, GitLab과 일반 SSH 또는 HTTPS Remote
- Repository Clone, Fetch, Pull과 Push
- Branch 생성, Diff, Commit, Tag와 Merge 요청 보조
- Commit SHA와 Run, Build, Artifact, Model Version 연결
- Signed Commit과 Protected Branch 선택 지원

### AI Agent 규칙

- 읽기와 Diff는 L0
- Workspace 파일 수정과 Local Commit은 L1
- Remote Push와 Branch 생성은 Project Policy에 따라 L1 또는 L2
- Protected Branch Merge, Tag와 Release는 L2
- Force Push와 History Rewrite는 기본 L3

Working Tree가 더러우면 Agent는 기존 변경의 소유자를 추정해 덮어쓰지 않는다. 작업마다 변경 파일과 Base Commit을 Evidence로 남긴다.

## 10. Docker 통합

### 사용자 경험

~~~powershell
docker build -t pacs-ai:test .
docker compose up
inv up
~~~

표면상 표준 Docker CLI를 지원하되, 실제 실행은 Docker Context 또는 INV Docker Proxy를 통해 정책이 적용된 Build Service와 Runtime Node로 전달한다.

### 보안 경계

- Host Docker Socket 직접 Mount 금지
- Privileged Container 기본 금지
- Host Path Mount Allowlist
- Image Signature, Digest, SBOM과 Vulnerability Scan
- Build Secret은 BuildKit Secret Mount 등 일시 주입
- Registry Push와 Production Deploy는 승인 분리
- GPU Device 요청은 Workload ResourceRequest로 변환

### Build 흐름

~~~mermaid
flowchart LR
    SRC[Git Commit] --> PLAN[Build Plan]
    PLAN --> POLICY[Policy Check]
    POLICY --> BUILD[Isolated BuildKit]
    BUILD --> TEST[Test Stage]
    TEST --> SCAN[SBOM and Scan]
    SCAN --> IMG[Image Digest]
    IMG --> REG[Registry]
    REG --> RUN[INV Deployment]
~~~

## 11. MLOps 통합

MVP는 Git, MLflow, INV Storage, Docker, Ray 또는 PyTorch와 OpenTelemetry의 조합으로 시작한다.

### 핵심 Entity

- Experiment
- TrainingRun 또는 EvaluationRun
- DatasetVersion
- CodeVersion
- EnvironmentVersion
- Metric
- Parameter
- Artifact
- Model
- ModelVersion
- Evaluation
- Deployment

### Lineage

~~~mermaid
graph LR
    REPO[Repository] --> COMMIT[Commit]
    DATA[Dataset Version] --> RUN[Training Run]
    COMMIT --> RUN
    ENV[Image Digest] --> RUN
    RUN --> METRIC[Metrics]
    RUN --> ART[Artifacts]
    RUN --> MV[Model Version]
    MV --> EVAL[Evaluation]
    EVAL --> APPROVAL[Approval]
    APPROVAL --> DEPLOY[Deployment]
    DEPLOY --> MON[Monitoring]
~~~

Model Version은 Dataset Version, Code Commit, Parameter, Runtime Image, Hardware Profile, Metrics와 Evaluation Evidence를 참조해야 승인 가능하다.

## 12. Secret과 Credential

### 범위

- User Secret: 개인 Provider Token과 SSH Key
- Project Secret: Database, Registry와 서비스 Credential
- Runtime Credential: Run에만 유효한 짧은 Token
- Node Credential: Agent 인증서와 Rotation 상태

### 주입 원칙

1. Policy가 필요한 Secret의 사용을 승인한다.
2. Vault가 대상 Run과 Scope가 제한된 Credential을 발급한다.
3. Runtime은 Environment Variable보다 File 또는 Memory 기반 주입을 우선한다.
4. Log와 Trace Export 전에 Redaction한다.
5. Run 종료 시 Credential을 폐기하거나 만료시킨다.

AI Agent에는 Secret 값 자체 대신 CredentialRef와 사용 가능한 Tool만 제공한다.

## 13. 명령 위험 등급

| Level | 예 | 기본 처리 |
|---|---|---|
| L0 | pwd, ls, git status, test 실행 | 자동 허용 |
| L1 | Workspace 파일 수정, package 설치, docker build | Sandbox와 Project Policy |
| L2 | deploy, registry push, Node 설정, compose down | 역할 확인과 승인 |
| L3 | disk format, unrestricted delete, host registry 변경, credential export | 기본 차단 |

문자열 Pattern만으로 분류하지 않는다. 실행 주체, Target, Working Directory, 권한, Network, Data Sensitivity와 예상 부수 효과를 함께 평가한다.

## 14. 개발 여정

1. 사용자가 Template과 Repository로 Workspace를 생성한다.
2. 필요한 AI CLI를 연결하고 Project Data Policy를 확인한다.
3. AI와 사람이 코드를 작성하고 Test를 실행한다.
4. Commit SHA를 고정한 뒤 격리 Build를 수행한다.
5. Scheduler가 Dataset과 GPU 위치를 고려해 Training 또는 Evaluation을 배치한다.
6. Metrics, Artifact와 Model Version을 Experiment에 기록한다.
7. Evaluation Gate와 사람 승인을 통과한다.
8. Immutable Image와 Model Digest로 Deployment한다.
9. 운영 Metrics가 새 평가와 개발 Backlog로 돌아온다.

## 15. 완료 기준

- Bash와 PowerShell Workspace가 Project별로 생성되고 재현된다.
- Workspace와 물리 Node의 차이가 UI와 API에서 명확하다.
- Git Commit에서 Build, Run, Model과 Deployment까지 Lineage 조회가 된다.
- Docker Socket 노출 없이 Build와 GPU Container 실행이 가능하다.
- 두 개 이상의 AI CLI Adapter가 같은 Policy와 Evidence 계약으로 실행된다.
- L2 승인이 RunGraph에서 중단과 재개로 표현된다.
- Secret 원문이 Repository, Log, Trace와 Artifact에 남지 않는다.
- 5 Node 중 적합한 Node를 선택한 이유를 inv explain이 제공한다.

## 관련 문서

- [[Overview]]
- [[기술 문서]]
- [[시스템 스키마]]
- [[보안 평가 운영 가이드]]
- [[Ontology 설계]]
