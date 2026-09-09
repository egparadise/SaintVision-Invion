---
title: Saint Vision INV Overview
aliases:
  - Overview
  - 제품 개요
tags:
  - saintvision
  - inv
  - product
  - architecture
status: baseline
updated: 2026-09-09
---

# Saint Vision INV Overview

## 결론

Saint Vision은 여러 PC를 물리적으로 한 대로 합치는 운영체제가 아니라, 기존 컴퓨터가 제공할 수 있는 자원을 실시간으로 발견하고 임대하여 하나의 **논리적 AI 개발 컴퓨터**처럼 사용하는 웹 기반 플랫폼이다. INV는 그 아래에서 자원, 실행, 정책, 데이터 위치와 장애 복구를 관리한다.

첫 목표는 같은 네트워크의 5대 PC다. 이후 VPN으로 연결된 원격 노드, 전용 GPU 서버, Kubernetes, Slurm과 클라우드까지 Adapter로 확장한다.

## 이름과 책임

| 이름 | 책임 |
|---|---|
| Saint Vision | 사용자가 접하는 제품, 웹 포털, 개발 경험과 AI Operator |
| INV | Inviz Virtual Infrastructure. 분산 자원 가상화, Scheduler, Node Agent와 실행 제어 |
| INV Dev Workspace | 코드 편집, 터미널, Git, Docker, Jupyter, AI CLI와 MLOps를 묶은 개발 환경 |
| INV AI Runtime | Ray, PyTorch, vLLM, CUDA, 모델 서빙과 학습 실행 |
| INV AI Operator | 자연어 요청을 계획으로 바꾸고 설명, 진단과 제한된 자동화를 수행하는 Agent 계층 |

## 사용자가 보는 경험

사용자는 브라우저에서 Saint Vision에 로그인해 프로젝트와 Workspace를 연다. 논리적 대시보드는 전체 제공 가능 자원을 합산해 보여주지만, 실행 시에는 물리 배치를 보존한다.

~~~text
Saint Vision INV Cluster

Nodes               5
Healthy             5
Virtual CPU         68 cores
Virtual RAM         192 GB
GPU                 5 devices
Aggregate VRAM      72 GB
INV Storage         6.4 TB
~~~

Aggregate VRAM은 현재 제공 가능한 장치 메모리의 합계 표시일 뿐, 모든 작업에서 하나의 GPU 메모리처럼 사용할 수 있다는 뜻은 아니다. 모델이 단일 GPU에 들어가지 않을 때는 지원 가능한 Tensor Parallel, Pipeline Parallel 또는 계층 분할 실행 계획이 별도로 필요하다.

## 목표

- 기존 PC를 포맷하거나 전용 장비로 바꾸지 않고 유휴 자원을 활용한다.
- 현재 사용자 작업을 방해하지 않도록 제공 한도와 선점 정책을 지킨다.
- 브라우저 하나에서 코딩부터 빌드, 테스트, 학습, 배포와 관찰까지 완료한다.
- 데이터 위치, GPU 메모리, 네트워크, 사용자 부하와 정책을 함께 고려해 작업을 배치한다.
- 실행 이유, 사용 자원, 정책 결정과 결과를 추적하고 설명한다.
- 상용 AI CLI와 오픈소스 Agent를 공급자별 Adapter로 연결한다.

## 비목표

- 여러 PC의 RAM을 일반 프로그램이 투명하게 공유하는 단일 주소 공간으로 제공하지 않는다.
- 네트워크가 느린 원격 GPU를 로컬 GPU와 동일한 성능으로 보장하지 않는다.
- 모든 모델과 프레임워크를 자동으로 다중 노드 분할하지 않는다.
- AI Agent에 무제한 관리자 권한을 주지 않는다.
- 5노드 MVP에서 완전한 Kubernetes 또는 Kubeflow 플랫폼을 먼저 구축하지 않는다.

## 제품의 다섯 기둥

1. **Resource Fabric**  
   Node가 제공한 CPU, GPU, RAM, Storage, Network와 가용 시간을 임대 가능한 자원으로 표현한다.

2. **Execution Fabric**  
   단일 Node 실행, 독립 작업 분산, 요청 라우팅, Gang Scheduling, 모델 병렬 실행을 구분한다.

3. **Development Fabric**  
   Web IDE, Terminal, PowerShell, Git, Docker, Jupyter와 프로젝트별 개발 환경을 제공한다.

4. **AI and MLOps Fabric**  
   AI CLI Adapter, Experiment Tracking, Dataset와 Model Version, Registry, Deployment를 연결한다.

5. **Trust Fabric**  
   인증, 권한, 위험 등급, 승인, Secret, Sandbox, Audit와 복구를 모든 실행에 적용한다.

## 핵심 설계 원칙

### Workspace와 Node의 분리

Workspace는 지속적인 프로젝트 경험이고 Node는 일시적인 실행 장소다. 편집 세션은 Node 1에 있어도 Docker Build는 Node 2, GPU Test는 Node 3, Dataset은 Node 5에 있을 수 있다.

### Control Plane과 Data Plane의 분리

Control Plane은 원하는 상태, 자원 임대, 정책, RunGraph와 Metadata를 관리한다. Data Plane은 실제 Process, Container, Model Runtime, 데이터 전송과 로그 수집을 담당한다.

### 데이터가 있는 곳으로 코드 이동

대용량 의료영상과 학습 데이터는 이동 비용이 크다. Scheduler는 가장 빠른 GPU만 고르지 않고, 데이터 지역성과 예상 전송 시간을 Placement Score에 포함한다.

### 결정론적 코어와 AI 보조

자원 임대, 권한 검증, Fencing과 상태 전이는 결정론적 코드가 소유한다. AI는 자연어 해석, 계획 후보, 장애 설명, 코드 작성과 운영 보조를 담당하며 정책을 우회할 수 없다.

### 제공자 중립

Claude Code, Codex, Orca 계열 도구, Antigravity와 기타 상용 또는 오픈소스 CLI는 사용자의 계정과 라이선스로 설치하고 인증한다. INV는 공통 Adapter, 실행 정책, 로그와 Secret 주입을 제공한다.

## 대표 사용자 여정

1. 관리자가 5대 PC에 INV Node Agent를 설치한다.
2. 사용자는 각 Node가 제공할 CPU, GPU, RAM, Storage, 시간대와 우선순위를 정한다.
3. 사용자는 Python AI 또는 Medical Vision AI 템플릿으로 Workspace를 만든다.
4. Web IDE와 PowerShell 또는 Bash에서 코드를 작성하고 Git에 커밋한다.
5. inv up 또는 포털 실행 버튼으로 WorkloadSpec을 제출한다.
6. Scheduler가 자원, 데이터 위치, 네트워크, 사용자 부하와 정책을 평가한다.
7. Runtime Manager가 선택된 Node에서 Container나 Process를 실행한다.
8. Run, 로그, Metrics, Artifact와 Model Version이 연결되어 저장된다.
9. 사용자는 inv explain에서 배치 이유와 대안을 확인한다.
10. 검증을 통과한 Image 또는 Model을 배포하고 관찰한다.

## MVP 성공 기준

| 지표 | 파일럿 목표 |
|---|---:|
| 시험 Node | 5대 등록 및 상태 추적 |
| Node 이탈 감지 | 60초 이내 |
| Scheduler 결정 P95 | 2초 이내 |
| Workspace 생성 성공률 | 95% 이상 |
| Run Evidence 기록 | 99.99% 이상 |
| 위험 명령 L3 | 기본 차단 100% |
| Secret 원문 로그 노출 | 0건 |
| 핵심 개발 여정 | 코드 작성부터 배포까지 종단간 성공 |

## 관련 문서

- [[README]]
- [[시스템 스키마]]
- [[기술 문서]]
- [[Dev Workspace CLI Git Docker MLOps AI CLI 통합 설계]]
- [[개발 플랜]]
- [[Ontology 설계]]
