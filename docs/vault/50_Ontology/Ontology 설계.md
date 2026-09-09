---
title: Saint Vision INV Ontology 설계
aliases:
  - Ontology 설계
  - INV Ontology
tags:
  - saintvision
  - inv
  - ontology
  - knowledge-graph
status: draft
version: 0.1.0
updated: 2026-09-09
---

> [!important] 기존 설계 원문 참조
> 충돌 시 [[최종 개발 계획 - 모든 개발의 지침]]과 [[설계 충돌 정정 및 ADR]]을 따릅니다. 이 문서는 원문 보존용이며 확정 구현 사양이 아닙니다. 원본은 Git `docs/sources/50_Ontology/Ontology 설계.md`에 SHA-256과 함께 보존됩니다.

# Saint Vision INV Ontology 설계

## 1. 목적

INV Ontology는 인프라, 개발, 실행, AI와 MLOps, 정책과 증거를 같은 의미 체계로 연결한다. Database Schema를 대체하지 않으며, 서비스별 데이터를 통합 조회하고 Lineage와 정책 근거를 교환하는 Semantic Layer다.

초기 Namespace는 다음과 같다.

| Prefix | IRI |
|---|---|
| sv | https://saintvision.ai/ontology/core# |
| inv | https://saintvision.ai/ontology/inv# |
| dev | https://saintvision.ai/ontology/dev# |
| ml | https://saintvision.ai/ontology/mlops# |
| sec | https://saintvision.ai/ontology/security# |
| res | https://saintvision.ai/resource/ |

Turtle 초안은 [[saintvision-inv.ttl]], 예제 Instance는 [[saintvision-inv.example.jsonld]]에 있다.

## 2. 설계 원칙

- 제품 Database의 내부 Table 이름이 아니라 안정적인 Domain 개념을 모델링한다.
- Class 이름은 PascalCase, Property 이름은 camelCase를 사용한다.
- 장기 식별자는 IRI로 표현하고 표시 이름은 rdfs:label로 분리한다.
- 민감한 Credential 값과 개인 데이터는 RDF에 넣지 않고 Reference와 분류만 표현한다.
- 사실, 계획, 관측과 결정은 구분한다.
- Event와 Snapshot에 유효 시각과 출처를 기록한다.
- 기존 표준을 재사용할 때 내부 계약에 필요한 의미를 명확히 고정한다.
- Ontology Version과 Application Schema Version을 Release Manifest에서 연결한다.

## 3. 상위 Class

~~~mermaid
classDiagram
    class Entity
    class Actor
    class DigitalAsset
    class InfrastructureEntity
    class WorkEntity
    class GovernanceEntity
    class EvidenceEntity

    Entity <|-- Actor
    Entity <|-- DigitalAsset
    Entity <|-- InfrastructureEntity
    Entity <|-- WorkEntity
    Entity <|-- GovernanceEntity
    Entity <|-- EvidenceEntity

    Actor <|-- User
    Actor <|-- Agent
    InfrastructureEntity <|-- Cluster
    InfrastructureEntity <|-- Node
    InfrastructureEntity <|-- Resource
    WorkEntity <|-- Project
    WorkEntity <|-- Workspace
    WorkEntity <|-- Workload
    WorkEntity <|-- Run
    GovernanceEntity <|-- Policy
    GovernanceEntity <|-- PolicyDecision
    EvidenceEntity <|-- AuditEvent
    EvidenceEntity <|-- Artifact
~~~

## 4. Domain별 Class

### 4.1 제품과 주체

- Platform
- Tenant
- User
- Organization
- Role
- Agent
- AgentProfile
- Project

### 4.2 인프라와 자원

- Cluster
- Node
- NodeAgent
- Capability
- Resource
- CPUResource
- GPUResource
- MemoryResource
- StorageResource
- NetworkResource
- ResourceOffer
- ResourceSnapshot
- ResourceLease
- PlacementPlan
- NetworkLink

### 4.3 개발

- DevelopmentWorkspace
- WorkspaceTemplate
- DevelopmentEnvironment
- TerminalSession
- Shell
- CLI
- AITool
- AIToolAdapter
- Repository
- SourceCode
- CodeCommit
- Build
- TestRun
- ContainerImage
- Notebook
- ToolInvocation

### 4.4 실행

- Workload
- ResourceRequest
- Run
- Task
- RunAttempt
- RunGraph
- Checkpoint
- Runtime
- ContainerRuntime
- DistributedRuntime
- ModelServingRuntime

### 4.5 데이터와 MLOps

- Dataset
- DatasetVersion
- DataLocation
- Experiment
- TrainingRun
- EvaluationRun
- Metric
- Artifact
- Model
- ModelVersion
- Deployment
- MonitoringSignal

### 4.6 정책과 증거

- Policy
- PolicyRule
- PolicyDecision
- Approval
- RiskLevel
- Secret
- CredentialReference
- AuditEvent
- EvidenceBundle
- ProvenanceRecord

## 5. 핵심 Object Property

| Property | Domain | Range | 의미 |
|---|---|---|---|
| hasWorkspace | Project | DevelopmentWorkspace | Project가 Workspace를 가짐 |
| usesRepository | DevelopmentWorkspace | Repository | Workspace가 Source Repository를 사용 |
| hasTerminal | DevelopmentWorkspace | TerminalSession | Workspace에 Terminal Session이 열림 |
| usesShell | TerminalSession | Shell | Terminal이 사용하는 Shell |
| enablesTool | DevelopmentWorkspace | AITool | Workspace에서 사용 가능한 AI 또는 CLI Tool |
| implementedByAdapter | AITool | AIToolAdapter | Tool을 실행하는 Provider Adapter |
| submitsWorkload | DevelopmentWorkspace | Workload | Workspace가 Workload를 제출 |
| createsRun | Workload | Run | Workload가 실행 시도를 생성 |
| hasTask | Run | Task | Run이 Task를 포함 |
| requiresResource | Workload | ResourceRequest | 필요한 자원 요청 |
| scheduledBy | Run | PlacementPlan | Run이 따르는 배치 계획 |
| selectsNode | PlacementPlan | Node | 계획이 Node를 선택 |
| holdsLease | Run | ResourceLease | Run이 Resource Lease를 보유 |
| leasesResource | ResourceLease | Resource | Lease 대상 자원 |
| containsNode | Cluster | Node | Cluster가 Node를 포함 |
| advertisesCapability | Node | Capability | Node가 Capability를 광고 |
| offersResource | Node | ResourceOffer | Node가 제공 정책에 따라 자원을 제공 |
| describesResource | ResourceOffer | Resource | Offer가 설명하는 자원 |
| locatedOn | DataLocation | Node | 데이터 복제본 또는 Cache의 Node |
| hasLocation | DatasetVersion | DataLocation | Dataset Version의 위치 |
| consumesDataset | Run | DatasetVersion | Run이 입력 데이터 사용 |
| producesArtifact | Run | Artifact | Run이 Artifact 생성 |
| usesCommit | Run | CodeCommit | Run의 Source Version |
| usesImage | Run | ContainerImage | Run의 Runtime Image |
| registersModel | Run | ModelVersion | Run이 Model Version 생성 또는 등록 |
| deploysModel | Deployment | ModelVersion | Deployment가 배포하는 Model |
| governedBy | Run | Policy | Run에 적용된 Policy |
| hasDecision | Run | PolicyDecision | Run에 내려진 정책 결정 |
| requiresApproval | PolicyDecision | Approval | 결정이 사람 승인을 요구 |
| emitsAuditEvent | Run | AuditEvent | Run이 감사 Event 발생 |
| supportedByEvidence | PolicyDecision | EvidenceBundle | 결정의 근거 |
| usesCredential | ToolInvocation | CredentialReference | Tool이 값이 아닌 Credential 참조 사용 |

## 6. 핵심 Datatype Property

| Property | Range | 설명 |
|---|---|---|
| displayName | xsd:string | 사람에게 보이는 이름 |
| status | xsd:string | 표준 상태 값 |
| version | xsd:string | 개념 또는 Artifact Version |
| observedAt | xsd:dateTime | 관측 시각 |
| createdAt | xsd:dateTime | 생성 시각 |
| expiresAt | xsd:dateTime | Lease와 Credential 만료 |
| cpuCores | xsd:decimal | CPU Core 수 |
| memoryBytes | xsd:integer | Memory 양 |
| vramBytes | xsd:integer | GPU Memory 양 |
| storageBytes | xsd:integer | Storage 양 |
| bandwidthBps | xsd:integer | Link Bandwidth |
| latencyMs | xsd:decimal | Link Latency |
| riskCode | xsd:string | L0, L1, L2 또는 L3 |
| checksum | xsd:string | Artifact와 Dataset 무결성 |
| commitSha | xsd:string | Source Commit |
| imageDigest | xsd:string | Container Image Digest |
| correlationId | xsd:string | 전 구간 추적 ID |

수량은 단위를 Property 이름에 숨기지 않고 QUDT 같은 단위 Ontology를 도입할 수 있다. MVP 파일은 구현 편의를 위해 Bytes, bps와 ms 전용 Property를 제공한다.

## 7. 핵심 제약

### Node

- 하나 이상의 Capability를 가진다.
- 하나 이상의 최신 ResourceOffer를 가질 수 있다.
- quarantined Node는 active Lease의 새 대상이 될 수 없다.

### Run

- 정확히 하나의 Workload에서 생성된다.
- scheduled 이후 상태는 하나의 PlacementPlan을 가져야 한다.
- running 상태는 하나 이상의 유효한 ResourceLease를 가져야 한다.
- succeeded 상태는 EvidenceBundle과 종료 시각을 가져야 한다.

### ResourceLease

- 정확히 하나의 Run과 연결된다.
- 하나 이상의 Resource를 임대한다.
- expiresAt과 Fencing Token을 가져야 한다.

### ModelVersion

- 생성 Run 또는 외부 Provenance를 가져야 한다.
- Version, Checksum과 Artifact 위치를 가져야 한다.
- Production Deployment 전 Evaluation과 Approval을 가져야 한다.

### CredentialReference

- Secret 값 자체를 Literal로 갖지 않는다.
- Owner, Provider, Scope와 만료 정책을 표현한다.

위 제약은 OWL 추론만으로 강제하지 않고 SHACL 또는 Application Validation으로 검증한다.

## 8. 동일 개념의 상태 분리

Ontology는 다음을 혼동하지 않는다.

| 구분 | 예 |
|---|---|
| Capability | Node가 CUDA Runtime을 지원함 |
| Offer | Host가 GPU 1개를 INV에 제공함 |
| Snapshot | 현재 GPU 사용률이 12퍼센트임 |
| Request | Workload가 VRAM 16GiB를 요구함 |
| Lease | Run이 GPU Device 0을 2시간 예약함 |
| Usage | 실제 Run의 VRAM 사용량이 13GiB임 |

## 9. Provenance

각 관측과 결정에는 다음을 연결한다.

- 생성 주체 User, Agent 또는 Service
- Source System과 Source Record ID
- 생성 시각과 유효 시각
- Schema와 Ontology Version
- 입력 Snapshot과 Policy Version
- Correlation ID, Run ID와 Attempt ID
- 변환 또는 계산 방법
- Checksum 또는 Signature

W3C PROV-O와 Dublin Core Terms를 선택적으로 재사용하되 제품 계약에서는 필요한 Profile을 고정한다.

## 10. Competency Question

Ontology는 다음 질문에 답할 수 있어야 한다.

1. Project P가 현재 사용할 수 있는 GPU와 총 VRAM은 무엇인가?
2. Dataset D의 최신 Version이 어느 Node와 Storage에 있는가?
3. Run R이 Node N에 배치된 이유와 제외된 후보는 무엇인가?
4. ModelVersion M은 어떤 Dataset, Commit, Image와 Parameter로 생성되었는가?
5. Deployment X가 어떤 Approval과 Evaluation Evidence를 근거로 Production에 배포되었는가?
6. 특정 AI CLI가 어떤 Credential Scope와 Policy로 Workspace에서 실행되었는가?
7. quarantined Node에서 생성된 Artifact가 존재하는가?
8. Node 손실 이후 재시도된 Run Attempt와 Fencing Token은 무엇인가?
9. 특정 Source Commit이 영향을 준 Build, Test, Model과 Deployment는 무엇인가?
10. L2 또는 L3 명령 중 승인되지 않았거나 차단된 Invocation은 무엇인가?

## 11. 예제 질의

### Dataset 지역성을 고려한 후보 조회

~~~sparql
SELECT ?node ?gpu ?location
WHERE {
  ?datasetVersion a ml:DatasetVersion ;
                  inv:hasLocation ?location .
  ?location inv:locatedOn ?node .
  ?node inv:offersResource ?offer ;
        inv:advertisesCapability ?capability .
  ?offer inv:describesResource ?gpu .
  ?gpu a inv:GPUResource .
}
~~~

### Model Lineage

~~~sparql
SELECT ?modelVersion ?run ?dataset ?commit ?image
WHERE {
  ?run inv:registersModel ?modelVersion ;
       inv:consumesDataset ?dataset ;
       dev:usesCommit ?commit ;
       dev:usesImage ?image .
}
~~~

## 12. Application Schema 매핑

| Application Entity | Ontology Class |
|---|---|
| projects | sv:Project |
| workspaces | dev:DevelopmentWorkspace |
| nodes | inv:Node |
| resource_snapshots | inv:ResourceSnapshot |
| workloads | inv:Workload |
| resource_leases | inv:ResourceLease |
| placement_plans | inv:PlacementPlan |
| runs | inv:Run |
| datasets | ml:Dataset |
| dataset_versions | ml:DatasetVersion |
| artifacts | ml:Artifact |
| model_versions | ml:ModelVersion |
| policy_decisions | sec:PolicyDecision |
| approvals | sec:Approval |
| audit_events | sec:AuditEvent |

RDF IRI는 Database Primary Key에서 결정적으로 만들 수 있지만, Database ID 재사용이나 환경 간 충돌이 없도록 Tenant와 Environment를 포함한 Mapping Policy를 둔다.

## 13. 버전과 배포

- Ontology IRI는 Major Version에서만 변경한다.
- 0.x 단계에서는 Deprecated Annotation과 Migration Note를 제공한다.
- CI에서 Turtle Parse, Undefined Term, Domain과 Range, SHACL Example Validation을 실행한다.
- JSON-LD Context는 Ontology Release와 함께 Version한다.
- 서비스는 Ontology 전체를 Runtime 의존성으로 강제하지 않고 필요한 Projection을 사용한다.

## 14. 확장 후보

- W3C PROV-O: Artifact와 Decision Provenance
- DCAT: Dataset Catalog
- SPDX 또는 CycloneDX: Software와 Container SBOM
- QUDT: 자원 수량과 단위
- SSN 또는 SOSA: Node Telemetry Observation
- SKOS: 상태, 위험 수준과 Capability Taxonomy

외부 Ontology를 도입할 때는 구현 복잡성보다 실제 상호운용 Query가 있는지 먼저 확인한다.

## 관련 문서

- [[시스템 스키마]]
- [[기술 관계도]]
- [[saintvision-inv.ttl]]
- [[saintvision-inv.example.jsonld]]
