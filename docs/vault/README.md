---
title: Saint Vision INV 설계 문서
aliases:
  - Saint Vision
  - INV
  - Inviz Virtual Infrastructure
tags:
  - saintvision
  - inv
  - overview
status: baseline
updated: 2026-09-09
---

> [!important] 기존 설계 원문 참조
> 충돌 시 [[최종 개발 계획 - 모든 개발의 지침]]과 [[설계 충돌 정정 및 ADR]]을 따릅니다. 이 문서는 원문 보존용이며 확정 구현 사양이 아닙니다. 원본은 Git `docs/sources/README.md`에 SHA-256과 함께 보존됩니다.

# Saint Vision INV 설계 문서

Saint Vision은 기존 Windows와 Linux 컴퓨터를 유지한 채, 각 장치가 허용한 CPU, GPU, 메모리, 저장소와 네트워크를 하나의 논리적 AI 개발 자원으로 조직하는 플랫폼이다. 사용자는 웹 작업공간에서 터미널, PowerShell, Git, Docker, Jupyter, MLOps와 AI 코딩 CLI를 사용해 프로그램과 AI 모델을 설계하고 실행한다.

INV는 Saint Vision의 분산 자원 가상화와 오케스트레이션 코어이며 공식 명칭은 **Inviz Virtual Infrastructure**다. 폴더 이름의 Invion은 프로젝트 저장 위치의 명칭으로 유지하되, 기술 엔진 명칭은 INV로 통일한다.

## 핵심 문서

| 영역 | 문서 |
|---|---|
| 전체 개요 | [[Overview]] |
| 개발 계획 | [[개발 플랜]] |
| 시스템 데이터 구조 | [[시스템 스키마]] |
| 기술 설계 기준 | [[기술 문서]] |
| 전체 흐름 시각화 | [[기술 그래프]] |
| 요구사항과 기술의 관계 | [[기술 관계도]] |
| 개발 작업공간 통합 | [[Dev Workspace CLI Git Docker MLOps AI CLI 통합 설계]] |
| Ontology 모델 | [[Ontology 설계]] |
| Turtle 초안 | [[saintvision-inv.ttl]] |
| JSON-LD 예제 | [[saintvision-inv.example.jsonld]] |
| 기존 상세 인덱스 | [[SaintVision INV 개발 설계 인덱스]] |
| 기술 출처 | [[최신 기술 출처와 설계 근거]] |

## 한 문장 제품 정의

> 기존 컴퓨터 자원을 하나의 가상 AI 컴퓨터로 통합하고, 그 위에서 소프트웨어와 AI의 개발, 실행, 학습, 배포와 운영까지 수행하는 AI Virtual Computing and Development Fabric.

## 반드시 지키는 경계

- 여러 컴퓨터의 CPU와 RAM을 물리적인 단일 SMP 컴퓨터로 만드는 제품이 아니다.
- 논리적 자원 풀을 제공하되 실제 노드 위치, 네트워크 비용, 데이터 위치와 사용자 부하는 보존한다.
- 요청 라우팅, 분산 작업, 모델 병렬 실행을 서로 다른 실행 모드로 구분한다.
- Workspace와 물리 Node를 분리하며, 일반 개발 명령은 격리된 Workspace에서 실행한다.
- AI Agent는 인프라를 직접 조작하지 않고 정책과 승인을 적용하는 Tool Gateway를 통과한다.
- 기존 운영체제, 사용자 파일과 일상 작업을 침해하지 않는다.

## 권장 읽기 순서

1. [[Overview]]
2. [[시스템 스키마]]
3. [[기술 문서]]
4. [[Dev Workspace CLI Git Docker MLOps AI CLI 통합 설계]]
5. [[개발 플랜]]
6. [[기술 그래프]]
7. [[기술 관계도]]
8. [[Ontology 설계]]
9. [[saintvision-inv.ttl]]
10. [[saintvision-inv.example.jsonld]]

## 문서 상태

이 문서 세트는 5대 PC 파일럿을 위한 설계 기준선이다. 구현 과정에서 중요한 결정이 바뀌면 관련 문서의 updated 값, Architecture Decision Record, 계약 스키마와 Ontology 버전을 함께 갱신한다.
