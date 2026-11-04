---
doc_id: "HISTORY-20261104-PROJECT-NODE-CERTIFICATES-CODEX"
title: "2026-11-04 Project Node 인증서 관측 계약 Codex"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-11-04T13:52:06+09:00"
source_of_truth: "Git"
---

# 2026-11-04 Project Node 인증서 관측 계약 Codex

## 작업 계약

- 카드 `PROJECT-NODE-CERTIFICATE-OBSERVATION`, 부모 `SUPERVISION-20261104`; owner Codex, reviewer Claude pending; UI owner Gemini.
- 목표: PR #401이 제품에서 받지 못하던 실제 인증서 관측을 정식 authenticated project 경계에서 제공한다. 로컬 pilot console을 제품 API로 우회 연결하지 않는다.
- source checkout `D:/Project/SaintVisionI-Invion/supervision-integration-20261104`; branch `agent/codex/supervision-integration-20261104`; base `38d443b7e041b379a2d53b75b65c0d9e9e26bb25` + 아래 구현·fixture·생성 계약의 dirty input. 최종 code SHA는 후속 CI/report에 결속한다.
- 읽은 기준은 [[2026-11-04_전체개발_자동감독_착수_Codex]]의 GUIDE/GOV/ROADMAP/Skill 버전이며 추가로 기존 `node_channels`·`NodeResourceUsageResponse`의 grant/RLS/current-epoch 계약과 shared-fixture/serving-anchor 규칙을 대조했다.

## 제공 계약과 구현

`GET /v1/projects/{project}/node-certificates`는 기존 사용자 인증과 project grant 뒤에만 실행한다. 기존 `inv.node_channels.certificate_not_after`와 enabled 상태를 읽으므로 migration이나 새 signing authority가 필요하지 않다. tenant RLS, enabled project-node link, Node/channel/current runtime epoch를 함께 결속한다. certificate fingerprint·endpoint·issuer·private key는 응답에 포함하지 않는다.

정본은 `contracts/v1alpha1/core.schema.json`의 `ProjectNodeCertificateObservationResponse`다. 생성 Python/TS/Go·packaged schema·Node wire schema와 shared fixture를 함께 갱신했다. 기존 정의·서식을 보존하고 새 세 정의만 더했다.

- envelope: `source=execution-kernel`, `scope=project-node-certificates`, `projectId`, DB 시각 `observedAt`, `complete`, `items`, `trust`.
- Node item: `nodeId`, nullable `certificateNotAfter`, nullable `channelEnabled`.
- summary: `ok / renewal-window / expired / unknown` 및 nullable earliest expiry/권장 갱신 시작/남은 초. 갱신 창은 2일의 관측 기준이며 scheduler 등록이나 실제 자동 갱신을 주장하지 않는다.
- 201행까지 읽고 200행만 노출한다. 잘린 목록·0행·미관측/비활성 channel은 summary unknown이며 빈 집합을 정상으로 표시하지 않는다. 응답은 `Cache-Control: no-store`다.
- 프런트의 `fetchProjectNodeCertificates`는 같은 정본 schema, project identity, 중복 Node, freshness(60초·미래 skew 5초), summary의 실제 의미를 검사한다. 인증 실패를 이전 성공으로 대체하지 않는다. 만료의 ±1 microsecond와 음수 초 floor를 정확하게 검증한다.
- 표시·App/Desktop caller 연결은 Gemini에게 실제 전달했다. 이 계약 구현만으로 제품 UI 연결 완료라고 쓰지 않는다.

## 직접 실행한 증거

환경: Windows PowerShell, CPython **3.14.7**(`D:/Project/SaintVisionI-Invion/https-github.com-egparadise-SaintVision-Invion.git/.venv/Scripts/python.exe`), Node **v24.10.0**, npm **11.6.1**, Vitest **4.1.11**. 로컬 Docker Engine **20.10.22 / API 1.41 / Linux daemon**이다. 이 Docker는 disposable PG 시험에는 사용 가능하지만 Node-5 제품 인수의 API 1.45 요구를 충족했다는 뜻은 아니다.

- `python tools/generate_contracts.py`: exit 0. 생성 뒤 기존 정의의 의미 불변과 새 정의만의 추가를 대조했다.
- `python -m pytest -q tests/core/test_project_node_certificate_contract.py`: **13 passed**, exit 0.
- `npm --prefix apps/web test -- tests/node-certificate-observation-contract.test.ts`: 최종 **14 passed**, exit 0. 13:30:37 KST 시작. shared fixture/필수 필드·wrong-project·누락/비활성/잘림·stale/future·중복·거짓 정상·인증 회수·microsecond 경계를 포함한다.
- `python tools/run_vf_security_tests.py tests/integration/test_project_node_certificates.py`: **6 passed / 0 failed / 0 errors / 0 skipped**, runner와 pytest 직접 exit **0**. 실제 tmpfs PostgreSQL과 canonical HTTP/auth/project 경로를 실행했다. 13:29:11~13:29:29 KST. `isolatedContainerRemoved=true`.
- 최종 PG JUnit: `.work/vf-runs/node-certificate-contract-pg-9a4a229d56534c58aa923cc339b6bc22/tests.xml`, SHA-256 `686311c06e804ecf87b48d96fbcfabb08024368e9b7ab685e9b83e0fb8746bd1`. safe proof `.work/node-certificate-contract-pg.json`. 실제 grant 거부/미인증, 없는 channel, 만료, 비활성, old epoch, project link 회수, 잘못된 producer의 HTTP serving-anchor 거부를 포함한다.
- 앞선 PG 시도는 각각 fixture import 누락 **5 setup errors**, channel fixture의 forward CAS 누락 **2 passed / 3 failed**였다. 제품 guard를 낮추지 않고 fixture prerequisite와 `version+1`을 고쳤다. 그 원인·정정은 [[2026-11-04_Node_인증서_관측_검증_오류와해결]]에 보존한다.
- `python tools/check_contract_bindings.py`: exit 0(57 fixtures, 21 bound response types). `python tools/check_frontend_integrity.py`: exit 0(94 files, 9 rules, 0 violations).
- `python -m pytest -q tests/core/test_project_node_certificate_contract.py tests/core/test_serving_anchors.py tests/test_route_coverage.py`: **63 passed**, exit 0. 합계는 위 13을 포함하며 별도 76개로 더하지 않는다.
- microsecond verifier 변경 뒤 `npm --prefix apps/web run build`(TypeScript + Vite), `npm --prefix apps/web run lint`는 각각 직접 exit 0이다. 문서(1182 versioned pages), ontology, single-source ratchet(19 baseline pairs·새 중복 0), sync check(2090 managed·10 pending·0 conflicts·쓰기 0), whitespace gate도 각각 직접 exit 0이다. 최종 같은-SHA hosted CI와 reviewer 판정은 후속 delivery 기록에 결속한다.

## 실제 한계와 다음 담당

### 13:52 KST 독립 검토와 배포 컨테이너 보강

Claude는 `38d443b7..e97701bf`의 backend 계약과 microsecond verifier 의미를 독립 검토했고, 실제 PG/contract 19 passed와 frontend 14 passed를 보고했다. 다만 hosted Frontend `41774468131`의 Portal Container job에서 canonical root schema가 build context에 없어 TS2307로 실패했으므로 전체 delta 판정은 changes requested였다.

Codex는 `deploy/intranet/portal/Dockerfile`에 정본 schema **한 파일** COPY와 해당 Dockerfile 전용 ignore의 좁은 예외만 추가했다. 별도 schema 사본이나 public API 우회는 만들지 않았다. `5a980dba` + 이 두 수정의 dirty input에서 `DOCKER_BUILDKIT=1 docker build -f deploy/intranet/portal/Dockerfile -t saintvision-portal:supervision-20261104 .`를 실제 Linux daemon으로 실행해 **exit 0**을 확인했다. 이미지 config ID는 `sha256:3362916180a716666969b3ae4af83932bdadc8391323caaa19cf2f685e235301`, 로그는 `.work/portal-schema-context-build.log`다. Container 내부 Node 22의 `npm ci`, TypeScript와 Vite 빌드가 실행됐다. 독립 재검토와 수정 SHA의 hosted job은 아직 별도다.

같은 감독 과정에서 Codex root는 Claude 소유 PR #407 `5dd3f83b`의 fixture-only 월 구간 보강과 PR #403 `f42c4259`의 현재형 정정을 검토해 수락했다. 전자는 Claude의 115 actual-PG 통과 및 revert 실패 증거와 함께 판단했고, 후자는 11:04 기록을 보존하면서 12:08 착지를 명시한 정정만 수락했다. 점수나 운영 인수를 승격하지 않았다. 다음 행동은 이 source들을 격리 후보에 합치고 Gemini의 실제 caller 및 scheduler/provenance 수정까지 같은 최종 SHA로 검증하는 것이다.

`python -m pytest -q tests/test_intranet_portal_deploy.py`는 같은 수정에서 **71 passed**, 106.50초, 직접 exit 0이다. 이미지 빌드와 배포 검증의 성공을 기존 운영 Portal의 재배포로 해석하지 않는다.

이 결과는 실제 개발용 PG/HTTP 검증과 synthetic wire 변이의 증거다. 외부 IdP 운영 인수, 제품 브라우저와 이 API의 실제 연결, 5대 PC 인수, CP 신뢰·scheduler 등록은 별도다. 원래 48-task done을 승격하지 않는다.

다음 담당: Codex는 최종 code push·same-SHA CI와 Claude 검토를 결속하고, Gemini는 실제 App/Desktop caller와 unknown 표시를 연결한다. Claude는 병행 중인 VF-CL `verifiedAgainst` 재검증과 달력 변경으로 드러난 evidence partition fixture를 수정한다. 만료 r4는 보존하며 검토된 별도 r5 namespace 계획 뒤에만 운영 복구를 진행한다.
