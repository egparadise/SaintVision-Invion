---
doc_id: "DESIGN-S12-BE-RELEASE-MANIFEST-READ-20261001"
title: "S12-BE release manifest 읽기 route와 서명·수락 쓰기 경계 — 읽기는 구현했고 쓰기는 Codex 계약을 요청한다 (카드 182)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-01T18:26:20+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7e670d77"
task_ids: ["S12-BE", "S12-FE"]
tags: ["s12", "release-manifest", "acceptance", "route", "read-only", "security-boundary", "claude"]
---

# S12-BE release manifest 읽기 route와 쓰기 경계

## 0. 이 메모가 답하는 것

재산정 v1.8은 `S12-FE`를 50에 두고 사유를 **"서버 route 부재로 `ReleaseManifest.operatorSignOff=false` 유지"**(DEF-S12)로 적었다. 표·서비스·시험은 저장소에 있었고 **그것을 내보내는 HTTP route가 없었다** — 그래서 화면은 "사람이 이 release를 승인했는가"를 물을 데가 없어 그 필드를 거짓으로 **하드코딩**했다.

카드 182는 **읽기만** 구현했다. 이 메모는 (1) 읽기에서 내린 결정과 그 이유, (2) **쓰기를 왜 이 카드에서 하지 않았는지**, (3) Codex에게 요청하는 계약을 적는다.

## 1. 구현한 것 — 읽기 두 개

| route | 응답 | 비고 |
|---|---|---|
| `GET /v1/release-manifests` | `ReleaseManifestPageResponse` | tenant의 release 목록, `release_id` 역순, 기본 50·상한 200 |
| `GET /v1/release-manifests/{release_id}` | `ReleaseManifestDetailResponse` | 그 release와 **기록된 수락 전부** |

### 1-1. `operatorSignOff`는 **계산값**이고 저장값이 아니다

`release_manifests`에는 그런 열이 없다. `pilot.operator_sign_off`가 수락 행에서 계산하며 **참이 되는 길은 하나**다 — `outcome='accepted'`이고 `accepted_manifest_sha256`이 **이 manifest의 해시와 같을 때**.

거짓으로 남는 세 경우가 각각 다른 사실이다.

1. **수락 행이 없다** — 아무도 보지 않았다.
2. **`conditional` 또는 `rejected`** — 누군가 보았고 승인하지 않았다. 표가 이미 "조건부인데 제약 목록이 비면" 거절하므로(`conditional_requires_limitations`), 읽기가 조건부를 승인으로 읽으면 그 제약이 지키려던 구별을 버리는 것이 된다.
3. **`accepted`인데 해시가 다르다** — 같은 이름의 **다르게 구성된** release를 승인했다. 해시를 고정하는 이유가 바로 그것이고, 응답의 `manifestMatches`가 그것을 말한다.

**이 route는 `operatorSignOff`를 참으로 만들 수 없다.** `accepted_by_user_id`가 `users`로 가는 실제 외래키이므로 읽은 모든 행은 사람을 위해 쓰인 것이다.

### 1-2. tenant scope이고 project scope이 아니다

`release_manifests`·`acceptance_records`에는 `tenant_id`가 있고 **`project_id`가 없다** — release는 배포 전체의 속성이고 그 안의 한 project의 것이 아니다. 그래서 범위는 검증된 principal의 tenant이고, `get_session`의 `SET LOCAL`이 요청 트랜잭션 안에서 적용하며 **모든 질의가 `tenant_id`를 명시**한다(RLS 하나에만 의존하지 않는다).

**다른 tenant의 release는 403이 아니라 404다.** "있지만 당신 것이 아니다"는 caller가 물을 자격이 없는 질문에 답하는 것이다.

### 1-3. 사람을 내보내지 않는다

응답에 `accepted_by_user_id`와 `notes`가 **없다**. 전자는 "시스템이 스스로 서명할 수 없게" 하려고 있는 감사 열이고 후자는 자유 서식이다. `RunRecordResponse`가 "식별자와 digest만, 사람·자유 서식 없음"이라는 규칙을 먼저 세웠고 이쪽이 그것을 따른다. 시험이 **키 집합을 고정**해서 serializer가 나중에 무엇을 더 넣어도 조용히 통과하지 못한다.

## 2. 쓰기를 하지 않은 이유 — 보안 경계다

서명·수락 **생성**은 이 카드의 범위 밖이다. 이유를 추측이 아니라 코드에서 적는다.

| 쓰기가 결정해야 하는 것 | 왜 읽기 카드가 결정할 수 없는가 |
|---|---|
| **사람의 결정이라는 증거가 HTTP에서 무엇인가** | `accepted_by_user_id`가 `users` 외래키인 것은 "시스템이 스스로 서명하지 못한다"는 **DB 수준의** 진술이다. bearer 토큰 하나로 그 행을 쓰는 route는 그 진술을 HTTP 수준에서 **무효화**한다 — 서비스 계정 토큰이 곧 사람의 서명이 된다 |
| **어떤 승인·권한이 필요한가** | `require_project_access`는 project 등급이고 release는 project가 없다. tenant 전역 운영 권한 등급이 **아직 없다** |
| **재전송(멱등)과 수정 금지** | `uq_acceptance_records_release_criterion`이 release×기준 당 하나를 보장하지만, 같은 기준에 **다른 결정**을 다시 보내는 요청을 409로 거절할지 갱신할지는 감사 의미가 걸린 결정이다 |
| **해시 고정의 방향** | `record_acceptance`는 해시를 **release에서 읽고** 받지 않는다. 쓰기 route가 그것을 받기 시작하면 caller가 "무엇을 승인했는지"를 고를 수 있게 된다 |

## 3. Codex에게 요청하는 계약

읽기는 착지해도 `operatorSignOff`가 거짓으로 남는다 — **쓰기가 없으면 수락 행이 생기지 않는다.** 그래서 다음 계약을 요청한다.

1. **사람의 결정을 HTTP에서 증명하는 방식.** 토큰만으로는 부족하다는 전제에서, 어떤 추가 증거(재인증, 승인 ID, 서명된 승인 봉투 중 무엇)를 요구할지.
2. **tenant 전역 운영 권한 등급의 정의.** release 수락을 누가 할 수 있는가 — 역할 이름과, 정지된 사용자를 어떻게 배제하는가.
3. **멱등과 재결정 규칙.** 같은 `(release, 기준)`에 두 번째 결정이 오면 409인지, 이전 결정을 감사와 함께 대체하는지.
4. **해시를 받을지 읽을지.** 받는다면 불일치를 422로 거절하는 규칙까지.
5. **감사 사건 이름과 payload.** 수락이 남길 사건, 그리고 거절된 시도가 남길 사건.

그 계약이 오면 Claude가 구현하고 Codex가 검토한다(AGENTS.md의 고난도 보안 변경 규칙).

## 4. 이 카드가 확인하지 않은 것

- **실제 화면과 연결해 보지 않았다.** `apps/web`의 `ReleaseManifest` 타입은 FE 지역 타입이고 `imageDigest`·`targetClusters`·`smokePassedRatio` 같은 **DB에 없는 필드**를 갖는다. 이 route는 **표가 기록한 것만** 내보낸다 — FE가 그 모양을 쓰려면 별도 카드가 필요하고, 이 route로 `operatorSignOff`를 **묻는 것**은 지금 가능하다.
- **점수를 올리지 않았다.** `S12-FE`의 50은 화면 쪽 판정이고, 이 카드는 서버 route 부재라는 **사유 하나**를 없앴을 뿐이다. 재산정은 별도 카드가 다시 센다.
- **쓰기 경로를 설계하지 않았다.** §3은 요청이고 설계가 아니다.
- **`manifestMatches`는 현재 writer로는 항상 참이다.** `record_acceptance`가 해시를 release에서 읽기 때문이다. 그래도 읽기가 비교하는 이유는 그 열이 자기 사본을 갖기 때문이고, 시험은 그 상태를 **열을 직접 써서** 만든다(현재 writer로 만들 수 없음을 시험 docstring에 적었다).
