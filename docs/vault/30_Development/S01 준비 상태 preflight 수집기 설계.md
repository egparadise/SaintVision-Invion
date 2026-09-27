---
doc_id: "SPEC-S01-READINESS-PREFLIGHT-001"
title: "S01-BE·S01-ST 준비 상태 preflight 수집기 설계"
version: "1.3.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T14:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S01-BE", "S01-ST", "preflight", "read-only", "redaction"]
---

# S01-BE·S01-ST 준비 상태 preflight 수집기 설계

## 목적과 입력

`tools/s01_readiness_preflight.py`는 사용자 입력 U1~U6이 준비된 직후 한 번 실행해
S01의 현재 합격 신호와 남은 차단을 redacted JSON 하나로 고정한다. 입력은 Control
Plane base URL, #129 `/v1/operations/configuration-readiness`의 exact URL, session token과
operator token의 환경변수 이름, S01 inventory JSON, LAN pilot private state, Node CA bundle,
선택적인 HTTP TLS CA bundle, #135 Storage 왕복 evidence JSON과 별도 운영자 attestation JSON이다. 두 토큰은 같아도 되지만
별도 operator token을 우선하며, 토큰·DSN은 CLI 인자로 받지 않고 환경 또는 보호 state에서만
읽는다. 입력이 없으면 합성하지 않고 해당 U 항목을 `BLOCKED`로 둔다.

settings 요청은 operator Bearer로만 수행한다. 401·403·503은 자격/운영 표면이 준비되지
않은 `BLOCKED`이고 404를 포함한 다른 비정상 응답이나 계약 불일치는 `FAIL`이다. `status` 문자열을 그대로
믿지 않고 `unresolvedSettings`의 정본 이름 목록으로 Node CA와 object-store endpoint를 각각
판정하며, status와 파생 상태가 다르면 실패한다. `ready`는 두 입력의 **구조가 준비됨**을
뜻할 뿐 Node 체인·Storage 왕복이나 S01 합격 증거가 아니다.

S01 inventory `schemaVersion=s01-readiness-inventory:1`은 토폴로지와 정확히 5개 Node의
식별·DNS·OS·역할·certificate fingerprint, CPU 모델/코어, GPU 모델/VRAM/driver,
disk/NIC, 실제 capacity, 허용 상한·절대 폴더, NTP source/스큐, Storage 역할을 담는다.
CPU는 millicores, memory/storage는 bytes, GPU는 devices, network는 bitsPerSecond 정본
단위를 쓴다. 허용 상한은 capacity를 넘을 수 없고 CP 겸임 토폴로지는 정확히 한 Node만
`cp-colocated`여야 한다.

## 검사와 판정

| 검사 | 입력/U 항목 | PASS | FAIL | BLOCKED |
|---|---|---|---|---|
| configuration readiness — Node CA | U3 | 200 이름 목록에 `INV_NODE_MTLS_CA_BUNDLE` 없음 | 응답/형식/status 불일치 | URL/token 없음, 401·403·503, 이름이 unresolved |
| configuration readiness — Object Store | U6 | 200 이름 목록에 `INV_OBJECT_STORE_ENDPOINT` 없음 | 응답/형식/status 불일치 | URL/token 없음, 401·403·503, 이름이 unresolved |
| `/readyz` | U2·U3 | 200, `status=ready` | 그 외 | base URL 없음 |
| `/v1/session` | U2 | 실토큰 200과 무토큰 401·Bearer | 제공된 토큰 또는 익명 경계 불일치 | 토큰 없음 |
| Node 인증서 체인 | U3·U5 | inventory 5대가 모두 등록되고 CA 서명·유효기간·leaf `ca=false`·`SERVER_AUTH`·nodeId/epoch의 정확한 SPIFFE URI를 만족 | 제공된 체인/identity/fingerprint 불일치 | CA/state가 없거나 5대 등록 미충족 |
| DNS | U4 | inventory에 선언한 CP·portal·IdP·Node 이름 전부 해석 | 제공된 이름 중 해석 실패 | inventory/이름 없음 |
| inventory lint | U1·U5·U6 | 5 Node와 필수 값·단위·상한·폴더·NTP가 정합 | 값/형식/중복/상한 위반 | 파일 또는 필수 사용자 값 없음 |
| pilot PG 대조 | U5 | read-only transaction에서 등록 5 Node의 CPU/RAM/profile/cert가 inventory와 일치 | DB/등록/관측 값 불일치 | state/DSN/inventory 없음 |
| Storage 왕복 evidence | U6 | operational·PASS, 필수 check 6개 true, HEAD 조상 `codeSha`, 24시간 이내 UTC `observedAt`, 별도 운영자 attestation 결속 | operational evidence 자체가 `status=FAIL` | 파일/형식/조건/attestation 중 하나라도 미충족 |

U 항목 판정은 연결된 검사 중 `FAIL > BLOCKED > PASS` 우선순위로 집계한다. 이 보고서는
S01 자동 `done` 판정이 아니며 Storage retention/GC·제품 adapter·독립 검토·운영 인수를
대신하지 않는다. 특히 U2(IdP)는 settings 결과와 무관하게 `/readyz`와 실토큰/무토큰
session 경계만으로 판정한다.

## 보안·읽기 전용·출력 계약

HTTP는 GET만 사용하고 redirect를 따르지 않는다. Node CA와 HTTP TLS CA는 분리하며 session/operator
토큰을 `http://` Control Plane으로 전송하지 않는다. pilot PG는 `REPEATABLE READ READ ONLY`,
2초 statement timeout, tenant local scope에서 SELECT만 수행한다. LAN state, serve/observe,
인증서와 heartbeat를 수정하지 않는다. output이 inventory·두 CA 또는 state 디렉터리와 그
하위 또는 Storage evidence·attestation 자체이면 삭제 전에 거부한다. 보호 검사를 통과한 output만 실행
시작 시 삭제해 실패 뒤 stale PASS가 남지 않게 한다.

JSON에는 schema version, 시각, `readOnly=true`, `redacted=true`, 검사/U별 status·고정
reason code·개수/불리언만 기록한다. URL, hostname, IP, Node/tenant ID, fingerprint, 경로,
토큰, DSN, 인증서 원문과 예외 문자열은 기록하지 않는다. exit code는 전부 PASS 0,
하나라도 FAIL 1, FAIL 없이 BLOCKED만 있으면 2다.

Storage evidence는 #135가 실제 생성하는 top-level 8개 필드와 필수 check 6개의 정확한 키 집합만
허용한다. 알 수 없는 top-level 필드나 check 이름은 전부 `BLOCKED`다. 운영자 attestation은
별도 `--storage-attestation` 파일이며 `executedBy`, `configurationProfile`, `runbookRevision`,
`codeSha`, `observedAt`의 정확한 다섯 키와 비어 있지 않은 절차 문자열만 허용한다. 두 파일의
`codeSha`와 `observedAt`이 정확히 같아야 하며 보고서에는 값 대신 완전성·결속 boolean만 남긴다.
`targetKind=ci-candidate`, unreachable/non-ancestor SHA, 24시간 초과·비UTC·미래 시각,
BLOCKED 또는 false/missing check는 U6 `BLOCKED`다. 신뢰 가능한 operational evidence가
`status=FAIL`이면 제품 실패를 숨기지 않고 U6 `FAIL`이다. 필수 check는 `put`, `get`,
`bodySha256`, `metadataSha256`, `delete`, `cleanupVerified`다.

PR head에서 만든 evidence는 squash merge 뒤 그 `codeSha`가 현재 checkout의 조상이 아닐 수
있다. 운영 runbook은 병합된 integration checkout에서 evidence와 attestation을 다시 생성해야
하며, 404 configuration-readiness route는 입력 미제공이 아니라 배포 표면 불일치 `FAIL`로 남긴다.

pilot PG 대조는 현재 snapshot 정본에 존재하는 CPU/RAM/profile과 channel certificate만
검증한다. GPU와 NTP는 해당 DB snapshot에 정본 필드가 없으므로 inventory lint의 사용자
입력 검증 범위이며, 이 수집기가 DB 관측 일치를 주장하지 않는다.
