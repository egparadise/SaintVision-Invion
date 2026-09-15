---
doc_id: "CONTRACT-PROVISIONING-INTEGRITY-001"
title: "Codex 계정 준비와 실행 권한 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T14:19:43+09:00"
source_of_truth: "Git"
---

# 계정 준비와 실행 권한

ADR-068, owner Codex/reviewer Claude. S01-BE/DB·S03-BE·S12-BE 후속. [[Codex 계정과 실행 커널 통합 계약]]과 [[Codex 실제 실행 결과 조회 계약]]의 운영자 연결 도구다.

## 명시적 입력과 경계

`tools/provision_account.py`는 `--tenant --project --user --issuer --sub --grant`를 모두 받는다. grant는 request / approve / request-and-approve 중 명시한 하나다. `--check`는 read-only transaction 진단, `--apply --reason <운영 근거>`는 현재 값을 다시 잠그고 한 transaction에서 필요한 링크·grant·불변 감사를 넣는다. DSN은 기본 INV_PROVISION_DSN 환경 변수에서만 읽고 argv/결과에 쓰지 않는다. 운영 DB 소유 권한은 웹 앱과 분리한다.

기존 active 사용자와 정확히 같은 OIDC issuer/sub, active Project·현재 역할, 별도 준비된 recovery epoch가 필요하다. 외부 subject나 이미 설정된 mapping·grant scope·비활성 link·role·epoch를 바꾸지 않는다. 충돌은 거부한다. 현재 역할이 요청/승인을 허용하지 않으면 해당 grant를 넣지 않는다. 동일 요청의 재실행은 변경·추가 감사 0이며 동시 호출은 tenant 단위 transaction advisory lock과 현재 DB row lock으로 직렬화한다. 감사 삽입까지 실패하면 그 호출의 모든 연결을 rollback한다. 불확실한 DB commit 응답은 같은 입력으로 check 후 재실행해 실제 존재를 확인한다.

이 명령은 실제 사람을 검증하는 IdP 등록, 계정 생성, Workspace 파일 준비, Node 설치, 자원 제공, 실행 admission을 대신하지 않는다. 결과 `linked=true`는 지정 계정 연결과 grant 정합성만 뜻하며 `executionReady=false`를 유지한다. 개발자의 현재 포괄 승인으로 운영 계정을 임의 생성/교체하지 않는다. 사용자/운영자가 확정한 계정 정보와 대상 범위가 있어야 운영 apply를 실행한다.

## migration과 결과 경계

이미 게시된 0026_subject_kernel_link, 0028_result_readiness_merge, Claude 0028_subject_kernel_link/0029_run_outputs를 삭제·개명하지 않고 0030_provisioning_integrity에서 병합한다. 마지막 subject 검사에는 현재 transaction tenant, active 계정, 정확한 external_subject, enabled mapping을 모두 요구한다. `inv.account_provisioning_events`는 DB operator·epoch·명시한 범위·실제 새 링크·근거를 원자 기록하며 앱/kernel runtime에는 쓰기 권한이 없다.

독립 raw output resolver에는 현재 kernel project grant와 immutable Evidence 교집합이 없어 0030에서 inv_app EXECUTE를 회수한다. 제품의 다운로드는 기존 `/v1/runs/{runId}/artifacts`와 `/artifacts/content?path=...`, 상태/로그는 `/result`, `/logs`, `/attempts`다. public Run 존재 여부나 CP 로컬 CLI readiness를 실제 실행의 기준으로 사용하지 않는다. 과거 Claude raw `/outputs` 제안은 통합 route로 공개하지 않는다.

## 운영자 절차

확정된 IdP 계정으로 업무 API에서 생성한 tenant/project/user와 현재 멤버십을 준비한다. DB 소유 계정 DSN을 지정 환경 변수로 제공한 후 다음 형식으로 먼저 진단한다(꺾쇠 항목은 실제 확인값으로 치환하며 예제를 실행하지 않는다).

```text
python tools/provision_account.py --check --tenant <tenant-uuid> --project <prj-id> --user <usr-id> --issuer <https-issuer> --sub <oidc-sub> --grant request
```

같은 입력의 blockers와 missing을 확인한 운영 범위에만 --apply 및 --reason을 사용한다. 종료 코드는 0=지정 연결 충족, 1=진단 결과 미충족, 2=거부/DB 실패다. 계정/권한 충돌 또는 disabled 항목은 별도 검토 대상이며 이 명령으로 풀지 않는다. 이후 Workspace readiness·실제 Node profile·자원 제공·새 승인/admission을 확인한다. 설치한 worker의 private key/토큰은 보고에 넣지 않는다.
