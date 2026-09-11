---
doc_id: "REVIEW-CLAUDE-HANDOFF-20260911"
title: "Claude 잔여보고 Codex 독립검토"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T15:47:11+09:00"
source_of_truth: "Git"
---

# Claude 보고와 최신 적용 코드의 교차 검토

검토 대상은 Claude 4361584·529ac8b 및 [[Claude_통합코드_독립검토]], Codex 기준은 5de316d다. Claude 작성 코드에 대한 Codex 검토이며 아래 Codex 보완의 독립 승인은 별도로 대기한다. CI와 물리 원격 인수는 미완료다.

## tenant 누수 판정

`0026_subject_kernel_link` 원본에 session tenant 바인딩이 없는 지적은 맞다. 새 도구 `tools/check_subject_tenant.py`가 폐기 가능한 DB를 만들고 실제 NOSUPERUSER/NOBYPASSRLS 로그인 역할(inv_app만 상속)로 같은 계정에 대한 정상/타 tenant/미설정/빈 scope를 읽었다. 0026까지 적용하면 네 경우 모두 true로 누수된다. 후속 0028_result_readiness_merge, 0030_provisioning_integrity, 0031_resource_offer_integrity를 적용하면 정상만 true, 나머지는 false였다. 현재 정의는 정지 사용자·subject 불일치·비활성 매핑도 false다.

이는 파일 안 문자열 개수와 다른 검증이다. 세 후속 revision의 `pg_get_functiondef` SHA-256은 모두 fcaa51cd4eaa3a069b750440f3ae10c84d9cdba3b64b37f379ddafcd9d162777이고, 0026은 a0215f8ede00159453715a8da985d6712a2947343536e47b6d52c4ad017d5d59다. 15:39:40 KST의 로컬 재현 1개가 통과했다. 최종 코드·원본 공개 Evidence는 후속 검증보고에 고정한다. 이 결과는 운영 DB 적용 상태 확인이나 모든 definer의 포괄적 감사가 아니다. session tenant는 검증된 JWT에서 업무 서비스가 설정하는 경계다.

따라서 '최신 적용 함수에도 그 누수가 남았다'는 판정은 이번 재현에서 확인되지 않았다. 이미 전달한 migration 원본을 고쳐 쓰지 않고 후속 guard와 재현 시험을 유지한다. 0026까지만 적용한 DB는 안전한 배포 대상으로 인정하지 않는다. 배포는 통합 head upgrade와 검사·검토가 선행해야 한다.

## 결과 정본과 migration 보존

Claude의 중복 결과 서비스/라우터 제거 방향을 수용했다. 현재 합성 통합 앱이 삭제되는 results router를 직접 import하고 있었으므로 readiness router로 전환한다. 옛 업무 결과 시험은 새 readiness 시험으로 정리하고 실제 kernel ResultView의 HTTP/Node/receipt/Evidence/해시/권한 시험을 유지한다. 업무 단독 앱이 kernel 결과 URL을 제공하지 않는지도 실제 HTTP로 검증한다.

반면 0029_run_outputs 삭제와 0030_apply_resource_offer의 부모 변경은 수용하지 않는다. 이 revision은 이미 PR #21·#22의 commit 및 upgrade 검증에 포함됐고 0030_provisioning_integrity가 부모로 참조한다. 현재 작업은 원본 0026/0028/0029/0030/0031_resource 파일을 그대로 보존한다. 대체 다운로드 definer의 inv_app EXECUTE는 기존 0030에서 회수돼 있다. public.artifacts 데이터 삭제는 이번 범위가 아니며 별도 소비자/보존 정책 검토가 필요하다.

## 신규 0031 입력 조회의 보완

Claude의 workspace_input_state는 tenant 바인딩과 고정 search_path가 있다. 그러나 과거 입력도 계속 prepared로 답하고, Run ID 문자열로 최신을 고르며, 동일 workspace ID의 다른 project 입력까지 선택할 수 있었다. 0032_workspace_readiness_merge는 두 공개 0031을 합치고 다음 조건으로 함수를 교체한다.

- 현재 recovery epoch 및 public Workspace와 동일한 tenant/project.
- 첫 실행은 attempt 0의 대기 상태, 복원은 현재 source_attempt에 대응하는 대기 상태.
- created_at 기준 최신 입력 선택. 취소/종료 또는 이전 epoch 입력을 준비 완료로 표시하지 않음.
- 없는 입력은 null과 해결 주체를 제공하며 입력 크기 상한도 항상 제공.

기존 별도 kernel_request_permission을 유지하므로 현재 통합 checks 배열은 7개다. '6개'를 UI에 고정하지 말고 check ID/배열을 표시한다. executable=false·admissionRequired=true는 유지하며 준비 진단이 실행 승인을 대신하지 않는다. 새 입력 조회/기존 readiness와 tenant 도구를 합친 로컬 집중 시험 20개가 15:45:02 KST에 통과했다. 복원 입력 및 업무 단독 앱의 후속 시험은 최종 보고로 고정한다.

## migration 도구·PR·후속 담당

Claude의 migration head 동적 계산과 src 경로 수정은 수용돼 있으며 현재 코드에도 존재한다. 기존 16개 prior에 두 0031을 추가한 18개 공개 경로의 실제 upgrade/replay를 최종 로컬 회귀로 검증한다. 경로 수는 CI 합격 수나 물리 PC 수가 아니다.

GitHub 조회상 #13·15·16·17·18·20은 이미 merged다. #11 head는 main 조상이고 #12 head는 이미 포함된 #13 head와 tree가 정확히 같은 후속 merge commit이다. 기존 사용자 승인 아래 중복 draft #11·#12를 closed로 정리했으며 새 merge로 표시하지 않았다. branch/worktree는 보존했다. #19·#21·#22의 미반영 변경과 독립 검토·CI는 별도다. 최종 PR 개수/합류 조건은 기계 조회 Evidence에 기록한다.

다음 owner: Codex는 실제 원격 설치 확인·7개 시험 및 리뷰 보완, Claude는 이번 보완 독립 검토·실제 운영 계정/Workspace 적용과 복원 리허설, Gemini는 정본 경로·7개 준비 진단·실제 관측 표시와 선행 완료 후 브라우저 인수다. 운영 로그인 코드의 구현 보고와 현재 pilot의 webAuthenticationConfigured=false는 서로 다른 배포 상태다.
