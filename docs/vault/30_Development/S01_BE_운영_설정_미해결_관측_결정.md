---
doc_id: "ADR-S01-BE-OPERATIONAL-CONFIG-READINESS-001"
title: "S01-BE 운영 설정 미해결 관측 결정"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T08:35:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S01-BE", "configuration", "operator", "readiness", "contract", "decision"]
---

# S01-BE 운영 설정 미해결 관측 결정

## 결정

**(a) 운영 factory에 인증된 운영자 전용 read-only route를 둔다.** `GET /v1/operations/configuration-readiness`는 운영 정본 `inv.app.create_configured_app`이 `saintvision.config.unresolved_s01_settings`를 명시 주입해 만든다. `/readyz`는 프로세스·identity·DB 준비 상태라는 기존 의미를 유지한다. (b)처럼 사용자 입력 미완료를 readiness에 합치면 정상 프로세스를 배포 실패로 만들고, (c) 별도 프로세스는 인증·TLS·설정 정본을 하나 더 만들어 drift를 늘리므로 기각한다.

## 공개 계약과 권한

Bearer 검증 후 현재 tenant의 `inv.operator_grants`를 `containment.operator()`로 확인한다. 토큰 누락/무효는 기존 `AUTH-0050`, operator grant 부재는 `AUTH-0062/403`, DB·provider 불가는 `SYS-0001/503` ProblemDetails다. 정상 관측은 미해결 여부와 무관하게 HTTP 200이며 `Boundary`가 `Cache-Control: no-store`를 붙인다.

```json
{
  "status": "blocked",
  "unresolvedSettings": ["INV_NODE_MTLS_CA_BUNDLE", "INV_OBJECT_STORE_ENDPOINT"]
}
```

`ConfigurationReadinessView`는 `additionalProperties:false`, `status=ready|blocked`, `unresolvedSettings`의 항목을 위 두 정본 이름으로 제한한다. 목록은 정렬되고 중복이 없으며 **이름만** 반환한다. 값·경로·endpoint·인증서 내용·DSN은 응답과 오류에 들어가지 않는다. 두 값이 모두 존재하면 `{status:"ready", unresolvedSettings:[]}`이다. 공개 HTTP/ProblemDetails의 기존 코드는 바꾸지 않는다.

목록은 요청 시점의 process environment를 직접 평가한 현재 관측이며 저장된 snapshot이 아니므로 `observedAt` freshness 필드를 추가하지 않는다.

## 결속과 시험

- route coverage: `/v1/operations/configuration-readiness`와 `/readyz`가 서로 별도 경로로 등록됨을 고정한다.
- serving anchor: route가 반환 직전 `validate_contract("ConfigurationReadinessView", response)`를 반드시 지난다.
- 공유 fixture와 생성 Python/TypeScript/Go 및 Node schema를 단일 `core.schema.json`에서 재생성한다.
- PG-free 시험은 fixture strictness, 미해결/해결 응답, 비밀값 미노출, 401, 403, provider 미구성 503, serving anchor를 검증한다. DB 역할의 실제 RLS/권한은 바꾸지 않으며 migration도 없다.

## 후속 정정

- PR #125 체크리스트 §7: `/v1/health.unresolvedSettings`를 운영 증거로 쓰지 말고 이 route에 Bearer를 보내 `status`와 이름 목록을 확인하도록 고친다. U2·U3·U6 해소는 해당 이름이 목록에서 사라지는 것으로 판정한다.
- PR #122 `s01_readiness_preflight`: 익명 별도 `--health-url` 설명을 폐기하고 `--settings-url`(기본값 `<base-url>/v1/operations/configuration-readiness`)로 바꾸며 동일 Bearer를 사용한다. U2·U3·U6은 이 응답이 없거나 401/403/503이면 fail-closed `BLOCKED`다. PR #122/#125 브랜치는 이 카드에서 직접 수정하지 않고 각 소유 브랜치의 후속 commit으로 반영한다.

S01-BE는 계속 `in_progress`다. 이 route는 사용자 입력을 관측할 뿐 U2·U3·U6을 채우거나 AC-01 완료를 주장하지 않는다.
