---
doc_id: "HIST-TENANT-BOUNDARY-REPORT-20260911"
title: "TENANT-BOUNDARY Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T15:55:07+09:00"
source_of_truth: "Git"
---

# tenant 재현·결과 정본·입력 준비 통합

[[2026-09-11_TENANT-BOUNDARY_Codex_착수]]의 base 5de316d 위에서 Claude 4361584·529ac8b의 검토한 부분을 통합하고 `f4fe37ebbed3641f9bcfe2adf913da16e2a985be`를 기존 agent/codex/resource-offer-integrity와 [draft PR #22](https://github.com/egparadise/SaintVision-Invion/pull/22)에 push했다. 새 PR 적층은 만들지 않았다. Codex의 Claude 코드 검토는 [[2026-09-11_Claude_잔여보고_Codex_독립검토]], Codex 보완의 독립 reviewer는 Claude(대기)다. main 병합·운영 migration/계정/Node 변경은 미수행이다.

## 확인한 사실과 구현

0026까지만 적용한 DB의 tenant 누수는 재현됐다. 그러나 실제 적용된 0028_result_readiness_merge, 0030_provisioning_integrity, 0031_resource_offer_integrity 및 최종 0032는 타 tenant/미설정/빈 scope를 차단한다. 별도 inv_app 로그인 역할로 정상 tenant의 true 응답과 거부의 false 응답을 모두 확인했으며 계정 정지·subject 불일치·비활성 매핑도 거부됐다. 과거 파일에 current_setting이 없다는 사실을 최신 DB 함수의 동작과 혼동하지 않는다. 기존 원본을 수정하는 대신 현재 guard를 보호하는 반복 가능한 재현 도구와 회귀를 추가했다.

[적용 함수 증거](../Evidence/tenant-boundary-functions.json) SHA-256 `be4c42e2298e32a8eafa2b5fe8a0f8d6fe2de30a5a332f50a7f66872ab62295c`는 각 실제 Alembic revision과 pg_get_functiondef hash 및 결과를 기록한다. 새 DB의 합성 계정을 사용했고 운영 DB 상태를 바꾸거나 운영 tenant 정보를 읽지 않았다.

업무 results.py/중복 결과 라우터를 제거하고 합성 앱을 별도 readiness router로 전환했다. 결과·다운로드·로그·attempt는 kernel ResultView가 정본이다. 이미 PR #21/#22에 전달된 0029 및 0030 부모 이력을 보존했고, 0032로 두 0031을 합쳤다. 입력 준비는 현재 epoch·같은 Workspace/project·해당 attempt의 대기 Run만 보고 created_at으로 최신을 고른다. 입력 없음은 null과 상한/해결 주체를 반환한다. 별도 kernel_request_permission을 유지하므로 checks는 7개이며 executable=false·admissionRequired=true다. 실제 복원 prepare 후 조회 및 취소 후 준비 해제도 검증했다. 오류/충돌 처리는 [[2026-09-11_TENANT-BOUNDARY_오류와해결]]을 따른다.

## 실제 로컬 검증

| 명령·범위 | 결과 |
|---|---|
| 최초 revision별 subject 재현 | 1 passed, exit 0, dirty 5de316d. 0026 누수 및 후속 0028/0030/0031 거부 실측 |
| 입력/readiness/tenant 집중 회귀 | 20 passed, exit 0, dirty 5de316d, 2026-09-11 15:45:02 KST |
| python -m pytest tests/core tests/test_migrations.py -q --tb=short | 구현 중 290 passed, exit 0, 29.12초; 최종 clean 전체 기본 재실행으로 표시하지 않음 |
| 최종 아래 격리 PostgreSQL/Node 회귀 | clean f4fe37e, 305 passed, 실패/오류/skip 0, exit 0, 2026-09-11T06:54:45.785073+00:00 |
| 공개 prior → head → head 재실행 | 최종 test_account_integration의 18개 경로 통과, 기존 sentinel/Workspace 값 보존 |
| tools/export_schemas.py --check | 업무 19개 schema 일치, exit 0 |
| tools/check_docs.py / tools/check_ontology.py / git diff --check | 구현 commit 시 각각 exit 0. 최종 문서·sync는 아래 후속 기록 |

Python은 C:/Project/SaintVision-Invion/.venv/Scripts/python.exe, Go는 로컬 1.27.1이다.

```text
python tools/check_kernel_docker.py --go C:/Project/SaintVision-Invion/.work/node-toolchain-1.27.1/go/bin/go.exe --prepare-only
python tools/check_kernel_docker.py --prepared .work/sv-kernel-b4708215ad47/prepared.json --tests tests/test_execution_readiness.py tests/test_result_readiness.py tests/test_workspace_input_readiness.py tests/test_account_integration.py tests/test_projects.py tests/test_settings.py tests/test_login.py tests/test_api.py tests/test_pools.py tests/test_migrations.py tests/test_contracts.py tests/integration/test_subject_tenant_boundary.py tests/integration/test_resume_input_readiness.py tests/integration/test_resource_offer_integrity.py tests/integration/test_provisioning_integrity.py tests/integration/test_result_observation.py tests/integration/test_account_production.py tests/integration/test_workspace_start.py tests/integration/test_business_handoff.py tests/integration/test_containment.py
```

[최종 로컬 회귀 Evidence](../Evidence/tenant-boundary-f4fe37e.json) SHA-256 `8fa84e0de39edfc1745ee90f2006a7c31b80cf9b0fbbb7ae52768a6ac3ed4890`. 실제 code/source/binary/image, 모든 case 및 runner/DB 정지·소유 network 해제 결과를 기록했다. 공개 JSON은 LF로 저장하며 private pytest 로그/DSN/토큰/개인키는 공개하지 않는다. 두 물리 PC·GPU·장시간 부하·전체 백업 복원 시험은 아니다.

## CI·PR·운영 상태

[CI 기록](../Evidence/tenant-boundary-f4fe37e-ci.json)의 push/PR trigger 6개는 기존 account billing/spending 제한으로 모두 job 시작 전에 실패했다. run ID는 Core 34571631617/34571628154, Backend 34571631653/34571628103, Docs 34571631695/34571628093이다. 계정 설정이나 결제는 변경하지 않았고 반복 retry를 요청하지 않았다. 위 로컬 회귀 통과는 CI나 전체 통합 인수 완료가 아니다.

[PR 상태와 정리 근거](../Evidence/tenant-boundary-pr-status.json): #13·15·16·17·18·20은 이미 merged다. #11 head의 main ancestry와 #12의 main에 포함된 두 번째 parent와의 tree 동일성을 확인해 중복 draft 두 개를 closed 처리했다(새 merge 아님). branch/worktree는 보존했다. 15:51 KST 조회는 open 13/draft 12다. main f9be6b6와 최종 코드 f4fe37e의 merge-tree는 충돌이 없고, #19는 개발 과정 인덱스 문서 충돌이 있다. merge-tree 성공은 검토·CI 통과나 실제 merge가 아니다.

다음 합류는 #19의 편집/PTY/Git 범위 독립 검증과 이력 충돌 해결, 최신 계정/결과 계보의 선행 검토, #21→#22의 dependency 순서 및 같은 통합 SHA 검증으로 진행한다. 오래된 PR을 수만큼 반복 병합하지 않는다. 이번 작업에서 작성한 보완의 Claude 독립 검토와 CI가 남아 있어 새 main 반영을 완료 처리하지 않았다.

[최신 실제 Node 관측](../Evidence/tenant-boundary-live.json)은 2026-09-11T06:55:07.589419+00:00 기준이다. .225는 여전히 관측 전용 lan-observe-v1이며 운영 kill switch=true, 업무 제출/웹 인증 설정은 false다. 원격 설치 JSON을 받지 않았고 실제 7개 시험은 대기다. 설치 안내는 [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]]다.

- Codex: 원격 설치된 profile/실제 image/identity·journal 보존 확인 뒤 Python·CPU 학습·실행 전/중 취소·실패·시간 초과·출력 복구 7개, 검토 지적 보완과 이후 main 합류.
- Claude: f4fe37e/0032 및 기존 0030·0031 보완 독립 검토, 실제 운영 계정/Workspace 적용, public.artifacts 소비자·보존 정책 정리, 전체 백업 복원·장시간 부하 및 credential provider 선행이 있는 Context/LLM adapter.
- Gemini: kernel 결과 URL/7개 checks 배열/실제 관측·kernelLinked=false 사유를 연결하고 운영 계정과 원격 시험 완료 후 편집→승인→실행→복구→다운로드 브라우저 인수.

작성자 자기 검증·독립 검토·CI·물리 원격·운영 인수의 상태를 구분한다. 전체 task를 done으로 변경하지 않았으며 다른 Agent에게 직접 메시지를 보내거나 검토했다고 꾸미지 않았다.

2026-09-11T15:56:05+09:00 최종 문서 검사: `python tools/check_docs.py`는 원문 24개/버전 문서 243개/48 task 검사를, `python tools/check_ontology.py`는 RDF/SHACL 검사를 통과했다(각 exit 0). `git diff --check`도 exit 0이었다. `python tools/sync_obsidian.py --check --state .work/offer-sync-state.json`은 383개 관리 파일/17개 반영 대기/충돌 0, 이어 `--apply`는 17개 파일 반영/383개 hash 일치, `--check`는 반영 대기 0/충돌 0으로 모두 exit 0이었다. 이 실행 기록 추가분을 같은 state로 후속 반영한다. 원문·미관리 파일은 변경하지 않았다. 다음 독립 reviewer는 Claude다.
