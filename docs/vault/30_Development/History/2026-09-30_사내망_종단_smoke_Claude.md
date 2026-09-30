---
doc_id: "HIST-INTRANET-E2E-SMOKE-2026-09-30"
title: "사내망 종단 smoke v1.2 (카드 155) — 검토 두 축이 찾은 fail-open을 닫았다: 시험 대상 신원이 CLI 인자였기 때문에 foreign issuer로 PASS가 재현됐다. issuer·client·신뢰 키를 제어 평면 설정에서 읽고 TLS 대상을 그 issuer에서 유도해 SNI·Host·announced issuer가 한 문자열이 되게 했다. invalid_client를 grant-disabled PASS에서 제거하고, 제어 평면 401은 정본 ProblemDetails·AUTH-0050만 인정하며, 서명까지 도달하는 토큰으로 검증한다. 해석된 뒤의 연결 실패는 FAIL이다. 되살림 변이 12종 전부 죽는다. v1.2에서 검토 두 축의 11건을 더 닫았다 — 승인 root 옆에 CA:FALSE self-signed leaf를 끼우면 `get_ca_certs()`가 그것을 빼고 돌려주므로 basicConstraints·승인 목록 검사를 **전부 우회해 TLS가 통과했다**(실측), 설정 digest만으로 PASS를 주던 결속을 NOT_BOUND로 정직하게 바꿨고, JWKS는 교집합이 아니라 **정확히 같은 집합**을 요구하며 key material까지 비교한다, OAuth error는 token endpoint의 status와 함께만 증거가 된다"
version: "1.2.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "user"
updated: "2026-09-30T10:54:43+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "6fc0428b"
task_ids: ["S01-BE"]
tags: ["history", "intranet", "smoke", "oidc", "card-155"]
---

# 사내망 종단 smoke (카드 155, 2026-09-30)

## 0. v1.1에서 바뀐 것 — 시험 대상 신원이 인자였다

첫 판은 **fail-open이었고 지적이 정확했다.** `--idp-host`·`--idp-port`·`--issuer`를 각각 자유롭게 받고, discovery의 issuer가 *호출자가 준 문자열*과 같은지만 봤다. 그래서 실제 provider에 접속하면서 foreign issuer를 검증해도 신원 관측이 전부 PASS였다 — 검토가 그것을 직접 재현했다.

**시험 대상 신원은 더 이상 인자가 아니다.** issuer·client id·신뢰 키 id를 **제어 평면 자신의 설정 파일**에서 읽고 그 bytes와 신뢰 bundle을 보고서에 해시로 남기며, **TLS 대상을 그 issuer에서 유도**한다. 그래서 SNI·Host 헤더·announced issuer가 세 flag의 합의가 아니라 **구성상 한 문자열**이다. issuer는 https·userinfo/query/fragment 없음·정본 realm 경로여야 한다.

그 과정에서 이전 모양으로는 표현할 수 없던 관측 두 개가 생겼다 — **설정된 client가 provider에 실제로 알려져 있는가**, 그리고 **provider가 서빙하는 키가 제어 평면이 신뢰하는 키인가**. 후자가 없으면 두 조각이 서로를 향해 정렬돼 있어도(각자 정상) 모든 토큰이 거부된다.

다른 변경은 §2·§5·§7에 녹였다. 요약하면: `invalid_client`는 grant 비활성의 증거가 아니라 **client가 없다는 별개 사실**이고, 제어 평면 401은 **정본 `ProblemDetails`·`AUTH-0050`**만 인정하며(loopback의 아무 프로세스나 401을 낼 수 있다), bad token은 **서명 검증까지 도달하는** 토큰이고, CA는 **한 번 읽은 bytes**로 신뢰하며, context를 직접 구성해 `SSLKEYLOGFILE`이 TLS 비밀을 파일로 빼내지 못하게 한다. 해석된 뒤의 연결·TLS·endpoint 실패는 **FAIL**이다.

**그리고 두 개의 크래시가 있었다.** `failed("...", reason=...)`가 `TypeError`를 던져 **인증서 검증 실패 경로에서 증거 없이 run이 끝났다** — 하필 그 경로였다. 두 번째 TLS 연결이 그것을 감싸야 할 `try` 밖에 있었다. 둘 다 고치고 시험으로 고정했다.

## 1. v1.2에서 바뀐 것 — 신뢰 bundle 검사가 신뢰 store를 보고 있었다

검토 두 축이 11건을 냈고, 그중 하나는 **차단**이었다.

**`get_ca_certs()`는 CA가 아닌 인증서를 빼고 돌려준다.** 그래서 bundle에 승인된 root **하나와** `basicConstraints: CA:FALSE`인 self-signed leaf **하나**를 넣으면, 그 leaf는 store에 적재되고 **자기 자신의 anchor로 동작하면서** 그 목록에는 나타나지 않는다. 직접 재현했다 — `cert_store_stats()`가 `{'x509': 2, 'x509_ca': 1}`이고 `get_ca_certs()`는 root 하나만 돌려주며, 그 leaf를 제시하는 서버에 **TLS 검증이 통과한다**. 즉 `basicConstraints` 검사와 승인 목록 대조가 **그 leaf가 애초에 없는 목록을 읽고 있었다.**

v1.1의 "leaf를 anchor로 넣으면 거부"라는 문장은 **leaf 하나만 넣은 경우에만 참이었다.** 그때는 store에 authority가 0개가 되어 다른 분기("CA가 하나도 없다")로 빠졌기 때문에 시험이 통과했고, 그 시험은 이 결함을 볼 수 없었다. **정정한다.**

지금은 PEM을 `x509.load_pem_x509_certificates`로 직접 파싱해 **전수 검사**하고, 개수를 `cert_store_stats()['x509']`와 대조하며, 반대 방향으로 store가 나열하는 CA가 검사한 bytes에 없으면 그것도 거부한다.

**설정 결속은 PASS를 주장할 수 없다.** `controlPlaneConfigurationBound`가 설정 파일 digest만으로 `MEASURED_PASS`였다 — **파일에 대한 주장을 배포에 대한 주장으로 입고 있었다.** 지금은 반증만 하고 확인은 하지 않으며, 그렇다고 말한다:

- `/readyz`가 200이 아니면 **MEASURED_FAIL** — `tokens is None`일 때 `app.py`가 503을 내고 `/readyz`는 `tokens._keys()`로 bundle까지 적재한다. `/v1/session`이 401을 낸다고 준비된 것이 되지는 않는다.
- 준비됐는데 설정된 bundle이 그 verifier가 거부할 것(만료, `{issuer, expiresAt, keys}`가 아닌 shape)이면 **MEASURED_FAIL** — 준비된 제어 평면이 그 파일을 적재했을 수 없으므로 **다른 파일을 쓰고 있다는 실증**이다. 얻을 수 있는 유일한 긍정 판별이다.
- 준비됐고 bundle도 정상이면 **`NOT_BOUND` (RECORDED_ONLY)** — 어느 파일에서 왔는지는 관측 불가다. 제품이 무엇을 노출해야 결속이 가능한지 `bindingGap`에 그대로 적는다.

이 관측은 **필수**이므로 `NOT_BOUND`인 실행의 전체 판정은 `PASS`가 되지 않는다. 그것이 정직한 상태이고, pass에 흡수되지 않고 보이는 곳에 남는 것이 목적이다.

**JWKS는 교집합이 아니라 같은 집합이어야 한다.** 교집합은 "신뢰되는 키 하나 + 아무도 모르는 키 하나"를 내는 provider에게 만족된다 — 그 provider는 받아들여지는 토큰도, 계정이 없는 키로 서명한 토큰도 만들 수 있다. 지금은 집합이 **같아야** 하고, 같은 `kid`에 다른 modulus를 실으면(신뢰 bundle이 막으려는 바로 그 치환) `substitutedKidSha256`으로 FAIL이다.

**OAuth error는 status와 함께만 증거다.** `(503, "unauthorized_client")`가 잠긴 문으로 읽혔다. 유지보수 페이지·proxy·다른 서비스가 그 본문을 낼 수 있다. 내려가 있는 서비스는 꺼져 있는 grant가 아니다. 이제 RFC 6749 §5.2의 **400/401만** 허용한다.

**본문 전체를 엄격히 파싱한다.** 첫 `{`부터 마지막 `}`까지 자르면 brace를 품은 **아무 문서에서나** JSON 객체를 읽어낸다. `--out-dir` 경로도 stdout에서 뺐다 — 검사한 bytes와 출력한 bytes가 달랐고, 절대 경로는 이 PC의 계정 이름을 PR 코멘트로 옮긴다.

증거 schema를 `intranet-e2e-smoke:3`으로 올렸다. **`…-r1.json`(schema `:2`)의 `controlPlaneConfigurationBound: MEASURED_PASS`는 여기서 찾은 fail-open 그 자체이므로 인수 근거로 읽으면 안 된다** — 측정 기록이므로 지우지 않고 남기되 대체됐다고 적는다.

## 2. 무엇이 나왔나

`tools/intranet_e2e_smoke.py`. 신원 경로의 조각들은 각각 측정돼 있었지만, 그것이 **배포된 상태로 줄이 맞는지**는 다른 주장이다 — 이름이 해석되는지, 제시되는 인증서가 사내 CA가 낸 그것인지, discovery의 issuer가 제어 평면에 설정된 문자열과 같은지, 제어 평면이 거부해야 할 토큰을 거부하는지.

| 관측 | 결과 |
|---|---|
| **`controlPlaneConfigurationBound`** | v1.1 기록은 **MEASURED_PASS**였고 그것이 §1의 결함이다. v1.2 코드로는 `/readyz` 200 + bundle 정상이면 **`NOT_BOUND` (RECORDED_ONLY)**, 준비 안 됐거나 bundle이 적재 불가면 **MEASURED_FAIL** |
| `idpNameResolves` | **BLOCKED_EXTERNAL** `hosts-not-applied` |
| `idpHttpsVerified` | BLOCKED_EXTERNAL (issuer의 host 미해석) |
| `idpDiscoveryIssuer` | BLOCKED_EXTERNAL (동일) |
| `portalClientKnown` | BLOCKED_EXTERNAL (동일) |
| `idpJwksMatchesTrustBundle` | BLOCKED_EXTERNAL (동일) |
| `passwordGrantRefused` | BLOCKED_EXTERNAL (동일) |
| `clientCredentialsRefused` | BLOCKED_EXTERNAL (동일) |
| **`controlPlaneRejectsBadToken`** | **MEASURED_PASS** — `401`, `application/problem+json`, `AUTH-0050`, 정본 shape |
| **`controlPlaneRejectsMissingToken`** | **MEASURED_PASS** — 동일 |

전체 판정 **`BLOCKED_EXTERNAL`**, exit 3 — 해석되지 않는 이름이 그 위에 있으므로 v1.2 코드로도 판정은 같다. 증거는 `docs/vault/30_Development/Evidence/intranet-e2e-smoke/`이고 두 판을 함께 둔다 — schema `:1`(첫 판)과 `:2`(v1.1). **둘 다 대체됐다**: 현재 도구는 `:3`을 쓰고, `NOT_BOUND`를 낼 수 있는 결속 관측은 두 기록에 없다. 측정 기록이므로 지우지 않는다.

**bad token이 이제 서명 검증까지 간다.** 첫 판의 `not.a.valid.token`은 header 파싱에서 거부돼 issuer·audience·kid·서명 경로를 **전혀 타지 않았다**. 지금은 제어 평면이 신뢰하는 kid를 지목하고 필수 claim 7종을 갖춘 well-formed 토큰이며 **서명만 틀리다** — 그리고 돌아온 거부가 정본 `problem+json`의 `AUTH-0050`이다. 관측할 가치가 있는 거부는 그것이다.

## 3. 하지 않기로 만든 세 가지

이것들은 약속이 아니라 **구조로 막았고, 그 사실 자체를 시험이 붙들고 있다.**

**인증서 검증을 끄는 수단이 없다.** flag가 아예 없고, 시험이 `--insecure`·`--no-verify`·`-k` 같은 option이 **존재하지 않음**을 단정한다. 끌 수 있는 smoke는 언젠가 그렇게 돌려지고, 그때의 PASS는 아무 의미가 없다.

**이름 해석을 대체하는 수단이 없다.** `--resolve`·`--address`·`--connect-to`가 없음을 시험이 단정한다. `idp.sv.lan`이 해석되지 않으면 답은 **`BLOCKED_EXTERNAL` `hosts-not-applied`** 이고, 주소로 조용히 우회하면 **운영자가 아직 해야 할 일 하나를 가리는** 셈이다. 다만 **측정된 실패가 미충족 전제보다 우선한다** — 인증서가 틀린 것은 결함이고 "아직 준비 안 됨"이 아니다. 그 우선순위를 시험으로 고정했다.

**실제 사용자의 password grant를 쓰지 않는다.** 그 grant는 portal client에서 의도적으로 꺼져 있고, 이 도구는 **존재할 수 없는 계정 이름**으로 거부를 확인한다 — 열쇠를 들지 않고 문이 잠겼는지 보는 방식이다.

여기서 이 검사가 의미를 갖게 하는 구분이 있다. **`invalid_grant`는 틀린 거부다** — 그것은 이 client가 해당 grant를 *쓸 수 있다*는 뜻이고, 그 자체가 결함이다. "200이 아니면 통과"로 만들었다면 **살아 있는 password grant를 잠긴 문으로 보고**했을 것이다.

**그리고 `invalid_client`도 틀린 거부다.** 첫 판은 그것을 PASS 집합에 넣었는데, `invalid_client`는 "client가 알려지지 않았다"는 뜻이고 "알려진 client의 grant가 꺼져 있다"는 증거가 아니다. 검토가 재현한 대로 **client id에 오타가 있으면 두 grant가 모두 잠긴 문으로 읽혔다.** PASS 집합에서 빼고, **client가 알려져 있는지를 별도 관측**으로 분리했다 — `invalid_client`가 오면 그 관측이 실패하고 grant 관측도 통과할 수 없다.

## 4. 제어 평면 401은 *어떤* 401인가

**loopback의 아무 프로세스나 401을 낼 수 있다.** 첫 판은 body가 `{}`여도 PASS였다 — nginx의 401도 같은 PASS였을 것이다. 지금은 넷을 모두 요구한다.

| 요구 | 왜 |
|---|---|
| `application/problem+json` | 임의 앱의 401을 배제한다 |
| status `401` | `503`은 **identity trust 미설정**이라는 다른 상태이고 같은 `AUTH-0050`을 낸다 — 거부로 세면 안 된다 |
| 정본 `ProblemDetails` shape (정확히 10키) | 계약이 `additionalProperties: false`다 |
| `code == AUTH-0050`, `category == AUTH` | 다른 코드의 401은 다른 사실이다 |

HTTP parser가 response header를 버리고 있어서 media type을 볼 수 없었다 — header를 보존하도록 고쳤다. `/readyz`도 함께 기록한다(요구 아님, **기록만**) — 어느 프로세스가 답했는지는 어느 쪽이든 알 가치가 있다. 이번 실행에서 `readyz`는 `503`이었고, 그것이 기록돼 있다.

## 5. 보고서가 무엇을 담지 않는가

주소·토큰·키가 들어가지 않는다. 그리고 그것을 **만드는 코드의 선의에 맡기지 않고 직렬화된 출력에서 검사**한다 — `assert_no_addresses`가 IPv4·IPv6 형태를 찾으면 파일을 쓰지 않는다.

그 과정에서 두 가지를 바꿨다.

- **인증서의 `notAfter`를 날짜로 정규화했다.** `Dec 28 23:05:05 2026 GMT`의 시각 부분이 검사기에 **IPv6로 읽힌다.** 검사기에 예외를 가르치는 대신 기록 형식을 `2026-12-28`로 바꿨다 — 읽는 사람에게도 만료일이 필요한 것이다.
- **제어 평면을 주소가 아니라 이름으로 적는다.** `loopback` / `non-loopback` + 포트. loopback 주소가 무엇을 누설하지는 않지만, "주소 0건"을 예외 없는 규칙으로 두는 편이 낫다.

ISO 시각도 콜론 때문에 IPv6로 읽히므로 검사 전에 제거한다. 그 경계들을 시험으로 고정했다(`2026-09-30T09:10:10+09:00`·SHA-256·호스트명은 조용하고, 실제 주소 5종은 반드시 걸린다).

## 6. 제어 평면 401은 어떤 제어 평면인가

**중요한 사실 하나**: 이 PC의 `8080`은 **다른 프로세스가 이미 점유**하고 있었다. 처음 그 포트로 측정했을 때 `401 AUTH-0050`이 돌아왔지만, 그것은 **내가 설정하지 않은 앱**의 응답이었다 — 그 앱의 issuer·JWKS 신뢰를 내가 모르므로 카드의 "그 issuer/JWKS trust를 넣었을 때"를 만족하지 않는다. 그 측정은 버렸다.

대신 **내가 설정한 인스턴스를 loopback의 다른 포트에 띄웠다**. 설정은 카드 152에서 세운 것과 같은 다섯 값이고, `jwks_file`은 검증된 https로 받아 둔 JWKS로 만든 신뢰 bundle이다. 그 인스턴스가 두 경우 모두 `401` `AUTH-0050`으로 답한다.

- 잘못된 bearer → **401**. 첫 판의 `not.a.valid.token`이 아니다 — §2에 적은 대로 지금은 제어 평면이 신뢰하는 `kid`를 지목하고 필수 claim 7종을 갖춘 **well-formed·서명만 틀린** 토큰이며, 그래야 header 파싱에서 멈추지 않고 issuer·audience·kid·서명 경로를 실제로 탄다. 증거 파일의 `probe: signed-but-invalid`가 그것이다.
- `Authorization` 없음 → **401** (`probe: no-authorization`)

보고서에 포트가 적히므로 어느 인스턴스였는지 감춰지지 않는다. 남의 프로세스는 건드리지 않았다(읽기만).

부수로 두 가지를 확인했다 — 제어 평면은 `jsonschema[format]`이 없으면 **오류 응답을 만들다가 500**이 된다(`date-time` 검증이 필수라서 problem 문서 자체가 만들어지지 않는다). 그리고 landed 앱은 `src`와 `services/control-plane/src` **둘 다** import 경로에 있어야 기동한다.

## 7. 왜 해석되는 환경에서 한 번 더 돌리지 않았나

(a)~(c)를 실측하려면 이름이 해석되는 환경이 필요하다. 지금 **어느 환경에서도 해석되지 않는다** — 이 PC의 hosts는 관리자 권한이 필요하고 노드의 `/etc/hosts`는 sudo가 필요하며, 둘 다 사용자 실행으로 남아 있다.

`--add-host`를 쓴 container 안에서 돌리는 방법은 있었지만 **하지 않았다.** 그 환경에는 git이 없어 `codeSha`가 비고, 이 도구는 40-hex commit이 아니면 증거를 쓰지 않는다. 우회해서 SHA를 만들어 넣는 것은 **측정하지 않은 것을 측정한 것처럼** 만드는 일이라, 측정하지 않는 편을 택했다. 대신 `runEnvironment`를 **필수 필드**로 만들어, 나중에 해석되는 환경에서 돌린 보고서를 이 보고서와 혼동할 수 없게 했다.

`(a)`~`(c)`의 판정 논리 자체는 부정 시험으로 덮여 있다 — issuer 불일치, 다른 origin의 `jwks_uri`, RS256 서명 키 없음, grant가 틀린 이유로 거부됨, 200으로 발급됨.

## 8. 검증 (실제 수행한 것만)

| 확인 | 결과 |
|---|---|
| 단위·부정 시험 | `tests/core/test_intranet_e2e_smoke.py` **140 passed**(v1.1은 103) — 대부분 **실제 TLS 서버와 실제 socket**, 서로 다른 CA 두 개. 첫 판의 60건은 helper를 monkeypatch해 "helper가 시킨 값을 돌려준다"만 증명했고, 그래서 host↔issuer 불일치를 놓쳤다 |
| **되살림 변이** | 검토 12건을 **실제 도구에 하나씩 주입해 전부 죽는 것**을 확인했다(CLI issuer 복구·`invalid_client` 복귀·아무 401 수용·`cafile` 복귀·default context·해석 후 강등·IPv6 누락·`reason` 키워드·빈 집합 PASS·deadline 흡수·oversize 절단·`503` 수용) |
| 전 경로 측정 | 시험 안에서 **내부 CA로 서명한 localhost leaf**를 쓰는 provider를 세워 **관측 가능한 9건 전부 `MEASURED_PASS`**, 결속 1건은 `NOT_BOUND`, 전체 `NOT_OBSERVED`를 확인했다. v1.1은 여기서 10/10 PASS를 주장했고 그 10번째가 파일 digest였다 |
| 검증 무력화 수단 부재 | option 집합에 `--insecure`·`--no-verify`·`--skip-verify`·`-k`·`--allow-insecure` **없음**, `--ca-bundle`은 **필수** |
| 해석 대체 수단 부재 | `--resolve`·`--address`·`--ip`·`--connect-to` **없음** |
| context | `CERT_REQUIRED`, `check_hostname=True` |
| 우선순위 | 미해석 + 인증서 실패가 동시일 때 판정은 **FAIL**(결함이 전제보다 우선) |
| 주소 차단 | 실제 주소 6종(압축 `::1` 포함) 전부 거부, ISO 시각·SHA-256·호스트명·`2026-12-28`은 통과. 첫 판은 `::1`을 통과시켰다 — 콜론을 strip하면 `1`이 남아 주소가 아니게 됐다. 이제 `ipaddress`로 판정한다 |
| 자격증명 차단 | URL userinfo·bearer·JWT·PEM·`Authorization:` 거부, JSON·Markdown·stdout **셋 다** 검사 |
| CA 결속 | **PEM을 직접 전수 파싱**해 전부 CA임을 `basicConstraints`로 확인, 개수를 `cert_store_stats()['x509']`와 대조, store가 나열하는 CA가 검사한 bytes에 없으면 거부, 승인 목록과 대조, **한 번 읽은 bytes를 `cadata`로** 신뢰. **승인 root + CA:FALSE self-signed leaf**를 넣으면 거부(v1.1은 통과시켰다), leaf 단독도 거부, 승인 안 된 root가 섞이면 네트워크 전에 거부 |
| 환경 독립 | `SSL_CERT_FILE`·`SSL_CERT_DIR`·`REQUESTS_CA_BUNDLE`·`PYTHONHTTPSVERIFY`·`CURL_CA_BUNDLE`을 세워도 anchor 불변, `SSLKEYLOGFILE`에도 `keylog_filename is None` |
| **되살림 변이 (v1.2)** | 검토 11건을 **실제 도구에 하나씩 주입해 전부 죽는 것**을 확인했다 — 교집합 복귀 · key material 무시 · 결속 `MEASURED_PASS` 복귀 · status 무시 · brace slice 복귀 · stdout에 전체 경로 · `get_ca_certs()` 복귀 · `if statuses:` · readyz 무시 · bundle 창 무시 · 상대 `jwks_file` 허용. 주입 후 도구는 원본으로 복원했다(대조 확인) |
| 실행 | clean tree에서 실행, 판정 **BLOCKED_EXTERNAL**, exit 3, 두 증거 파일에 **주소 형태 0건**. v1.2 코드로 새 증거는 **아직 쓰지 않았다** — `/readyz` 200을 요구하므로 신원과 **데이터베이스가 함께 준비된** 제어 평면이 필요하고, 이 PC의 메모리 제약 안에서 그것까지 띄우지 않았다. 측정하지 않은 것을 쓰지 않는다 |
| 제어 평면 | **내가 설정한** 인스턴스가 잘못된 토큰·토큰 없음 모두 **401 `AUTH-0050`** |
| 손대지 않은 것 | `8080`을 점유한 다른 프로세스(읽기만), 노드 컨테이너, sudo **0건** |

`origin()`은 신뢰 bundle 생성기에서 **의도적으로 복제**했다. 이 branch는 착지된 integration 기준이고 그 모듈이 아직 없으며, smoke가 미착지 코드를 필요로 해서는 안 된다. 두 구현이 어긋나면 그것이 결함이므로 형태를 똑같이 유지했다.

## 9. 다음 첫 행동

1. **사용자**: hosts 적용(관리자·sudo) + 사내 root 반입. 그것이 `(a)`~`(c)`를 여는 유일한 열쇠다.
2. **Claude**: 적용 확인되면 같은 도구를 그대로 다시 돌려 **`runEnvironment` 그대로의 측정 보고서**를 남긴다. 그때 제어 평면은 `/readyz` 200이어야 하므로 신원과 데이터베이스를 함께 세운다. 기대 판정은 **`NOT_OBSERVED`**다 — 결속이 `NOT_BOUND`인 동안 `PASS`는 나올 수 없고, 그것이 의도다.
3. **코디네이터 결정 사항**: 결속을 `PASS`까지 올리려면 제품이 무엇 하나를 노출해야 한다 — 인증 없는 endpoint에 설정 digest(또는 issuer) 한 필드. `bindingGap`에 필요한 것을 그대로 적어 두었다. 제어 평면 표면 변경이므로 **이 PR에서 하지 않았다**: 검토 중인 smoke PR에 제품 코드를 얹지 않고, 배정 없이 코어 표면을 바꾸지 않는다.
3. 독립 검토는 Codex.
