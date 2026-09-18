---
doc_id: "HIST-RESOURCE-OFFER-REPORT-20260911"
title: "RESOURCE-OFFER Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T14:56:20+09:00"
source_of_truth: "Git"
---

# 자원 제공량과 예약 원자 반영 검증

[[2026-09-11_RESOURCE-OFFER_Codex_착수]]의 base d945633에서 Claude 9ab84ab를 b5d265a로 가져와 검토하고, Codex 수정 `01fdb15556cea77b4e6f62a5f09ad45848904e6b`를 agent/codex/resource-offer-integrity에 push했다. [검토용 draft PR #22](https://github.com/egparadise/SaintVision-Invion/pull/22)은 agent/codex/provisioning-integrity를 기준으로 한다. 원저자 이력을 보존했으며 Codex 수정의 독립 reviewer Claude는 대기다. main 병합·운영 DB migration·계정·프로필 적용은 수행하지 않았다.

## 구현과 합격 범위

CPU millicores와 RAM/storage bytes의 capability 제공 총량을 Node의 같은 종류 모든 kernel resource에 반영한다. 현재 resources.manage 권한을 서비스/DB 양쪽에서 확인하고 Node→정렬된 Resource 잠금 뒤 미반납 lease를 다시 조회한다. 만료된 lease도 실제 반환 전에는 점유로 계산한다. 기존 예약보다 작은 요청은 거부하며 모든 slice 제공량의 합은 요청 총량과 일치한다. public history와 kernel 변경은 한 transaction이고 뒤늦은 history 저장 실패에도 함께 rollback한다. 기존 함수의 runtime EXECUTE를 회수하고 inv_app 직접 kernel UPDATE 금지를 유지했다.

0031은 두 0030 migration 이력을 보존한다. 미등록 resource 또는 device mapping이 없는 GPU는 pending 사유를 반환한다. 등록 자원은 mTLS 실측과 별개이며 appliedToKernel=true도 executionReady를 보장하지 않는다. 상세 계약은 [[Codex 자원 제공량과 예약 원자 반영 계약]]/ADR-069, 발견·수정은 [[2026-09-11_RESOURCE-OFFER_오류와해결]]이다.

사용자가 전달한 Claude 질문에 따라 실제 결과 정본을 `services/control-plane/src/inv/result_view.py`로 확정했다. Claude의 중복 결과/다운로드/attempt 구현은 호출자를 정본으로 이관한 뒤 제거하며 readiness와 업무 CRUD 및 migration/data는 보존한다. [[Codex 실제 실행 결과 조회 계약]] v1.1.0을 따른다. 중복 코드 제거 자체는 다음 Claude 작업이다.

Gemini의 제안은 [[3 Agent 원격 실행과 운영 인수 확정]]에 보완 확정했다. 프로필 설치와 schedulable 판정을 구분하며 Gemini 최종 브라우저 인수는 Codex 원격 시험 및 Claude 운영 계정/Workspace/권한/제공량 준비가 모두 선행해야 한다.

## 실제 검증과 증거

| 검증 | 결과 |
|---|---|
| python -m pytest tests/core tests/test_migrations.py -q --tb=short | clean 01fdb15, 290 passed, exit 0, 23.14초. 의존성 deprecation warning 2개 |
| 구현 중 집중 통합 | 43 passed, exit 0, dirty b5d265a. 최초 SQL setup 오류와 이후 시험 구성 2개 실패는 오류 문서에 보존 |
| 최종 격리 PostgreSQL/Node 통합 | clean 01fdb15, 297 passed, 실패/오류/skip 0, exit 0, 2026-09-11T05:56:14.537037+00:00 |
| 공개 prior → head → head 재실행 | test_account_integration에서 16개 경로 통과, 기존 sentinel/Workspace 값 보존 |
| tools/export_schemas.py --check | 업무 19개 schema 일치, exit 0 |
| tools/check_docs.py / tools/check_ontology.py / git diff --check | 구현 commit 시 통과, exit 0. 최종 문서·sync는 후속 기록 |

Python은 C:/Project/SaintVision-Invion/.venv/Scripts/python.exe, Go는 로컬 1.27.1이다.

```text
python tools/check_kernel_docker.py --go C:/Project/SaintVision-Invion/.work/node-toolchain-1.27.1/go/bin/go.exe --prepare-only
python tools/check_kernel_docker.py --prepared .work/sv-kernel-90b59063525e/prepared.json --tests tests/test_business_results.py tests/test_result_readiness.py tests/test_account_integration.py tests/test_projects.py tests/test_settings.py tests/test_login.py tests/test_api.py tests/test_pools.py tests/test_migrations.py tests/test_contracts.py tests/integration/test_resource_offer_integrity.py tests/integration/test_provisioning_integrity.py tests/integration/test_result_observation.py tests/integration/test_account_production.py tests/integration/test_workspace_start.py tests/integration/test_business_handoff.py tests/integration/test_containment.py
```

[최종 통합 Evidence](../Evidence/resource-offer-01fdb15.json) SHA-256 `3a4539b7727679b4552bc56d65f47ed8297485251ec351e741877a9a8dcb619f`. 코드/source/Node binary/image와 모든 case, stopped runner/DB 및 소유·빈 상태를 확인한 network 해제를 기록했다. JWT API·별도 inv_app 역할·동시 예약/제공량·권한 회수·GPU pending·늦은 실패 rollback과 실제 로컬 Node 실행/취소/출력 복구 회귀다. 두 물리 PC·GPU·장시간 부하 시험은 아니다. private pytest 로그/DSN/JWT/개인키는 공개하지 않는다.

[CI 기록](../Evidence/resource-offer-01fdb15-ci.json): Backend 34567599834, Core 34567599838, Docs 34567599822. 기존 계정 결제/spending 제한으로 job 시작 전 실패했으며 계정 변경이나 반복 재시도는 하지 않았다.

## 남은 작업과 담당

[2026-09-11 14:53 KST 실제 관측](../Evidence/resource-offer-live.json): 원격 192.168.45.225 / nod_01M25VZZFBYQVFGYB11G7HC10J는 online/fresh지만 lan-observe-v1이다. offered는 비어 있고 운영 kill switch=true, 업무 제출 및 웹 인증 설정은 false다. 표시된 16 CPU는 제공량이 아니며 RAM은 Linux Node 가시 범위, GPU는 unknown이다. 아직 설치 결과 JSON을 받지 않았다.

- Codex: [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]]의 profile/실제 image/identity·journal 보존 확인 후 원격 Python, CPU 학습, 실행 전 취소, 실행 중 취소, 실패, timeout, output recovery 7개를 검증한다. 중복 전달·격리·출력 해시·자원 반환은 case 내 assertion이다. reviewer 회신을 통합한다.
- Claude: 최신 kernel/0031 독립 검토, 실제 운영 IdP/계정·프로젝트 grant·Workspace 파일·제공량 준비, 정본 결과로 호출자 이관 및 중복 제거, 운영 시작/복구 절차.
- Gemini: 실제 API telemetry/예약 가능량/차단 사유/정본 결과를 연결한다. Codex와 Claude 선행 완료 후 편집→승인→원격 실행→취소/복구→결과 다운로드 브라우저 인수. Node-04는 실제 ID와 연결된 표시 이름만 허용한다.

현재 2-PC는 서버 1대와 원격 worker 1대다. 두 실행 Node 병렬 학습 또는 GPU 합격을 뜻하지 않는다. 등록된 전체 task, CI, 독립 검토 및 실제 운영 인수는 완료 처리하지 않았다. 검토 자료는 Git/Obsidian/draft PR로 제공하며 다른 Agent에게 직접 메시지를 보내거나 독립 검토를 했다고 표시하지 않는다.

2026-09-11T14:56:52+09:00 최종 문서 검사: `python tools/check_docs.py`는 원문 24개/버전 문서 239개/48 task 검사를, `python tools/check_ontology.py`는 RDF/SHACL 검사를 통과했다(각 exit 0). `git diff --check`도 exit 0이었다. `python tools/sync_obsidian.py --check --state .work/offer-sync-state.json`은 374개 관리 파일/14개 반영 대기/충돌 0, 이어 `--apply`는 14개 파일 반영/374개 hash 일치, `--check`는 반영 대기 0/충돌 0으로 모두 exit 0이었다. 이 실행 기록 추가분을 같은 state로 후속 반영한다. 원문·미관리 파일은 변경하지 않았다. 다음 독립 reviewer는 Claude다.
