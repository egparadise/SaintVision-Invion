---
title: SaintVision INV 개발 설계 인덱스
aliases:
  - SaintVision 개발 계획
  - INV 개발 로드맵
tags:
  - saintvision
  - inv
  - agent-engineering
  - system-design
status: baseline
updated: 2026-09-09
---

# SaintVision INV 개발 설계 인덱스

이 문서 모음은 SaintVision과 INV를 실제 코드로 구현하기 위한 기준선이다. 제품 정의, 여섯 가지 AI 엔지니어링 개념, 공통 용어, 시스템 경계, 구현 순서, 보안 통제, 평가 기준을 하나의 흐름으로 연결한다.

## 제품 한 문장 정의

**SaintVision은 기존 Windows와 Linux PC를 그대로 유지하면서 각 노드가 허용한 CPU, GPU, 메모리, 스토리지를 하나의 논리적 AI 개발 자원으로 조직하고, 웹 작업공간에서 코딩, 빌드, 테스트, AI 실행, 학습, 배포까지 수행하게 하는 AI Virtual Computing and Development Fabric이다.**

INV는 SaintVision 아래에서 노드, 자원, 작업, 정책, 실행을 담당하는 기술 엔진이며 공식 풀네임은 **Inviz Virtual Infrastructure**로 통일한다.

## 핵심 설계 결정

1. 기존 PC의 운영체제와 사용자 데이터를 재설치하거나 포맷하지 않는다.
2. 사용자가 보는 Workspace와 실제 실행 Node를 분리한다.
3. 제어 핵심은 결정론적으로 구현하고 AI는 계획, 설명, 진단, 보조 판단에 사용한다.
4. 모든 실행은 권한 정책, 자원 임대, 감사 기록, 검증 증거를 거친다.
5. 단일 에이전트로 시작하고 도구, 정책, 책임 계약이 달라질 때만 전문 에이전트를 추가한다.
6. 프롬프트, 컨텍스트, 도구, 그래프, 정책, 에이전트 구성을 모두 버전이 있는 코드와 데이터로 관리한다.
7. 데이터 이동보다 데이터 지역성을 우선하고, 의료영상 같은 대용량 데이터에는 코드를 데이터가 있는 곳으로 보낸다.

## 읽는 순서

1. [[README]]
2. [[Overview]]
3. [[시스템 스키마]]
4. [[기술 문서]]
5. [[Dev Workspace CLI Git Docker MLOps AI CLI 통합 설계]]
6. [[개발 플랜]]
7. [[기술 그래프]]
8. [[기술 관계도]]
9. [[Ontology 설계]]
10. [[saintvision-inv.ttl]]
11. [[saintvision-inv.example.jsonld]]

## 전체 문서 맵

### 시작과 개념

- [[README]]
- [[Overview]]
- [[용어 사전과 6단계 통합 모델]]

### Architecture

- [[시스템 아키텍처와 기술 스택]]
- [[시스템 스키마]]
- [[기술 문서]]
- [[기술 그래프]]
- [[기술 관계도]]
- [[Dev Workspace CLI Git Docker MLOps AI CLI 통합 설계]]

### Development

- [[개발 플랜]]
- [[단계별 개발 계획]]
- [[24주 구현 로드맵과 백로그]]
- [[공통 계약 요구사항과 완료 기준]]

### Ontology

- [[Ontology 설계]]
- [[saintvision-inv.ttl]]
- [[saintvision-inv.example.jsonld]]

### Governance와 Sources

- [[보안 평가 운영 가이드]]
- [[최신 기술 출처와 설계 근거]]

## 6단계 성숙도 모델

```mermaid
flowchart LR
    P[1 Prompt<br/>행동 지시] --> C[2 Context<br/>판단 재료]
    C --> H[3 Harness<br/>실행 환경]
    H --> G[4 Graph<br/>상태와 흐름]
    G --> R[5 ROOF<br/>통제와 복구]
    R --> A[6 Agent<br/>책임 있는 자율성]
    A --> E[평가와 운영 피드백]
    E --> P
```

이 여섯 단계는 일회성 폭포수가 아니다. 첫 구현은 순서대로 기준을 만들되, 운영 이후에는 평가 결과가 Prompt, Context, Harness, Graph, ROOF, Agent 정의를 다시 개선하는 순환 구조로 관리한다.

## 저장 위치와 코드 위치

- 설계 지식 기준선: 현재 Obsidian 폴더
- 구현 저장소 예정 위치: `C:\Project\SaintVision-Invion`
- 현재 구현 저장소 상태: 빈 폴더이므로 0단계에서 Git 저장소와 기본 구조를 생성한다.
- 원칙: Obsidian은 토론과 장기 지식, Git 저장소의 `docs/`는 실행 중인 에이전트가 읽는 최신 시스템 기록으로 사용한다. 승인된 설계는 두 위치에 동일한 문서 ID와 버전을 유지한다.

## 바로 시작할 첫 작업

- [ ] 제품 범위와 MVP 비범위를 승인한다.
- [ ] 5대 시험 노드의 OS, CPU, GPU, RAM, 네트워크, 제공 가능 폴더를 조사한다.
- [ ] 저장소를 초기화하고 `AGENTS.md`, `ARCHITECTURE.md`, `docs/`, `contracts/`를 만든다.
- [ ] `NodeRegistration`, `Heartbeat`, `ResourceSnapshot`, `WorkloadSpec`, `PolicyDecision`, `RunRecord` 계약을 먼저 정의한다.
- [ ] 한 대의 노드를 등록하고 웹에서 상태를 확인하는 첫 수직 기능을 완성한다.
- [ ] 위험 명령 기본 차단과 감사 로그를 첫 실행부터 적용한다.

## 변경 관리

설계 변경은 문서의 `updated` 날짜와 관련 ADR을 갱신한다. 구현이 문서와 달라지면 코드를 임시 진실로 방치하지 않고 같은 작업에서 문서 또는 코드를 일치시킨다. 중요한 변경은 평가 데이터와 완료 기준까지 함께 갱신한다.
