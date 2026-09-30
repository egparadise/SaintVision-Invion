---
doc_id: "HIST-INTRANET-E2E-SMOKE-2026-09-30"
title: "사내망 종단 smoke (카드 155) — 신원 경로를 배포된 상태로 한 번 걸어 보는 도구. 인증서 검증을 끌 수단도, 이름 해석을 대체할 수단도 두지 않았고, hosts가 적용되지 않은 지금은 BLOCKED_EXTERNAL(hosts-not-applied)로 정직하게 멈춘다. 제어 평면 401 두 건은 실측 PASS다"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "user"
updated: "2026-09-30T09:35:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "6fc0428b"
task_ids: ["S01-BE"]
tags: ["history", "intranet", "smoke", "oidc", "card-155"]
---

# 사내망 종단 smoke (카드 155, 2026-09-30)

## 0. 무엇을 만들었고 무엇이 나왔나

`tools/intranet_e2e_smoke.py`. 신원 경로의 조각들은 각각 측정돼 있었지만, 그것이 **배포된 상태로 줄이 맞는지**는 다른 주장이다 — 이름이 해석되는지, 제시되는 인증서가 사내 CA가 낸 그것인지, discovery의 issuer가 제어 평면에 설정된 문자열과 같은지, 제어 평면이 거부해야 할 토큰을 거부하는지.

| 관측 | 결과 |
|---|---|
| `idpNameResolves` | **BLOCKED_EXTERNAL** `hosts-not-applied` |
| `idpHttpsVerified` | BLOCKED_EXTERNAL (이름 미해석) |
| `idpDiscoveryIssuer` | BLOCKED_EXTERNAL (이름 미해석) |
| `idpJwksSameOrigin` | BLOCKED_EXTERNAL (이름 미해석) |
| `passwordGrantRefused` | BLOCKED_EXTERNAL (이름 미해석) |
| `clientCredentialsRefused` | BLOCKED_EXTERNAL (이름 미해석) |
| **`controlPlaneRejectsBadToken`** | **MEASURED_PASS** — `401`, `AUTH-0050` |
| **`controlPlaneRejectsMissingToken`** | **MEASURED_PASS** — `401`, `AUTH-0050` |

전체 판정 **`BLOCKED_EXTERNAL`**, exit 3. 증거는 `docs/vault/30_Development/Evidence/intranet-e2e-smoke/`.

## 1. 하지 않기로 만든 세 가지

이것들은 약속이 아니라 **구조로 막았고, 그 사실 자체를 시험이 붙들고 있다.**

**인증서 검증을 끄는 수단이 없다.** flag가 아예 없고, 시험이 `--insecure`·`--no-verify`·`-k` 같은 option이 **존재하지 않음**을 단정한다. 끌 수 있는 smoke는 언젠가 그렇게 돌려지고, 그때의 PASS는 아무 의미가 없다.

**이름 해석을 대체하는 수단이 없다.** `--resolve`·`--address`·`--connect-to`가 없음을 시험이 단정한다. `idp.sv.lan`이 해석되지 않으면 답은 **`BLOCKED_EXTERNAL` `hosts-not-applied`** 이고, 주소로 조용히 우회하면 **운영자가 아직 해야 할 일 하나를 가리는** 셈이다. 다만 **측정된 실패가 미충족 전제보다 우선한다** — 인증서가 틀린 것은 결함이고 "아직 준비 안 됨"이 아니다. 그 우선순위를 시험으로 고정했다.

**실제 사용자의 password grant를 쓰지 않는다.** 그 grant는 portal client에서 의도적으로 꺼져 있고, 이 도구는 **존재할 수 없는 계정 이름**으로 거부를 확인한다 — 열쇠를 들지 않고 문이 잠겼는지 보는 방식이다.

여기서 이 검사가 의미를 갖게 하는 구분이 하나 있다. **`invalid_grant`는 틀린 거부다** — 그것은 이 client가 해당 grant를 *쓸 수 있다*는 뜻이고, 그 자체가 결함이다. 그래서 `unauthorized_client`·`invalid_client`·`unsupported_grant_type`처럼 **grant 수준의 거부만 PASS**로 본다. "200이 아니면 통과"로 만들었다면 **살아 있는 password grant를 잠긴 문으로 보고**했을 것이다. 그 시험을 부정 시험으로 넣었다.

## 2. 보고서가 무엇을 담지 않는가

주소·토큰·키가 들어가지 않는다. 그리고 그것을 **만드는 코드의 선의에 맡기지 않고 직렬화된 출력에서 검사**한다 — `assert_no_addresses`가 IPv4·IPv6 형태를 찾으면 파일을 쓰지 않는다.

그 과정에서 두 가지를 바꿨다.

- **인증서의 `notAfter`를 날짜로 정규화했다.** `Dec 28 23:05:05 2026 GMT`의 시각 부분이 검사기에 **IPv6로 읽힌다.** 검사기에 예외를 가르치는 대신 기록 형식을 `2026-12-28`로 바꿨다 — 읽는 사람에게도 만료일이 필요한 것이다.
- **제어 평면을 주소가 아니라 이름으로 적는다.** `loopback` / `non-loopback` + 포트. loopback 주소가 무엇을 누설하지는 않지만, "주소 0건"을 예외 없는 규칙으로 두는 편이 낫다.

ISO 시각도 콜론 때문에 IPv6로 읽히므로 검사 전에 제거한다. 그 경계들을 시험으로 고정했다(`2026-09-30T09:10:10+09:00`·SHA-256·호스트명은 조용하고, 실제 주소 5종은 반드시 걸린다).

## 3. 제어 평면 401은 어떤 제어 평면인가

**중요한 사실 하나**: 이 PC의 `8080`은 **다른 프로세스가 이미 점유**하고 있었다. 처음 그 포트로 측정했을 때 `401 AUTH-0050`이 돌아왔지만, 그것은 **내가 설정하지 않은 앱**의 응답이었다 — 그 앱의 issuer·JWKS 신뢰를 내가 모르므로 카드의 "그 issuer/JWKS trust를 넣었을 때"를 만족하지 않는다. 그 측정은 버렸다.

대신 **내가 설정한 인스턴스를 loopback의 다른 포트에 띄웠다**. 설정은 카드 152에서 세운 것과 같은 다섯 값이고, `jwks_file`은 검증된 https로 받아 둔 JWKS로 만든 신뢰 bundle이다. 그 인스턴스가 두 경우 모두 `401` `AUTH-0050`으로 답한다.

- 잘못된 bearer(`Bearer not.a.valid.token`) → **401**
- `Authorization` 없음 → **401**

보고서에 포트가 적히므로 어느 인스턴스였는지 감춰지지 않는다. 남의 프로세스는 건드리지 않았다(읽기만).

부수로 두 가지를 확인했다 — 제어 평면은 `jsonschema[format]`이 없으면 **오류 응답을 만들다가 500**이 된다(`date-time` 검증이 필수라서 problem 문서 자체가 만들어지지 않는다). 그리고 landed 앱은 `src`와 `services/control-plane/src` **둘 다** import 경로에 있어야 기동한다.

## 4. 왜 해석되는 환경에서 한 번 더 돌리지 않았나

(a)~(c)를 실측하려면 이름이 해석되는 환경이 필요하다. 지금 **어느 환경에서도 해석되지 않는다** — 이 PC의 hosts는 관리자 권한이 필요하고 노드의 `/etc/hosts`는 sudo가 필요하며, 둘 다 사용자 실행으로 남아 있다.

`--add-host`를 쓴 container 안에서 돌리는 방법은 있었지만 **하지 않았다.** 그 환경에는 git이 없어 `codeSha`가 비고, 이 도구는 40-hex commit이 아니면 증거를 쓰지 않는다. 우회해서 SHA를 만들어 넣는 것은 **측정하지 않은 것을 측정한 것처럼** 만드는 일이라, 측정하지 않는 편을 택했다. 대신 `runEnvironment`를 **필수 필드**로 만들어, 나중에 해석되는 환경에서 돌린 보고서를 이 보고서와 혼동할 수 없게 했다.

`(a)`~`(c)`의 판정 논리 자체는 부정 시험으로 덮여 있다 — issuer 불일치, 다른 origin의 `jwks_uri`, RS256 서명 키 없음, grant가 틀린 이유로 거부됨, 200으로 발급됨.

## 5. 검증 (실제 수행한 것만)

| 확인 | 결과 |
|---|---|
| 단위·부정 시험 | `tests/core/test_intranet_e2e_smoke.py` **60 passed** (네트워크 없이 실행) |
| 검증 무력화 수단 부재 | option 집합에 `--insecure`·`--no-verify`·`--skip-verify`·`-k`·`--allow-insecure` **없음**, `--ca-bundle`은 **필수** |
| 해석 대체 수단 부재 | `--resolve`·`--address`·`--ip`·`--connect-to` **없음** |
| context | `CERT_REQUIRED`, `check_hostname=True` |
| 우선순위 | 미해석 + 인증서 실패가 동시일 때 판정은 **FAIL**(결함이 전제보다 우선) |
| 주소 차단 | 실제 주소 5종(IPv4 3·IPv6 2) 전부 거부, ISO 시각·SHA-256·호스트명·`2026-12-28`은 통과 |
| 실행 | clean tree에서 실행, 판정 **BLOCKED_EXTERNAL**, exit 3, 두 증거 파일에 **주소 형태 0건** |
| 제어 평면 | **내가 설정한** 인스턴스가 잘못된 토큰·토큰 없음 모두 **401 `AUTH-0050`** |
| 손대지 않은 것 | `8080`을 점유한 다른 프로세스(읽기만), 노드 컨테이너, sudo **0건** |

`origin()`은 신뢰 bundle 생성기에서 **의도적으로 복제**했다. 이 branch는 착지된 integration 기준이고 그 모듈이 아직 없으며, smoke가 미착지 코드를 필요로 해서는 안 된다. 두 구현이 어긋나면 그것이 결함이므로 형태를 똑같이 유지했다.

## 6. 다음 첫 행동

1. **사용자**: hosts 적용(관리자·sudo) + 사내 root 반입. 그것이 `(a)`~`(c)`를 여는 유일한 열쇠다.
2. **Claude**: 적용 확인되면 같은 도구를 그대로 다시 돌려 **`runEnvironment` 그대로의 측정 보고서**를 남긴다. 기대는 `PASS`이고, 아니면 그 자체가 찾던 결함이다.
3. 독립 검토는 Codex.
