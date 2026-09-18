---
doc_id: "HIST-REGISTRY-RUNTIME-001"
title: "Registry frozen workload와 실행권한 결속"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T13:14:42+09:00"
source_of_truth: "Git"
---

# Registry frozen workload와 실행권한 결속

VF-CX-02/03, owner Codex/reviewer Claude(결과 대기), base1b39d40, branch agent/codex/model-registry-binding. 공통/개인 진행판과 agent-delivery1.1.0/core-reliability1.0.0 지침 적용. 범위: 기존 registry 결속을 frozen workload와 승인·dispatch·delivery·claim에 연결. 운영 배포·image lane은 제외한다.

## 수신

사용자 clean1b39d40/PG16(55432) 독립 검증: tests/integration/test_model_registry_revalidation.py 및 test_model_registry_binding.py,23passed/0failed/0skipped. 작성자23건과 합산하지 않는다. 기존 helper 검증 보강이다. 외부 대기 네 건(Actions 결제, gh 인증, 호스트 조치, 원격 profile/mTLS)은 미완 유지하며 CI 조회 재시도하지 않는다. Claude R5-01/02 수정 및 e89a415/8c347b7 독립 검토는 진행 보고만 수신했고 완료로 기록하지 않는다.

## 구현 경계

운영자 Database.registry_binding_policy 설정은 typed RegistryBindingPolicy이며 BoundDatabase에도 전달한다. 설정된 경우 prepare에서 정확한 registryVersionId와 기존 binding을 필수로 요구한다. 네트워크/파일 읽기 전후 같은 registry snapshot을 재검사한다. model/registry.json에 canonical binding을 넣어 전체 snapshot inputSha256와 기존 action_digest에 결속한다. 경로는 고정이며 외부 URI를 해석하지 않는다.

승인 요청·승인 dispatch(재호출 포함)·delivery·claim에서 frozen binding과 현재 registry/policy/권한을 비교한다. 마지막 registry SHARE 잠금은 호출자 transaction 종료까지 유지한다. prepare replay도 현재 권한을 다시 검사한다. 설정 제거는 이미 등록된 frozen 입력의 우회가 아니며 거부된다. 설정 활성화 후 과거 미결속 입력도 거부한다. policy 미설정의 기존 kernel-only 입력은 registry 실행 승인을 의미하지 않는다.

공개 HTTP 설정/운영 배포 연결은 이번 범위 밖이며 trusted worker가 같은 Database policy를 일관되게 전달해야 한다. registry 결속은 실행 permit 자체가 아니므로 기존 Run/Node/fence/quorum과 승인 digest 검사는 유지한다.

## 검증과 인계

사용자 disposable PG16에서 각 파일을 순차 실행했다. 명령은 `python -m pytest <아래 파일> -q --tb=short --junitxml=<private report>`이며 모두 exit0, skip0, failure0이다.

| 파일 | passed |
|---|---:|
| tests/integration/test_model_registry_runtime.py | 22 |
| tests/integration/test_model_runtime.py | 23 |
| tests/integration/test_model_remote_runtime.py | 6 |
| tests/integration/test_approvals.py | 25 |
| tests/integration/test_model_retry.py | 8 |

PG 합계84건. 신규22건은 local/remote 각각 정상 launch, 읽기 중 retirement, replay/승인/dispatch/claim/delivery 거부, policy 제거·변경, ID누락, 미결속 legacy replay 거부를 검사한다. 전송은 합성이며 실제 Node 프로세스 시험이 아니다. credentials는 증거에 기록하지 않는다.

오프라인: `python -m pytest tests/core/test_model_execution_registry.py tests/core/test_model_source.py tests/core/test_model_remote.py -q --tb=short` exit0,60passed. 신규 변조 시험에는 유효 WorkspaceId와 동일 helper의 정상 positive control을 두어 사전 schema 실패가 목표 검증으로 오인되지 않도록 했다. 총144건이며 전체 스위트 수치가 아니다. 기존53건 실행과 중복 합산하지 않는다.

각 Evidence/model-registry-binding/*registry-runtime-pg.json, test_model_registry_runtime-coord-pg.json, registry-runtime-offline.json에 base SHA·실제 코드 hash·JUnit hash·범위를 기록했다. check_docs exit0(518문서), check_ontology exit0. CI는 사용자 요청대로 조회 재시도 없음, 인증/결제 대기. image/prune/실장비 조치 없음.

다음 Claude: frozen registry 삭제/변조 방어, 현재 policy 전파, Run→Node/grants/Location/channel→registry 잠금 순서와 기존 승인/dispatch 경계 독립 검토. e89a415/8c347b7 검토와 이번 변경 검토를 구분한다. 다음 Codex: 검토 finding 반영 및 운영자 policy 구성·공개 서비스 연결 범위 검토. 독립 review/CI/운영 인수는 미완이며 이번 trusted worker 구현 성공으로 대체하지 않는다. Claude816346c가 마지막 확인 tip으로 R5 수정본은 아직 수신하지 못했다.

## 후속 입력: Claude d59b8a6 수신

Claude의 8c347b7/e89a415 독립 소스 검토 sound/finding 없음 수신 및 실제 History 원문 확인. 해당 검토는 앞선 원격 orchestration과 CAS fixture에 한정되며 이번 registry 실행 연결의 독립 검토가 아니다. CAS fixture의 disable/expiry UPDATE는 version 미증가로 23514를 발생시켜 제품 무커밋/claim 거부 단언 이전에 멈췄고, DSN 부재에서는 skip이었다. 제약은 정상 작동했고 e89a415는 test/docs/evidence만 교정했다. 사용자의 migration0005 소스 독립 대조 보고도 수신했다.

별도 detached d59b8a6에서 `pytest --noconftest tests/test_docker_diag.py tests/test_check_kernel_docker_hygiene.py tests/test_vf_docker.py -q -k 'not test_prune_removes_old_exited_residue_but_spares_a_recent_one and not test_prune_never_force_removes_a_running_concurrent_container'`: exit0,22passed/2deselected. 제외한 두 건은 실제 Docker/prune라 실행하지 않았다. 작성자24passed 보고와 합산하지 않는다.

R5-01: cleanup_owned는 결과 기반 docker_diag.run을 사용하고 pytest outcome helper 재사용을 제거했다. 본문 AssertionError 유지·모든 자원 시도·미정리 관측·KeyboardInterrupt 전파 회귀가 통과했다. 넓은 Exception 관용은 이 finally cleanup에 한정하며 오류를 기록한다. 사전 prune의 프로그래밍 오류 표면화와 구분한다.

R5-02: 실제 source_files499개에 tools/docker_diag.py·check_kernel_docker.py와 tests/vf_docker.py가 포함됐다. 이 세 파일만 임시 격리 복사한 뒤 python -I에서 import 성공(exit0), 호스트 원본 tools를 경로에 넣지 않았다. Docker build 실행은 아니다. 새 소스/오프라인 blocker 미관측, 사용자가 진행 중이라고 한 독립24건 결과를 기다려 최종 착지 판정한다. 원인 관련 과거 문서의 호스트 압박 인과 표현은 기존 정본의 상관관계 판정을 대체하지 않는다.

## 최종 Claude 착지 판정 및 현재 인계

사용자 clean d59b8a6에서 정확한 세 파일(test_docker_diag/test_check_kernel_docker_hygiene/test_vf_docker)24passed/0failed, 실제Docker포함 독립 결과 수신. 작성자24와 Codex22/2제외를 합산하지 않는다. R2-01/R2-02/R3-01/R2-03/R4-01/R5-01/R5-02 기존 blocker 해소 판정으로 전체 Claude 브랜치를 e2908a5 기반에 병합한다. 조각 추출 없음. 병합 후보에서도 오프라인22passed/2deselected(exit0), 문서521/ontology 통과. 새 blocker 미관측.

제품 registry 실행 연결 구현 SHA e2908a5를 작업 branch와 integration에 push(exit0)했다. Claude merge는 개발 기준선 반영이며 운영 인수가 아니다. 최신 image lane 미검증6건과 business-kernel-role DB role 거부 단언 미검증을 그대로 유지한다. 이 외부 환경 시험을 진단/cleanup 브랜치 착지 조건으로 걸지 않는다. 호스트 NTSTATUS 실패는 관측 사실이지만 OneDrive/handle 압박의 인과 확정은 아니며 기존 정본의 상관관계 판정을 유지한다.

다음 Codex: e2908a5 registry 실행 연결 독립 검토 수신·finding 대응, 운영자 policy 설정의 서비스 진입 경계 검토. 다음 Claude: 이번 registry 변경 독립 검토(이전 8c/e89 sound와 별도). 외부 대기4건/CI/실장비는 계속 미완이며 승인 요청을 반복하지 않는다.

## 최종 push·sync

registry 구현 e2908a5, Claude 전체 병합 b378785, 공유판 외부 이력 보존187269c. 모두 작업 branch와 integration 일반 push exit0. Obsidian 최초 check는 Claude 작업판 외부편집으로 exit1/쓰기0; 원문과 hash를 Evidence/claude-d59-landing에 보존하고 현재 인계와 통합했다. 동일 외부 hash 재확인 후 변경17파일만 check→apply→check,17exported/0pending/0conflict(exit0), source187269c. CI조회 재시도0/image lane실행0. 현재 작업트리 clean, 미완사항과 다음 담당은 위 인계를 따른다.
