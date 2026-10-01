---
doc_id: "DESIGN-S12-BE-RELEASE-MANIFEST-READ-20261001"
title: "S12-BE release manifest 읽기 route와 서명·수락 쓰기 경계 — operatorSignOff는 외래키로 증명되지 않아 계약에서 false로 고정하고, 사람 확인 수와 원시 수락 수를 두 필드로 분리했다(코디네이터 결정), 쓰기는 Codex 계약 요청 (카드 182, r3)"
version: "1.3.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-01T20:30:20+09:00"
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

### 1-1. `operatorSignOff`는 **계약에서 `false`로 고정**된다 (r2 정정, r3 이름 결정)

**v1.0의 이 절은 틀렸다.** 그때는 `operatorSignOff`를 수락 행에서 계산하고 `outcome='accepted'`에 해시가 맞으면 **참**으로 냈다. 근거로 "`accepted_by_user_id`가 `users`로 가는 실제 외래키이므로 시스템은 스스로 서명할 수 없다"를 적었다.

**독립 검토(Codex, `#280` r1 F1)가 그것을 측정해 반증했다.** `users`는 사람과 서비스를 구분하지 않는다 — `identity.py`가 임의의 `external_subject`로 Principal을 만들고, 외래키는 **참조된 행이 존재한다는 것만** 증명한다. `external_subject`가 `svc:release-bot`인 사용자로 `record_acceptance(accepted)`를 쓰면 **`operatorSignOff`가 참이 되었다.** 존재 증명을 사람 증명으로 읽은 것이고, 그것이 내가 다른 PR에서 계속 지적해 온 바로 그 형태다 — **기구의 모양에서 성질을 단언한 것.**

그래서 이제:

| 필드 | 값 | 뜻 |
|---|---|---|
| `operatorSignOff` | **`Literal[False]`** | 이 읽기 표면은 참을 **낼 수 없다**. docstring의 약속이 아니라 **계약**이 거부한다 |
| `operatorSignOffBlockedBy` | `"release-acceptance-prerequisites-unavailable"` | 왜 거짓인지. 카드 187의 코드만으로는 부족하며, 검증된 fresh-auth/step-up 공급과 authoritative target/Evidence resolver가 모두 결속돼야 한다. 어느 하나라도 없으면 이 값이다 |
| `requiredDistinctOperatorCount` | **`Literal[2]`** | 쓰기 계약(`#282`, 카드 184)의 정족수 |
| `confirmedOperatorCount` | **`Literal[0]`** | **사람 확인(`#282`의 human attestation)된 서로 다른 운영자 수.** 그 구현이 없으므로 이 표면에서는 0 고정이다. "수락이 없다"가 아니라 "여기 어떤 결정도 사람에게 귀속되지 않았다"는 뜻이다 |
| `matchingAcceptedUserCount` | 정수(≥0) | **원시 기록**: 해시가 맞는 `accepted` 행의 서로 다른 사용자 id 수. 서비스 주체가 그중 하나일 수 있고, **그래서 이름이 다른 필드**다 |

**이름은 코디네이터가 2026-10-01에 정했다**(`#282`에도 같은 결정이 전달됐다). r2에서 나는 원시 수를 `confirmedOperatorCount`에 담았고, 그러면 **서비스 계정이 올릴 수 있는 수에 "confirmed"라는 말이 붙는다** — F1에서 고친 것과 같은 종류의 과잉 주장이다. 이제 `confirmedOperatorCount`는 사람 확인의 자리로 비워 두고(0 고정), 기록된 사실은 아무 주장도 하지 않는 이름으로 나간다.

이 필드들은 **release 전체 읽기 범위**다. `#282`의 proposal/decision 응답은
`proposalConfirmationCount`·`decisionConfirmationCount`·`decisionSignOff`로 분리한다.
따라서 release의 `confirmedOperatorCount`를 proposal 투표 수로 읽거나, release의
`operatorSignOff`를 개별 criterion decision의 quorum 값으로 읽어서는 안 된다.

`matchingAcceptedUserCount`가 `0`으로 남는 세 경우는 그대로 각각 다른 사실이다.

1. **수락 행이 없다** — 아무도 보지 않았다.
2. **`conditional` 또는 `rejected`** — 누군가 보았고 승인하지 않았다. 표가 이미 "조건부인데 제약 목록이 비면" 거절하므로(`conditional_requires_limitations`), 읽기가 조건부를 승인으로 읽으면 그 제약이 지키려던 구별을 버리는 것이 된다.
3. **`accepted`인데 해시가 다르다** — 같은 이름의 **다르게 구성된** release를 승인했다. 해시를 고정하는 이유가 바로 그것이고, 응답의 `manifestMatches`가 그것을 말한다.

**이 route는 `operatorSignOff`를 참으로, `confirmedOperatorCount`를 0 이상으로 만들 수 없다** — 이제는 계약이 둘 다 거부하기 때문이고, 외래키 때문이 아니다. 실 PG 시험이 **서비스 주체로 `accepted` 행을 써도 `operatorSignOff` 거짓 · `confirmedOperatorCount` 0 · `matchingAcceptedUserCount` 1**임을 고정한다(`test_a_service_principal_cannot_produce_operator_sign_off`). **이 시험이 두 수를 같은 수의 두 이름이 아니게 만드는 자리다.**

### 1-1-bis. 목록이 **없는 것**은 빈 목록이 아니다 (Codex `#281` 계약 r2)

`ReleaseManifestPageResponse.items`가 `default_factory=list`였다. 그래서 **공개 schema에 `required`가 하나도 없었고**, 거기서 생성한 TypeScript가 `items?:`가 되었다 — FE의 strict guard는 키 누락을 거부하므로 **계약이 클라이언트가 거부할 payload를 허용**하고 있었다(서버는 그런 payload를 보낸 적이 없다).

이 응답들의 목록 네 개(`components`·`knownLimitations`·`acceptances`·`items`)는 **서비스가 항상 보낸다.** 그러므로 전부 **required**로 바꿨다 — 빈 페이지는 `items: []`이고, `items`가 없는 것은 **깨진 응답**이며 양쪽이 그렇게 말해야 한다. `nextCursor`도 같은 이유로 required nullable이다: `null`("마지막 페이지")과 키 부재("이 응답은 그 말을 하지 않는다")는 다른 진술이다.

시험이 다섯 모델의 **required 집합을 통째로** 적어 두고(선택 필드 0개), **생성된 contract 파일**도 같은 집합을 요구하는지 따로 읽는다. 전자는 source를, 후자는 FE가 실제로 읽는 파일을 잡는다.

### 1-2. tenant scope이고 project scope이 아니다

`release_manifests`·`acceptance_records`에는 `tenant_id`가 있고 **`project_id`가 없다** — release는 배포 전체의 속성이고 그 안의 한 project의 것이 아니다. 그래서 범위는 검증된 principal의 tenant이고, `get_session`의 `SET LOCAL`이 요청 트랜잭션 안에서 적용하며 **모든 질의가 `tenant_id`를 명시**한다(RLS 하나에만 의존하지 않는다). 그 명시 조건은 **compile된 SQL로 단언**한다(`release_page_query`·`release_detail_query`·`acceptances_query`) — RLS가 같은 행을 막기 때문에 조건 하나를 지워도 교차 tenant 시험이 녹색으로 남았고(`#280` r1 F2), **시험이 볼 수 없는 층은 실수로 지워질 수 있는 층**이다.

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
3-bis. **사람과 서비스 주체의 구별.** 지금 `users`에는 그 구별이 없다(`identity.py`). `operatorSignOff`가 언제든 참이 되려면 그 구별이 스키마나 attestation에 있어야 한다 — 이것이 F1이 드러낸 가장 중요한 공백이다.
4. **해시를 받을지 읽을지.** 받는다면 불일치를 422로 거절하는 규칙까지.
5. **감사 사건 이름과 payload.** 수락이 남길 사건, 그리고 거절된 시도가 남길 사건.

그 계약이 오면 Claude가 구현하고 Codex가 검토한다(AGENTS.md의 고난도 보안 변경 규칙).

## 4. 이 카드가 확인하지 않은 것

- **실제 화면과 연결해 보지 않았다.** `apps/web`의 `ReleaseManifest` 타입은 FE 지역 타입이고 `imageDigest`·`targetClusters`·`smokePassedRatio` 같은 **DB에 없는 필드**를 갖는다. 이 route는 **표가 기록한 것만** 내보낸다 — FE가 그 모양을 쓰려면 별도 카드가 필요하고, 이 route로 `operatorSignOff`를 **묻는 것**은 지금 가능하다.
- **점수를 올리지 않았다.** `S12-FE`의 50은 화면 쪽 판정이고, 이 카드는 서버 route 부재라는 **사유 하나**를 없앴을 뿐이다. 재산정은 별도 카드가 다시 센다.
- **쓰기 경로를 설계하지 않았다.** §3은 요청이고 설계가 아니다.
- **`operatorSignOff`가 참이 될 수 있는 길을 설계하지 않았다.** 이 PR은 그것을 **거짓으로 고정**했을 뿐이고, 참이 되는 조건은 `#282`의 계약이다.
- **`manifestMatches`는 현재 writer로는 항상 참이다.** `record_acceptance`가 해시를 release에서 읽기 때문이다. 그래도 읽기가 비교하는 이유는 그 열이 자기 사본을 갖기 때문이고, 시험은 그 상태를 **열을 직접 써서** 만든다(현재 writer로 만들 수 없음을 시험 docstring에 적었다).
